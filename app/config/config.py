"""
Configuración centralizada de la aplicación.
Pydantic-Settings valida y tipea cada variable automáticamente.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Aplicación ---
    APP_NAME: str = "pdf-extractext"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- MongoDB ---
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "pdf_extractext"
    MONGODB_COLLECTION: str = "documents"

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 10  # Tamaño máximo permitido en MB

    class Config:
        # Permite leer desde un archivo .env si existe
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instancia única reutilizada en toda la app (patrón Singleton implícito).
# Importar siempre desde acá: `from app.config import settings`
settings = Settings()
