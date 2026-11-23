"""
Configuración centralizada de la aplicación.
Pydantic-Settings valida y tipea cada variable automáticamente.
"""
import os
from typing import Any, Dict, Optional

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
    # Incluye 'monolitico' para Consul health checks.
    ALLOWED_HOSTS: list[str] = ["api.localhost", "localhost", "127.0.0.1", "testserver", "monolitico", "monolitico.localhost"]

    # --- Network ---
    SHARED_NETWORK_NAME: str = "test_network"
    # Servicios internos - resueltos vía Consul Service Discovery.
    # Se usan como fallback si Consul no está disponible.
    # Defaults vacíos: se espera que Consul Discovery los resuelva en runtime.
    PDF_EXTRACT_SERVICE_URL: str = ""
    DB_SERVICE_URL: str = ""

    # --- Consul Service Discovery ---
    CONSUL_HTTP_ADDR: str = "consul:8500"
    CONSUL_HTTP_TOKEN: str = ""
    CONSUL_DNS_PORT: int = 8600
    CONSUL_DISCOVERY_CACHE_TTL: int = 30

    # --- Consul KV Config ---
    # Prefijo en Consul KV para configuración centralizada (ej: config/monolitico/)
    CONSUL_CONFIG_PREFIX: str = "config/monolitico/"

    # --- Validación de PDF ---
    PDF_MAX_SIZE_MB: int = 25  # Default por si no hay .env
    UPLOAD_CHUNK_SIZE_MB: int = 1

    # --- RFC 9457 ---
    # Base de las URIs `type` de los errores (mismo esquema que los Go).
    ERROR_BASE_URL: str = "https://errors.example.com"

    # Timeout en segundos para requests al microservicio DB Go.
    DB_SERVICE_TIMEOUT_SECONDS: float = 10.0

    # Configuración para Pydantic
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    def get_with_consul_fallback(self, key: str, consul_key: str, consul_config: Optional[Dict[str, str]] = None) -> Any:
        """
        Get a setting value with Consul KV fallback.
        
        Priority: Consul KV > environment variable > Pydantic default.
        
        Args:
            key: The Settings attribute name (e.g., "PDF_MAX_SIZE_MB")
            consul_key: The key in Consul KV (e.g., "PDF_MAX_SIZE_MB")
            consul_config: Optional dict of Consul KV values (from ConfigWatcher)
        """
        # 1. Check Consul KV first
        if consul_config and consul_key in consul_config and consul_config[consul_key]:
            val = consul_config[consul_key]
            # Try to convert to the field's type
            field_type = self.__annotations__.get(key)
            if field_type == int:
                return int(val)
            elif field_type == float:
                return float(val)
            elif field_type == bool:
                return val.lower() in ("true", "1", "yes", "on")
            return val
        
        # 2. Check environment variable (pydantic-settings handles this via model_config)
        env_val = os.getenv(key)
        if env_val is not None:
            field_type = self.__annotations__.get(key)
            if field_type == int:
                return int(env_val)
            elif field_type == float:
                return float(env_val)
            elif field_type == bool:
                return env_val.lower() in ("true", "1", "yes", "on")
            return env_val
        
        # 3. Return the default from settings
        return getattr(self, key)


settings = Settings()  # type: ignore