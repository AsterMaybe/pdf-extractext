"""
Controlador de fallback para errores generados por infraestructura (Traefik).

Traefik intercepta los errores de Rate Limiting (429) y Circuit Breaker (503)
y los delega a estas rutas a través del middleware `errors`, de modo que la
respuesta cumpla RFC 9457 en lugar del texto plano por defecto.
"""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.problems import build_problem_response

router = APIRouter()


@router.get("/traefik/errors/429", response_class=JSONResponse, summary="Respuesta RFC 9457 para Rate Limit de Traefik")
async def traefik_rate_limited(request: Request) -> JSONResponse:
    """Devuelve el error estándar de rate limiting (429) cuando Traefik lo detecta."""
    return build_problem_response(
        request,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Se ha excedido el límite de peticiones permitidas. Intente nuevamente más tarde.",
    )


@router.get("/traefik/errors/503", response_class=JSONResponse, summary="Respuesta RFC 9457 para Circuit Breaker de Traefik")
async def traefik_service_unavailable(request: Request) -> JSONResponse:
    """Devuelve el error estándar de servicio no disponible (503) cuando el Circuit Breaker se abre."""
    return build_problem_response(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="El servicio no se encuentra disponible en este momento. Intente nuevamente más tarde.",
    )