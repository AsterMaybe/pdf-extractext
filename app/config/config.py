"""
Configuración centralizada de la aplicación.
Pydantic-Settings valida y tipea cada variable automáticamente.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Aplicación ---
    APP_NAME: str = "pdf-extractext"
    APP_VERSION: str = "0.4.0"
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
    # Servicios internos accesibles por la red compartida.
    PDF_EXTRACT_SERVICE_URL: str = "http://api:8080"
    DOCUMENT_GATEWAY_URL: str = "http://microservicio-io:8080"
    DB_SERVICE_URL: str = "http://microservicio-db-go:8080"

    # --- MongoDB ---
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "pdf_db"
    MONGODB_COLLECTION: str = "extracted_texts"
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 15  # Default por si no hay .env
    UPLOAD_CHUNK_SIZE_MB: int = 1

    # Timeout en segundos para requests al microservicio DB Go.
    DB_SERVICE_TIMEOUT_SECONDS: float = 10.0

    # Configuración para Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()  # type: ignore