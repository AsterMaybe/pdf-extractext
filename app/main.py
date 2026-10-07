import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.exception_handlers import install_exception_handlers
from app.config.config import settings
from app.config.logging_config import setup_logging
from app.controllers import document_controller, health_controller, traefik_error_controller

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: configuring DB service client...")
    app.state.db_service_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.DB_SERVICE_TIMEOUT_SECONDS),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    try:
        yield
    finally:
        logger.info("Application shutdown: closing DB service client...")
        await app.state.db_service_http_client.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API para procesar y extraer texto de documentos PDF.",
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RFC 9457: todos los handlers de error se registran centralizadamente.
install_exception_handlers(app)

app.include_router(health_controller.router, tags=["System"])

app.include_router(
    document_controller.router,
    prefix="/api/v1/documents",
    tags=["Documents"],
)

# Fallback de errores de infraestructura (Traefik) en RFC 9457.
app.include_router(traefik_error_controller.router, tags=["Infrastructure"])