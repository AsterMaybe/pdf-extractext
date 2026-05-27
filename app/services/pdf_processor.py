import hashlib
import fitz

from fastapi import HTTPException, UploadFile, status
from app.config.config import settings

# ── Constantes ──────────────────────────────────────────────────────────────

PDF_MAGIC_BYTES = b"%PDF"
MAX_SIZE_BYTES = settings.PDF_MAX_SIZE_MB * 1024 * 1024


# ── Funciones públicas ───────────────────────────────────────────────────────

def compute_checksum(file_bytes: bytes) -> str:
    """
    Calcula el hash SHA-256 de los bytes dados para evitar duplicados en BD.
    """
    return hashlib.sha256(file_bytes).hexdigest()


def validate_pdf(file_bytes: bytes, filename: str) -> None:
    """
    Valida formato y tamaño del archivo sin persistirlo en disco.

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

    # Validación de formato rápida por magic bytes
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es un PDF válido.",
        )

    # Validación estructural: confirmamos que PyMuPDF puede leerlo
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        doc.close()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF está corrupto o no se puede procesar.",
        )


async def read_upload_bytes(upload: UploadFile) -> bytes:
    """
    Lee todos los bytes de un UploadFile de FastAPI en memoria.
    """
    return await upload.read()