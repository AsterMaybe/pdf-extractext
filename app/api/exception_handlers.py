"""
Handlers de error consolidados (RFC 9457).

Existe un único handler para la jerarquía de `DomainError` (LSP-safe: las
subclases se resuelven por el `code` que cargan, no por tipo exacto) y un
registro `HTTP_STATUS_BY_CODE` como punto único de extensión (OCP).
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.problems import build_problem_response
from app.domain.exceptions import (
    DomainError,
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    FileSizeExceededError,
    InvalidDocumentIdError,
    InvalidPDFFormatError,
    PDFProcessingError,
)

logger = logging.getLogger(__name__)

# ── Registro de estados por código de error de dominio (punto único de extensión) ──

HTTP_STATUS_BY_CODE: dict[str, int] = {
    DocumentNotFoundError.code: status.HTTP_404_NOT_FOUND,
    InvalidDocumentIdError.code: status.HTTP_400_BAD_REQUEST,
    FileSizeExceededError.code: status.HTTP_400_BAD_REQUEST,
    InvalidPDFFormatError.code: status.HTTP_400_BAD_REQUEST,
    PDFProcessingError.code: status.HTTP_422_UNPROCESSABLE_CONTENT,
    DocumentAlreadyExistsError.code: status.HTTP_409_CONFLICT,
}


# ── Handlers ───────────────────────────────────────────────────────────────────

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Errores HTTP estándar de Starlette/FastAPI (ej. 404, 405)."""
    return build_problem_response(request, status_code=exc.status_code, detail=str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Errores de validación de parámetros/cuerpo (422)."""
    errors = [
        {"type": e.get("type"), "loc": e.get("loc"), "msg": e.get("msg")}
        for e in exc.errors()
    ]
    return build_problem_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="La petición contiene datos inválidos o incompletos.",
        errors=errors,
    )


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Errores de dominio: el código HTTP sale del registro por `code` (OCP + LSP).

    El handler está registrado exclusivamente para la jerarquía de `DomainError`,
    por lo que el parámetro tipo el contrato de dominio sin adivinanzas.
    """
    status_code = HTTP_STATUS_BY_CODE.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    return build_problem_response(request, status_code=status_code, detail=str(exc))


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Cualquier error 500 no controlado, sin filtrar detalles internos."""
    logger.exception("Error interno del servidor no controlado")
    return build_problem_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Ha ocurrido un error inesperado en el servidor. Por favor, intente más tarde.",
    )


# ── Registro en la aplicación ──────────────────────────────────────────────────

def install_exception_handlers(app: FastAPI) -> None:
    """Registra todos los handlers RFC 9457 sobre una instancia de FastAPI."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)