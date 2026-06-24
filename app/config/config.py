"""
Configuración centralizada de la aplicación.
Pydantic-Settings valida y tipea cada variable automáticamente.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Aplicación ---
    APP_NAME: str = "pdf-extractext"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- CORS ---
    # Override this in production!
    CORS_ORIGINS: list[str] = ["*"]

    # --- MongoDB ---
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    MONGODB_COLLECTION: str

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 5  # Default por si no hay .env

    # Configuración para Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )



settings = Settings()  # type: ignore