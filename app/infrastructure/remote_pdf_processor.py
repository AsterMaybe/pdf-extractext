"""
Adaptador concreto de `IPDFProcessor` que delega la extracción de texto al
microservicio Go (microservicio-go).

Vive en `app/infrastructure` para que la capa de aplicación (servicios) nunca
dependa de un cliente HTTP concreto (Hexagonal / Ports & Adapters). La
validación de formato y el checksum se mantienen locales (rápidos y sin round
trip); sólo la extracción de texto viaja por HTTP al microservicio.

Contrato HTTP del microservicio:
- `POST {PDF_EXTRACT_SERVICE_URL}/api/v1/extract` con multipart/form-data
  (campo `file` con los bytes del PDF).
- Respuesta 200: `{"filename", "extension", "mime_type", "text"}`.
- Errores RFC 9457 en `application/problem+json`: 400 (invalid-file),
  422 (malformed-pdf), 413 (too-large), 504 (timeout), 500 (server-error).
"""

import asyncio
import hashlib
import logging

import httpx

from app.config.config import settings
from app.domain.exceptions import InvalidPDFFormatError, PDFProcessingError
from app.services.ports import IPDFProcessor

logger = logging.getLogger(__name__)

PDF_MAGIC_BYTES = b"%PDF"
EXTRACT_TIMEOUT_SECONDS = 30.0
EXTRACT_PATH = "/api/v1/extract"
UPLOAD_FIELD = "file"
UPLOAD_FILENAME = "document.pdf"
UPLOAD_MEDIA_TYPE = "application/pdf"


def compute_checksum(file_bytes: bytes) -> str:
    """Calcula el hash SHA-256 de los bytes dados para evitar duplicados en BD."""
    return hashlib.sha256(file_bytes).hexdigest()


def validate_pdf_format(file_bytes: bytes) -> None:
    """
    Comprueba los magic bytes del PDF.

    La validación estructural la hace el microservicio al recibir el documento;
    acá sólo se descarta temprano lo que claramente no es un PDF (sin round trip).
    """
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        raise InvalidPDFFormatError("El archivo no es un PDF válido.")


class RemotePdfProcessor(IPDFProcessor):
    """Implementa `IPDFProcessor` extrayendo el texto vía el microservicio."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.PDF_EXTRACT_SERVICE_URL).rstrip("/")

    async def validate_format(self, file_bytes: bytes) -> None:
        await asyncio.to_thread(validate_pdf_format, file_bytes)

    async def compute_checksum(self, file_bytes: bytes) -> str:
        return await asyncio.to_thread(compute_checksum, file_bytes)

    async def extract_text(self, file_bytes: bytes) -> str:
        files = {UPLOAD_FIELD: (UPLOAD_FILENAME, file_bytes, UPLOAD_MEDIA_TYPE)}
        async with httpx.AsyncClient(timeout=EXTRACT_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(f"{self._base_url}{EXTRACT_PATH}", files=files)
                response.raise_for_status()
            except httpx.RequestError as exc:
                logger.exception("No se pudo alcanzar el microservicio de extracción")
                raise PDFProcessingError(
                    f"Microservicio de extracción no disponible: {exc}"
                ) from exc
            except httpx.HTTPStatusError as exc:
                logger.exception(
                    "El microservicio de extracción respondió %s: %s",
                    exc.response.status_code,
                    exc.response.text,
                )
                # 400 (invalid-file) y 422 (malformed-pdf) → documento inválido.
                if exc.response.status_code in (400, 422):
                    raise InvalidPDFFormatError(
                        "El documento no es un PDF válido o está corrupto."
                    ) from exc
                raise PDFProcessingError(
                    f"El microservicio de extracción falló (HTTP {exc.response.status_code})."
                ) from exc
        return response.json()["text"]