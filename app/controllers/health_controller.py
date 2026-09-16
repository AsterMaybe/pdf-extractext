import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_health_service
from app.api.problems import build_problem_response
from app.services.health_service import HealthService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health/live", summary="Verifica que la aplicación esté viva", response_class=JSONResponse)
async def health_live() -> JSONResponse:
    """
    Liveness para balanceadores/reverse proxies (Traefik).
    Solo comprueba que el proceso responde; no toca la base de datos.
    """
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})


@router.get("/health", summary="Verifica el estado del sistema", response_class=JSONResponse)
async def health_check(
    request: Request,
    service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """
    Realiza un chequeo de salud profundo, verificando tanto
    la aplicación HTTP como la conexión a la base de datos MongoDB.
    """
    if await service.database_is_healthy():
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "app": "ok", "database": "ok"},
        )
    return build_problem_response(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="La base de datos no está disponible.",
    )