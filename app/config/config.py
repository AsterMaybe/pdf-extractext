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
    # URL interna del microservicio Go de extracción. En la red compartida
    # resuelve tanto por el nombre del contenedor (microservicio-go-api-1)
    # como por el alias de servicio (`api`). docker-compose.app.yml la
    # sobreescribe vía env; este default es el fallback local.
    PDF_EXTRACT_SERVICE_URL: str = "http://microservicio-go-api-1:8080"

    # --- MongoDB ---
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    MONGODB_COLLECTION: str
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 15  # Default por si no hay .env
    UPLOAD_CHUNK_SIZE_MB: int = 1

    # Configuración para Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()  # type: ignore