import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.exception_handlers import install_exception_handlers
from app.config.config import settings
from app.config.logging_config import setup_logging
from app.config.mongodb import MongoDB
from app.controllers import document_controller, health_controller, traefik_error_controller
from app.repositories.document_repo import DocumentRepository

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = MongoDB()
    logger.info("Application startup: connecting to MongoDB...")
    try:
        await db.connect(settings.MONGODB_URL, settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS)
        document_repo = DocumentRepository(
            db.get_collection(settings.MONGODB_DB_NAME, settings.MONGODB_COLLECTION)
        )
        await document_repo.ensure_indexes()
    except Exception:
        await db.disconnect()
        raise
    _app.state.mongodb = db
    try:
        yield
    finally:
        logger.info("Application shutdown: disconnecting from MongoDB...")
        await db.disconnect()


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