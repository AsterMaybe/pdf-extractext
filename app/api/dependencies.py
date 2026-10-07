"""
Composición de dependencias (DIP).

Toda dependencia de infraestructura (microservicios HTTP, repositorios,
adaptadores) se resuelve vía `Depends` y se expone al consumidor como
abstracción (puerto), nunca como clase concreta.
"""

import httpx
from fastapi import Depends, Request

from app.config.config import settings
from app.infrastructure.remote_pdf_processor import (
    DocumentGatewayProcessor,
    RemotePdfProcessor,
)
from app.repositories.http_document_repo import HttpDocumentRepository
from app.repositories.http_health_repo import HttpHealthRepository
from app.services.document_service import DocumentService
from app.services.health_service import HealthService
from app.services.ports import IDocumentRepository, IHealthRepository, IPDFProcessor


def _get_http_client(request: Request) -> httpx.AsyncClient:
    """Devuelve el cliente HTTP compartido, gestionado por el lifespan."""
    return request.app.state.db_service_http_client


def get_document_repo(request: Request) -> IDocumentRepository:
    """Retorna el adaptador HTTP del microservicio Go de persistencia."""
    return HttpDocumentRepository(
        base_url=settings.DB_SERVICE_URL,
        timeout=settings.DB_SERVICE_TIMEOUT_SECONDS,
        client=_get_http_client(request),
    )


def get_pdf_processor() -> IPDFProcessor:
    """Instancia ǧnica del adaptador de PDF, expuesto como abstracciǹ (DIP)."""
    return RemotePdfProcessor()


def get_document_gateway_processor() -> IPDFProcessor:
    """Instancia ǧnica del adaptador del Document Gateway Service, expuesto como abstracciǹ (DIP).
    Se conecta al microservicio-io en el endpoint /api/v1/documents para operaciones de I/O.
    """
    return DocumentGatewayProcessor()


def get_document_service(
    repo: IDocumentRepository = Depends(get_document_repo),
    pdf_processor: IPDFProcessor = Depends(get_pdf_processor),
) -> DocumentService:
    return DocumentService(repo, pdf_processor)


def get_health_repo(request: Request) -> IHealthRepository:
    """Retorna el adaptador HTTP para el health check del microservicio Go."""
    return HttpHealthRepository(
        base_url=settings.DB_SERVICE_URL,
        timeout=settings.DB_SERVICE_TIMEOUT_SECONDS,
        client=_get_http_client(request),
    )


def get_health_service(
    health_repo: IHealthRepository = Depends(get_health_repo),
) -> HealthService:
    return HealthService(health_repo)