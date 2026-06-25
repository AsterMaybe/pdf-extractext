import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config.mongodb import mongodb

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health", summary="Verifica el estado del sistema", response_class=JSONResponse)
async def health_check():
    """
    Realiza un chequeo de salud profundo, verificando tanto
    la aplicación HTTP como la conexión a la base de datos MongoDB.
    """
    app_status = "ok"
    db_status = "error"
    overall_status = "error"
    http_status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    try:
        if mongodb.client is not None:
            await mongodb.client.admin.command("ping")
            db_status = "ok"
            overall_status = "ok"
            http_status_code = status.HTTP_200_OK
        else:
            logger.error("Health check falló: El cliente de MongoDB no está inicializado.")
    except Exception as e:
        logger.error(f"Health check falló al hacer ping a MongoDB: {str(e)}")

    payload = {
        "status": overall_status,
        "app": app_status,
        "database": db_status
    }

    return JSONResponse(status_code=http_status_code, content=payload)