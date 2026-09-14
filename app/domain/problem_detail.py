"""
Modelo estandarizado de errores según RFC 9457 (Problem Details for HTTP APIs).

Es la única fuente de verdad para construir las respuestas de error de la API:
los handlers consolidados en `app.api.exception_handlers` lo usan en lugar de
construir payloads a mano (DRY + Single Responsibility).
"""

from typing import Any

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """Cuerpo estándar de una respuesta de error HTTP (RFC 9457)."""

    type: str = Field(default="about:blank", description="URI que identifica el tipo de problema.")
    title: str = Field(description="Título breve y legible del problema.")
    status: int = Field(description="Código de estado HTTP de la respuesta.")
    detail: str = Field(description="Explicación específica de este error en particular.")
    instance: str | None = Field(
        default=None,
        description="URI que identifica la ocurrencia concreta del problema.",
    )
    errors: list[Any] | None = Field(
        default=None,
        description="Detalle adicional, por ejemplo errores de validación (422).",
    )