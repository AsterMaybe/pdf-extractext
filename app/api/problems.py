"""
Constructor único de respuestas de error RFC 9457 (Problem Details for HTTP APIs).

Es la única fuente de verdad para serializar errores: todos los handlers y
rutas de fallback usan `build_problem_response` en lugar de armar payloads a
mano (DRY + Single Responsibility).
"""

import http

from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.problem_detail import ProblemDetail


def build_problem_response(
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
        instance=str(request.url),
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )