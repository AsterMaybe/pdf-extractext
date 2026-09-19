"""
Repositorio de documentos (patrón Repository).

Esta capa es la ÚNICA que habla con MongoDB. No conoce HTTP ni el framework:
expone exclusivamente errores de dominio (subclases de `DomainError`), que la
capa de API traduce a respuestas RFC 9457.
"""

from typing import Any, Mapping

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.domain.document import DocumentCreate, DocumentResponse
from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    InvalidDocumentIdError,
)
from app.domain.pagination import PageQuery


def _map_to_response(doc: Mapping[str, Any]) -> DocumentResponse:
    """
    Convierte un documento de MongoDB (Mapping con _id) al modelo de respuesta.
    """
    return DocumentResponse(
        id=str(doc["_id"]),
        filename=doc["filename"],
        text_content=doc["text_content"],
        checksum=doc["checksum"],
        file_size_bytes=doc["file_size_bytes"],
        created_at=doc["created_at"],
    )


def _to_object_id(doc_id: str) -> ObjectId:
    """Convierte un string a ObjectId con manejo de error de dominio."""
    try:
        return ObjectId(doc_id)
    except InvalidId:
        raise InvalidDocumentIdError(doc_id)


class DocumentRepository:
    """
    CRUD sobre la colección de documentos en MongoDB.
    """

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    async def ensure_indexes(self) -> None:
        """
        Crea el índice único sobre `checksum`.

        Es la garantía atómica anti-duplicados: aunque el pre-check del servicio
        falle por una carrera (TOCTOU), `create()` convierte el `DuplicateKeyError`
        en un error de dominio en lugar de dejar que la BD devuelva un 500.
        """
        await self._col.create_index("checksum", unique=True)

    async def exists_by_checksum(self, checksum: str) -> bool:
        """
        Verifica si ya existe un documento con ese checksum.
        Usado para evitar duplicados antes de insertar.
        """
        doc = await self._col.find_one({"checksum": checksum}, {"_id": 1})
        return doc is not None

    async def create(self, data: DocumentCreate) -> DocumentResponse:
        """
        Inserta un nuevo documento y devuelve la representación pública.

        `insert_one` ya devuelve el `_id` generado y el payload contiene todos
        los datos persistidos, por lo que no se re-consulta la BD (KISS).

        El índice único de `checksum` garantiza la atomicidad: si dos request
        concurrentes insertan el mismo archivo, la BD rechaza el duplicado y acá
        se traduce a `DocumentAlreadyExistsError` (red de seguridad TOCTOU).
        """
        payload = data.model_dump()
        try:
            result = await self._col.insert_one(payload)
        except DuplicateKeyError:
            raise DocumentAlreadyExistsError(data.checksum)
        return DocumentResponse(id=str(result.inserted_id), **payload)

    async def get_all(self, query: PageQuery) -> list[DocumentResponse]:
        """Devuelve los documentos con paginación.

        Evita materializar toda la colección en memoria: la capa de datos
        protege a la capa de aplicación contra volúmenes de datos ilimitados.
        """
        cursor = self._col.find().skip(query.skip).limit(query.limit)
        return [_map_to_response(doc) async for doc in cursor]

    async def get_by_id(self, doc_id: str) -> DocumentResponse:
        """
        Busca un documento por su ID.

        Raises:
            InvalidDocumentIdError: si el ID no tiene formato válido de ObjectId.
            DocumentNotFoundError: si no existe el documento.
        """
        doc = await self._col.find_one({"_id": _to_object_id(doc_id)})
        if not doc:
            raise DocumentNotFoundError(doc_id)
        return _map_to_response(doc)

    async def update(self, doc_id: str, changes: dict[str, object]) -> DocumentResponse:
        """
        Aplica los cambios provistos sobre el documento.

        Raises:
            InvalidDocumentIdError: si el ID no tiene formato válido de ObjectId.
            DocumentNotFoundError: si no existe el documento.
        """
        result = await self._col.find_one_and_update(
            {"_id": _to_object_id(doc_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,  # Devuelve el documento YA actualizado
        )
        if result is None:
            raise DocumentNotFoundError(doc_id)
        return _map_to_response(result)

    async def delete(self, doc_id: str) -> None:
        """
        Elimina un documento por su ID.

        Raises:
            InvalidDocumentIdError: si el ID no tiene formato válido de ObjectId.
            DocumentNotFoundError: si no existe el documento.
        """
        result = await self._col.delete_one({"_id": _to_object_id(doc_id)})
        if result.deleted_count == 0:
            raise DocumentNotFoundError(doc_id)