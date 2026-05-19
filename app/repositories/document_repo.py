"""
Repositorio de documentos (patrón Repository).

Esta capa es la ÚNICA que habla con MongoDB.
"""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorCollection
from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate


def _map_to_response(doc: dict) -> DocumentResponse:
    """
    Convierte un documento de MongoDB (dict con _id) al modelo de respuesta.

    MongoDB usa '_id' (ObjectId), pero la API expone 'id' (string).
    Esta conversión ocurre una sola vez, aquí (DRY).
    """
    return DocumentResponse(
        id=str(doc["_id"]),
        filename=doc["filename"],
        text_content=doc["text_content"],
        checksum=doc["checksum"],
        file_size_bytes=doc["file_size_bytes"],
        created_at=doc["created_at"],
    )


class DocumentRepository:
    """CRUD sobre la colección de documentos en MongoDB."""

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        # La colección se inyecta (Dependency Injection → fácil de mockear en tests)
        self._col = collection

    async def exists_by_checksum(self, checksum: str) -> bool:
        """
        Verifica si ya existe un documento con ese checksum.
        Usado para evitar duplicados antes de insertar.
        """
        doc = await self._col.find_one({"checksum": checksum}, {"_id": 1})
        return doc is not None

    async def create(self, data: DocumentCreate) -> DocumentResponse:
        """Inserta un nuevo documento y devuelve la representación pública."""
        result = await self._col.insert_one(data.model_dump())
        created = await self._col.find_one({"_id": result.inserted_id})
        return _map_to_response(created)

    async def get_all(self) -> list[DocumentResponse]:
        """Devuelve todos los documentos almacenados."""
        cursor = self._col.find()
        return [_map_to_response(doc) async for doc in cursor]

    async def get_by_id(self, doc_id: str) -> DocumentResponse:
        """
        Busca un documento por su ID.

        Raises:
            HTTPException 400 si el ID no tiene formato válido de ObjectId.
            HTTPException 404 si no existe el documento.
        """
        oid = _parse_object_id(doc_id)
        doc = await self._col.find_one({"_id": oid})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento con id '{doc_id}' no encontrado.",
            )
        return _map_to_response(doc)

    async def update(self, doc_id: str, data: DocumentUpdate) -> DocumentResponse:
        """
        Actualiza sólo los campos provistos (PATCH semántico).

        Raises:
            HTTPException 404 si no existe el documento.
        """
        oid = _parse_object_id(doc_id)
        # Excluir campos None para no sobreescribir con null
        changes = {k: v for k, v in data.model_dump().items() if v is not None}

        if not changes:
            # Nada que actualizar → devolvemos el documento sin cambios
            return await self.get_by_id(doc_id)

        result = await self._col.find_one_and_update(
            {"_id": oid},
            {"$set": changes},
            return_document=True,  # Devuelve el documento YA actualizado
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento con id '{doc_id}' no encontrado.",
            )
        return _map_to_response(result)

    async def delete(self, doc_id: str) -> None:
        """
        Elimina un documento por su ID.

        Raises:
            HTTPException 404 si no existe el documento.
        """
        oid = _parse_object_id(doc_id)
        result = await self._col.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documento con id '{doc_id}' no encontrado.",
            )


# ── Helper privado ───────────────────────────────────────────────────────────

def _parse_object_id(doc_id: str) -> ObjectId:
    """Convierte un string a ObjectId con manejo de error claro."""
    try:
        return ObjectId(doc_id)
    except (InvalidId, Exception):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{doc_id}' no es un ID válido.",
        )
