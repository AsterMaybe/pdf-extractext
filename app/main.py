import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.logging_config import setup_logging
from app.config.mongodb import mongodb
from app.controllers.document_controller import router as document_router

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Maneja el ciclo de vida de la aplicación.
    Garantiza que la base de datos esté lista antes de recibir peticiones.
    """
    logger.info("Starting up: connecting to MongoDB...")
    mongodb.connect()
    logger.info("MongoDB connected.")

    yield

    logger.info("Shutting down: disconnecting MongoDB...")
    mongodb.disconnect()
    logger.info("MongoDB disconnected.")


app = FastAPI(
    title="PDF Extractor API",
    description="API para validación, extracción y persistencia de texto desde PDFs.",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,  # type: ignore
    allow_origins=["*"],  # Modificar mediante settings en entornos de producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router, prefix="/api/v1/documents", tags=["Documents"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de control de estado para monitoreo."""
    return {
        "status": "ok",
        "message": "API operativa y ciclo de vida de la base de datos configurado."
    }

logger.info("API inicializada con éxito. Listo para recibir peticiones.")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Captura todas las excepciones no controladas globalmente.
    Registra el rastreo completo del error y devuelve un error genérico 500 al cliente.
    """
    logger.exception(f"Unhandled server error occurred while processing {request.method} {request.url.path}")

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error. Please try again later."},
    )