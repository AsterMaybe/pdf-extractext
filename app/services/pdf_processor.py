import hashlib
import fitz
from fastapi import HTTPException, UploadFile, status
from app.config.config import settings

# ── Constantes ──────────────────────────────────────────────────────────────

PDF_MAGIC_BYTES = b"%PDF"


# ── Funciones públicas ───────────────────────────────────────────────────────

def compute_checksum(file_bytes: bytes) -> str:
    """Calcula el hash SHA-256 de los bytes dados para evitar duplicados en BD."""
    return hashlib.sha256(file_bytes).hexdigest()


async def read_and_validate_size(upload: UploadFile) -> bytes:
    """
    Lee el archivo en bloques (chunks) para evitar colapsar la RAM.
    Valida el tamaño en tiempo real.
    """
    max_size_bytes = settings.PDF_MAX_SIZE_MB * 1024 * 1024
    content = bytearray()
    chunk_size = 1024 * 1024  # Leer de a 1 MB por iteración

    while chunk := await upload.read(chunk_size):
        content.extend(chunk)
        if len(content) > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo supera el límite permitido de {settings.PDF_MAX_SIZE_MB} MB."
            )

    return bytes(content)


def validate_pdf_format(file_bytes: bytes) -> None:
    """
    Valida únicamente el formato del archivo.
    (El tamaño ya fue validado en la etapa de lectura).
    """
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