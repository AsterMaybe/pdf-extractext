"""
Modelos de datos de la aplicación.
"""
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    """
    Datos necesarios para persistir un nuevo documento.
    """
    filename: str = Field(..., description="Nombre original del archivo PDF.")
    text_content: str = Field(..., description="Texto extraído del PDF.")
    checksum: str = Field(..., description="SHA-256 del archivo original.")
    file_size_bytes: int = Field(..., description="Tamaño del archivo en bytes.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fecha/hora de creación en UTC.",
    )


class DocumentResponse(BaseModel):
    """
    Representación pública de un documento (lo que ve el cliente).
    """
    id: str = Field(..., description="Identificador único en la base de datos.")
    filename: str
    text_content: str
    checksum: str
    file_size_bytes: int
    created_at: datetime


class DocumentUpdate(BaseModel):
    """
    Campos actualizables de un documento.
    Todos son opcionales: el cliente sólo manda lo que quiere cambiar (PATCH semántico).
    """
    filename: str | None = None
    text_content: str | None = None
