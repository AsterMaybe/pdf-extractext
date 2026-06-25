import http
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.logging_config import setup_logging
from app.config.mongodb import mongodb
from app.controllers import document_controller, health_controller

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Application startup: connecting to MongoDB...")
    await mongodb.connect()
    yield
    logger.info("Application shutdown: disconnecting from MongoDB...")
    mongodb.disconnect()

app = FastAPI(
    title="PDF ExtracText API",
    version="0.1.0",
    description="API para procesar y extraer texto de documentos PDF.",
    lifespan=lifespan,
)

@app.exception_handler(StarletteHTTPException)
async def rfc9457_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Convierte los errores HTTP estándar (ej. 404, 409) al formato RFC 9457"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": http.HTTPStatus(exc.status_code).phrase,
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": str(request.url.path)
        },
        media_type="application/problem+json"
    )

@app.exception_handler(RequestValidationError)
async def rfc9457_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convierte los errores de validación (ej. falta un campo o archivo) al formato RFC 9457"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "type": "about:blank",
            "title": "Unprocessable Entity",
            "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": "La petición contiene datos inválidos o incompletos.",
            "errors": exc.errors(),
            "instance": str(request.url.path)
        },
        media_type="application/problem+json"
    )


@app.exception_handler(Exception)
async def rfc9457_global_exception_handler(request: Request, exc: Exception):
    """Atrapa cualquier error 500 no controlado y lo devuelve en formato RFC 9457 para evitar fugas de información"""
    logger.exception("Error interno del servidor no controlado")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "type": "about:blank",
            "title": "Internal Server Error",
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": "Ha ocurrido un error inesperado en el servidor. Por favor, intente más tarde.",
            "instance": str(request.url.path)
        },
        media_type="application/problem+json"
    )


app.include_router(
    health_controller.router,
    tags=["System"]
)

app.include_router(
    document_controller.router,
    prefix="/api/v1/documents",
    tags=["Documents"]
)