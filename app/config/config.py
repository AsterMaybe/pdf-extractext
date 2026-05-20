"""
Configuración centralizada de la aplicación.
Pydantic-Settings valida y tipea cada variable automáticamente.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Aplicación ---
    # Es válido dejar defaults para variables no sensibles de la app
    APP_NAME: str = "pdf-extractext"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- MongoDB ---
    # Sin valor por defecto. Si faltan en el .env o en el entorno, la app no arranca.
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    MONGODB_COLLECTION: str

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 10  # Está bien dejar un default razonable para reglas de negocio

    # Configuración para Pydantic V2
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Instancia única reutilizada en toda la app (patrón Singleton implícito).
# Importar siempre desde acá: `from app.config.config import settings`
settings = Settings()