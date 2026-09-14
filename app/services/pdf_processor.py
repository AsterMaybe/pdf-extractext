import hashlib
import fitz
from fastapi import UploadFile
from app.config.config import settings
from app.domain.exceptions import FileSizeExceededError, InvalidPDFFormatError

# ── Constantes ──────────────────────────────────────────────────────────────

PDF_MAGIC_BYTES = b"%PDF"


# ── Funciones públicas ───────────────────────────────────────────────────────

def compute_checksum(file_bytes: bytes) -> str:
    """Calcula el hash SHA-256 de los bytes dados para evitar duplicados en BD."""
    return hashlib.sha256(file_bytes).hexdigest()


async def read_and_validate_size(upload: UploadFile) -> bytes:
    """
    Lee el archivo en bloques (chunks) para evitar colapsar la RAM.
    """
    content = bytearray()
    chunk_size = 1024 * 1024  # Leer de a 1 MB por iteración

    while chunk := await upload.read(chunk_size):
        content.extend(chunk)

    return bytes(content)


def validate_file_size(file_bytes: bytes) -> None:
    max_size_bytes = settings.PDF_MAX_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_size_bytes:
        raise FileSizeExceededError(settings.PDF_MAX_SIZE_MB)


def validate_pdf_format(file_bytes: bytes) -> None:
    """
    Valida únicamente el formato del archivo.
    (El tamaño ya fue validado en la etapa de lectura).
    """
    # Validación de formato rápida por magic bytes
    if not file_bytes.startswith(PDF_MAGIC_BYTES):
        raise InvalidPDFFormatError("El archivo no es un PDF válido.")

    # Validación estructural: confirmamos que PyMuPDF puede leerlo
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        doc.close()
    except Exception:
        raise InvalidPDFFormatError("El PDF está corrupto o no se puede procesar.")
