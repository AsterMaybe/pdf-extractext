import hashlib
import io

import pymupdf4llm
import fitz

from fastapi import HTTPException, UploadFile, status

from app.config.config import settings


# ── Constantes ──────────────────────────────────────────────────────────────

PDF_MAGIC_BYTES = b"%PDF"
MAX_SIZE_BYTES = settings.PDF_MAX_SIZE_MB * 1024 * 1024


# ── Funciones públicas ───────────────────────────────────────────────────────

def compute_checksum(file_bytes: bytes) -> str:
    """
    Calcula el hash SHA-256 de los bytes dados.

    Args:
        file_bytes: Contenido binario del archivo.

    Returns:
        String hexadecimal de 64 caracteres.
    """
    return hashlib.sha256(file_bytes).hexdigest()


def validate_pdf(file_bytes: bytes, filename: str) -> None:
    """
    Valida formato y tamaño del archivo.

    Raises:
        HTTPException 400 si el archivo no es PDF o es demasiado grande.
    """
    if len(file_bytes) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El archivo supera el límite permitido de "
                f"{settings.PDF_MAX_SIZE_MB} MB."
            ),
        )

    # Validación de formato por magic bytes
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es un PDF válido.",
        )

    # Validación estructural: se intenta abrir con PyMuPDF
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        doc.close()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF está corrupto o no se puede procesar.",
        )


def extract_text(file_bytes: bytes) -> str:
    """
    Extrae el texto de un PDF en memoria usando pymupdf4llm.

    Args:
        file_bytes: Bytes del PDF ya validado.

    Returns:
        Texto extraído como string. Puede ser vacío si el PDF no tiene texto.

    Raises:
        HTTPException 422 si la extracción falla inesperadamente.
    """
    try:
        # pymupdf4llm.to_markdown acepta un objeto de documento fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if doc.page_count == 0:
            doc.close()
            return ""
        text = pymupdf4llm.to_markdown(doc)
        doc.close()
        return text.strip()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se pudo extraer el texto del PDF: {exc}",
        )


async def read_upload_bytes(upload: UploadFile) -> bytes:
    """
    Lee todos los bytes de un UploadFile de FastAPI en memoria.

    Args:
        upload: Archivo recibido por el endpoint.

    Returns:
        Contenido binario completo del archivo.
    """
    return await upload.read()