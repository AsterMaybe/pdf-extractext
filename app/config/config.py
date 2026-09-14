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
    LOG_LEVEL: str = "INFO"

    # --- CORS ---
    # Override this in production!
    CORS_ORIGINS: list[str] = ["*"]

    # --- Security ---
    # Hosts allowed to reach the API (trusted host middleware).
    # Incluye el host del router de Traefik (api.localhost) para esta fase.
    ALLOWED_HOSTS: list[str] = ["api.localhost", "localhost", "127.0.0.1", "testserver"]

    # --- Network ---
    SHARED_NETWORK_NAME: str = "test_network"

    # --- MongoDB ---
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    MONGODB_COLLECTION: str
    MONGODB_USER: str = ""
    MONGODB_PASSWORD: str = ""

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 5  # Default por si no hay .env

    # Configuración para Pydantic
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()  # type: ignore