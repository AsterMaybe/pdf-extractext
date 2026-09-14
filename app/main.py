import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.exception_handlers import install_exception_handlers
from app.config.logging_config import setup_logging
from app.config.mongodb import mongodb
from app.config.config import settings
from app.controllers import document_controller, health_controller

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Application startup: connecting to MongoDB...")
    await mongodb.connect()
    yield
    logger.info("Application shutdown: disconnecting from MongoDB...")
    await mongodb.disconnect()

app = FastAPI(
    title="PDF ExtracText API",
    version="0.1.0",
    description="API para procesar y extraer texto de documentos PDF.",
    lifespan=lifespan,
)

# Add TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# RFC 9457: todos los handlers de error se registran centralizadamente.
install_exception_handlers(app)

app.include_router(
    health_controller.router,
    tags=["System"]
)

app.include_router(
    document_controller.router,
    prefix="/api/v1/documents",
    tags=["Documents"]
)