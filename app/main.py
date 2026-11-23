import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.exception_handlers import install_exception_handlers
from app.config.config import settings
from app.config.logging_config import setup_logging
from app.consul.config_watcher import ConfigWatcher, ConfigWatcherConfig
from app.consul.discovery import DiscoveryConfig, discovery_lifespan
from app.consul.registration import ConsulConfig, consul_lifespan
from app.controllers import document_controller, health_controller, traefik_error_controller

setup_logging()
logger = logging.getLogger(__name__)


def _build_consul_config() -> ConsulConfig:
    """Build Consul configuration from environment and settings."""
    return ConsulConfig(
        service_name=os.getenv("CONSUL_SERVICE_NAME", "monolitico"),
        service_port=int(os.getenv("CONSUL_SERVICE_PORT", "8000")),
        health_path=os.getenv("CONSUL_HEALTH_PATH", "/health"),
        consul_address=os.getenv("CONSUL_HTTP_ADDR", "consul:8500"),
        consul_token=os.getenv("CONSUL_HTTP_TOKEN"),
        # Let Traefik create default router via Consul Catalog provider
        # Default router will be: Host(`monolitico`)
        # NOTE: "consul-registered" is added in registration.py _build_tags() - don't duplicate here
        tags=[],
        meta={},
    )


def _build_discovery_config() -> DiscoveryConfig:
    """Build Service Discovery configuration from environment and settings."""
    return DiscoveryConfig(
        consul_address=os.getenv("CONSUL_HTTP_ADDR", "consul:8500"),
        consul_token=os.getenv("CONSUL_HTTP_TOKEN"),
        dns_port=int(os.getenv("CONSUL_DNS_PORT", "8600")),
        cache_ttl_seconds=int(os.getenv("CONSUL_DISCOVERY_CACHE_TTL", "30")),
        # Disable Connect sidecar resolution: monolitico only has inbound sidecar (Envoy)
        # for receiving mTLS, not outbound for making mTLS calls.
        # Use direct Catalog API resolution instead.
        use_connect_sidecar=os.getenv("CONSUL_USE_CONNECT_SIDECAR", "false").lower() == "true",
    )


def _build_config_watcher_config() -> ConfigWatcherConfig:
    """Build Config Watcher configuration from environment and settings."""
    return ConfigWatcherConfig(
        consul_address=os.getenv("CONSUL_HTTP_ADDR", "consul:8500"),
        consul_token=os.getenv("CONSUL_HTTP_TOKEN"),
        prefix=settings.CONSUL_CONFIG_PREFIX,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Consul registration lifecycle
    consul_config = _build_consul_config()
    discovery_config = _build_discovery_config()
    config_watcher_config = _build_config_watcher_config()
    
    # Start config watcher (optional - continues without Consul if unavailable)
    config_watcher = ConfigWatcher(config_watcher_config)
    config_watcher.start()
    
    async with consul_lifespan(consul_config) as registrar:
        async with discovery_lifespan(discovery_config) as discovery:
            logger.info("Application startup: configuring DB service client...")
            app.state.db_service_http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.DB_SERVICE_TIMEOUT_SECONDS),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
            # Store registrar for potential health checks
            app.state.consul_registrar = registrar
            # Store discovery for service resolution
            app.state.service_discovery = discovery
            # Store config watcher for hot-reload
            app.state.config_watcher = config_watcher
            try:
                yield
            finally:
                logger.info("Application shutdown: closing DB service client...")
                await app.state.db_service_http_client.aclose()
                config_watcher.stop()


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