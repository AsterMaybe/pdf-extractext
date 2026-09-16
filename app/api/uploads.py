"""
Adaptador de entrada HTTP (capa de presentación): convierten `UploadFile` en
`bytes` sin que la capa de servicios tenga que conocer tipos de FastAPI.
"""

from fastapi import UploadFile

from app.config.config import settings
from app.domain.exceptions import FileSizeExceededError


async def read_upload_bytes(upload: UploadFile) -> bytes:
    """
    Lee la totalidad de un upload en chunks (evita ocupar RAM de golpe) y
    aborta temprano si el archivo supera el tamaño máximo configurado.
    """
    chunk_size = settings.UPLOAD_CHUNK_SIZE_MB * 1024 * 1024
    max_size = settings.PDF_MAX_SIZE_MB * 1024 * 1024

    content = bytearray()
    while chunk := await upload.read(chunk_size):
        content.extend(chunk)
        if len(content) > max_size:
            raise FileSizeExceededError(settings.PDF_MAX_SIZE_MB)
    return bytes(content)