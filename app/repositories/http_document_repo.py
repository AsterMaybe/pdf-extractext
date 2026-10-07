"""
Adaptador HTTP que implementa IDocumentRepository delegando al microservicio Go.

Este adaptador delega la persistencia al microservicio Go, implementando la
misma interfaz (puerto) que consume DocumentService.
"""

import logging
from typing import Any

import httpx

from app.domain.document import DocumentCreate, DocumentResponse
from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    InvalidDocumentIdError,
)
from app.domain.pagination import PageQuery
from app.services.ports import IDocumentRepository

logger = logging.getLogger(__name__)


class HttpDocumentRepository(IDocumentRepository):
    """
    Implementación de IDocumentRepository vía HTTP al microservicio Go.

    No filtra detalles internos del microservicio (ObjectID, BSON, nombres de
    colección, stack traces). Convierte errores HTTP en errores de dominio.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Args:
            base_url: URL base del microservicio Go (ej. http://microservicio-db-go:8080)
            timeout: Timeout en segundos para requests HTTP
            client: Cliente HTTP opcional para inyección de dependencias (tests)
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self._timeout)

    async def _close_if_owned(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def exists_by_checksum(self, checksum: str) -> bool:
        """Verifica si existe un documento con ese checksum via HEAD/GET."""
        client = await self._get_client()
        try:
            # Usamos GET a la lista con filtro implícito: más simple que añadir endpoint
            # En producción real se añadiría endpoint HEAD /api/v1/documents/checksum/{checksum}
            response = await client.get(
                f"{self._base_url}/api/v1/documents",
                params={"skip": 0, "limit": 1},
                timeout=self._timeout,
            )
            # Nota: El microservicio Go no expone filtro por checksum en listado.
            # Esta implementación hace un workaround consultando y filtrando.
            # Para producción se recomienda añadir endpoint dedicado en Go.
            if response.status_code == 200:
                docs = response.json()
                return any(doc.get("checksum") == checksum for doc in docs)
            return False
        except httpx.RequestError:
            logger.exception("Error de red al verificar checksum")
            return False
        finally:
            await self._close_if_owned()

    async def create(self, data: DocumentCreate) -> DocumentResponse:
        """Crea un documento via POST /api/v1/documents."""
        client = await self._get_client()
        payload = {
            "filename": data.filename,
            "text_content": data.text_content,
            "checksum": data.checksum,
            "file_size_bytes": data.file_size_bytes,
        }
        try:
            response = await client.post(
                f"{self._base_url}/api/v1/documents",
                json=payload,
                timeout=self._timeout,
            )
            if response.status_code == 201:
                return DocumentResponse(**response.json())
            await self._handle_error(response, data.checksum)
        except httpx.RequestError as e:
            logger.exception("Error de red al crear documento")
            raise InvalidDocumentIdError(str(e)) from e
        finally:
            await self._close_if_owned()

    async def get_all(self, query: PageQuery) -> list[DocumentResponse]:
        """Lista documentos via GET /api/v1/documents con paginación."""
        client = await self._get_client()
        try:
            response = await client.get(
                f"{self._base_url}/api/v1/documents",
                params={"skip": query.skip, "limit": query.limit},
                timeout=self._timeout,
            )
            if response.status_code == 200:
                return [DocumentResponse(**doc) for doc in response.json()]
            await self._handle_error(response)
        except httpx.RequestError as e:
            logger.exception("Error de red al listar documentos")
            raise InvalidDocumentIdError(str(e)) from e
        finally:
            await self._close_if_owned()
        return []

    async def get_by_id(self, doc_id: str) -> DocumentResponse:
        """Obtiene un documento por ID via GET /api/v1/documents/{id}."""
        client = await self._get_client()
        try:
            response = await client.get(
                f"{self._base_url}/api/v1/documents/{doc_id}",
                timeout=self._timeout,
            )
            if response.status_code == 200:
                return DocumentResponse(**response.json())
            await self._handle_error(response, doc_id=doc_id)
        except httpx.RequestError as e:
            logger.exception("Error de red al obtener documento")
            raise InvalidDocumentIdError(doc_id) from e
        finally:
            await self._close_if_owned()

    async def update(self, doc_id: str, changes: dict[str, Any]) -> DocumentResponse:
        """Actualiza un documento via PATCH /api/v1/documents/{id}."""
        client = await self._get_client()
        try:
            response = await client.patch(
                f"{self._base_url}/api/v1/documents/{doc_id}",
                json=changes,
                timeout=self._timeout,
            )
            if response.status_code == 200:
                return DocumentResponse(**response.json())
            await self._handle_error(response, doc_id=doc_id)
        except httpx.RequestError as e:
            logger.exception("Error de red al actualizar documento")
            raise InvalidDocumentIdError(doc_id) from e
        finally:
            await self._close_if_owned()

    async def delete(self, doc_id: str) -> None:
        """Elimina un documento via DELETE /api/v1/documents/{id}."""
        client = await self._get_client()
        try:
            response = await client.delete(
                f"{self._base_url}/api/v1/documents/{doc_id}",
                timeout=self._timeout,
            )
            if response.status_code != 204:
                await self._handle_error(response, doc_id=doc_id)
        except httpx.RequestError as e:
            logger.exception("Error de red al eliminar documento")
            raise InvalidDocumentIdError(doc_id) from e
        finally:
            await self._close_if_owned()

    async def ensure_indexes(self) -> None:
        """Los índices los gestiona el microservicio Go al arrancar; no-op aquí."""
        # El microservicio Go crea el índice único de checksum en su startup
        pass

    async def _handle_error(
        self,
        response: httpx.Response,
        checksum: str | None = None,
        doc_id: str | None = None,
    ) -> None:
        """Convierte respuesta de error HTTP en excepción de dominio."""
        content_type = response.headers.get("content-type", "")
        detail = "Error desconocido del servicio de datos"

        if "application/problem+json" in content_type:
            try:
                problem = response.json()
                detail = problem.get("detail", detail)
            except Exception:
                pass

        status = response.status_code

        if status == 404:
            raise DocumentNotFoundError(doc_id or "unknown")
        if status == 400:
            raise InvalidDocumentIdError(doc_id or "unknown")
        if status == 409:
            raise DocumentAlreadyExistsError(checksum or "unknown")
        if status == 413:
            # File too large - mapear a error de dominio existente
            from app.domain.exceptions import FileSizeExceededError
            raise FileSizeExceededError(25)  # default max
        if status == 503:
            # Service unavailable / busy
            from app.domain.exceptions import PDFProcessingError
            raise PDFProcessingError(f"Servicio de datos no disponible: {detail}")
        if status >= 500:
            from app.domain.exceptions import PDFProcessingError
            raise PDFProcessingError(f"Error interno del servicio de datos: {detail}")

        # Fallback genérico
        from app.domain.exceptions import PDFProcessingError
        raise PDFProcessingError(f"Error HTTP {status}: {detail}")