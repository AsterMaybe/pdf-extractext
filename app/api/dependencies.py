"""
Composición de dependencias (DIP).

Toda dependencia de infraestructura (microservicios HTTP, repositorios,
adaptadores) se resuelve vía `Depends` y se expone al consumidor como
abstracción (puerto), nunca como clase concreta.
"""

import logging
import httpx
from fastapi import Depends, Request

from app.config.config import settings
from app.consul.config_watcher import ConfigWatcher
from app.consul.discovery import ServiceDiscovery
from app.infrastructure.remote_pdf_processor import RemotePdfProcessor
from app.repositories.http_document_repo import HttpDocumentRepository
from app.repositories.http_health_repo import HttpHealthRepository
from app.services.document_service import DocumentService
from app.services.health_service import HealthService
from app.services.ports import IDocumentRepository, IHealthRepository, IPDFProcessor


def _get_http_client(request: Request) -> httpx.AsyncClient:
    """Devuelve el cliente HTTP compartido, gestionado por el lifespan."""
    return request.app.state.db_service_http_client


def _get_discovery(request: Request) -> ServiceDiscovery:
    """Retorna la instancia de ServiceDiscovery del lifespan."""
    return request.app.state.service_discovery


def _get_config_watcher(request: Request) -> ConfigWatcher:
    """Retorna la instancia de ConfigWatcher del lifespan."""
    return request.app.state.config_watcher


def _get_db_timeout(request: Request) -> float:
    """Get DB service timeout with Consul KV fallback."""
    watcher = _get_config_watcher(request)
    return watcher.get_float("DB_SERVICE_TIMEOUT_SECONDS", "DB_SERVICE_TIMEOUT_SECONDS", settings.DB_SERVICE_TIMEOUT_SECONDS)


def _get_pdf_max_size_mb(request: Request) -> int:
    """Get PDF max size with Consul KV fallback."""
    watcher = _get_config_watcher(request)
    return watcher.get_int("PDF_MAX_SIZE_MB", "PDF_MAX_SIZE_MB", settings.PDF_MAX_SIZE_MB)


def _get_error_base_url(request: Request) -> str:
    """Get error base URL with Consul KV fallback."""
    watcher = _get_config_watcher(request)
    return watcher.get_string("ERROR_BASE_URL", "ERROR_BASE_URL", settings.ERROR_BASE_URL)


async def get_document_repo(request: Request) -> IDocumentRepository:
    """Retorna el adaptador HTTP del microservicio Go de persistencia."""
    discovery = _get_discovery(request)
    # Resolve service URL via Consul discovery, fallback to config
    try:
        base_url = await discovery.resolve_service_url("microservicio-db")
    except Exception as e:
        # Log warning and fallback to config
        logger = logging.getLogger(__name__)
        logger.warning(f"Service discovery failed for microservicio-db, using fallback: {e}")
        base_url = settings.DB_SERVICE_URL
    
    return HttpDocumentRepository(
        base_url=base_url,
        timeout=_get_db_timeout(request),
        client=_get_http_client(request),
    )


async def get_pdf_processor(request: Request) -> IPDFProcessor:
    """Instancia única del adaptador de PDF, expuesto como abstracción (DIP)."""
    discovery = _get_discovery(request)
    # Resolve service URL via Consul discovery, fallback to config
    try:
        base_url = await discovery.resolve_service_url("microservicio-go")
    except Exception as e:
        # Log warning and fallback to config
        logger = logging.getLogger(__name__)
        logger.warning(f"Service discovery failed for microservicio-go, using fallback: {e}")
        base_url = settings.PDF_EXTRACT_SERVICE_URL
    
    return RemotePdfProcessor(
        base_url=base_url,
        max_file_size_mb=_get_pdf_max_size_mb(request),
    )


def get_document_service(
    repo: IDocumentRepository = Depends(get_document_repo),
    pdf_processor: IPDFProcessor = Depends(get_pdf_processor),
) -> DocumentService:
    return DocumentService(repo, pdf_processor)


async def get_health_repo(request: Request) -> IHealthRepository:
    """Retorna el adaptador HTTP para el health check del microservicio Go."""
    discovery = _get_discovery(request)
    try:
        base_url = await discovery.resolve_service_url("microservicio-db")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Service discovery failed for microservicio-db, using fallback: {e}")
        base_url = settings.DB_SERVICE_URL
    
    return HttpHealthRepository(
        base_url=base_url,
        timeout=_get_db_timeout(request),
        client=_get_http_client(request),
    )


def get_health_service(
    health_repo: IHealthRepository = Depends(get_health_repo),
) -> HealthService:
    return HealthService(health_repo)