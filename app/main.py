from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.config import settings
# Importamos la instancia global desde tu archivo config/mongodb.py
from app.config.mongodb import mongodb
from app.controllers.document_controller import router as document_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Maneja el ciclo de vida de la aplicación.
    Garantiza que la base de datos esté lista antes de recibir peticiones.
    """
    # 1. Startup: Inicializar el pool de conexiones de Motor
    mongodb.connect()
    yield
    # 2. Shutdown: Liberar los recursos del cliente
    mongodb.disconnect()


app = FastAPI(
    title="PDF Extractor API",
    description="API para validación, extracción y persistencia de texto desde PDFs.",
    version="0.1.0",
    lifespan=lifespan
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modificar mediante settings en entornos de producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro de controladores organizados por versión
app.include_router(document_router, prefix="/api/v1/documents", tags=["Documents"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de control de estado para monitoreo."""
    return {
        "status": "ok",
        "message": "API operativa y ciclo de vida de la base de datos configurado."
    }