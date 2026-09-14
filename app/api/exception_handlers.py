"""
Handlers de error consolidados (RFC 9457).

Cada handler resuelve un único trabajo (construir una respuesta ProblemDetail)
y el registro de estados permite extender el comportamiento sin modificar los
handlers existentes (Open/Closed Principle): para sumar un error de dominio,
basta con agregar su tipo al mapa `HTTP_STATUS_BY_EXCEPTION`.
"""

import http
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    FileSizeExceededError,
    InvalidPDFFormatError,
)
from app.domain.problem_detail import ProblemDetail

logger = logging.getLogger(__name__)

# ── Registro de estados por excepción de dominio (punto único de extensión) ──

HTTP_STATUS_BY_EXCEPTION: dict[type[Exception], int] = {
    DocumentNotFoundError: status.HTTP_404_NOT_FOUND,
    FileSizeExceededError: status.HTTP_400_BAD_REQUEST,
    InvalidPDFFormatError: status.HTTP_400_BAD_REQUEST,
    DocumentAlreadyExistsError: status.HTTP_409_CONFLICT,
}

# ── Construcción de respuesta ────────────────────────────────────────────────

def _problem_response(
    request: Request,
    status_code: int,
    detail: str,
    title: str | None = None,
    errors: list | None = None,
) -> JSONResponse:
    """Construye una respuesta RFC 9457 a partir de un request y el detalle."""
    problem = ProblemDetail(
        title=title or http.HTTPStatus(status_code).phrase,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )

# ── Handlers ─────────────────────────────────────────────────────────────────

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Errores HTTP estándar de Starlette/FastAPI (ej. 404, 405)."""
    return _problem_response(request, status_code=exc.status_code, detail=str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Errores de validación de parámetros/cuerpo (422)."""
    return _problem_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="La petición contiene datos inválidos o incompletos.",
        errors=exc.errors(),
    )


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Errores de dominio: el código HTTP sale del registro (OCP)."""
    status_code = HTTP_STATUS_BY_EXCEPTION.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return _problem_response(request, status_code=status_code, detail=str(exc))


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Cualquier error 500 no controlado, sin filtrar detalles internos."""
    logger.exception("Error interno del servidor no controlado")
    return _problem_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Ha ocurrido un error inesperado en el servidor. Por favor, intente más tarde.",
    )


# ── Registro en la aplicación ────────────────────────────────────────────────

def install_exception_handlers(app: FastAPI) -> None:
    """Registra todos los handlers RFC 9457 sobre una instancia de FastAPI."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    for exception_type in HTTP_STATUS_BY_EXCEPTION:
        app.add_exception_handler(exception_type, domain_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)