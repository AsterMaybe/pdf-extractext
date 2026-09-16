"""
Composición de dependencias (DIP).

Toda dependencia de infraestructura (MongoDB, repositorios, adaptadores) se
resuelve acá vía `Depends` y se expone al consumidor como ABSTRACCIÓN (puerto),
nunca como clase concreta. Los tests pueden sobrescribir cualquier puerto con
`app.dependency_overrides`.
"""

from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorCollection

from app.config.config import settings
from app.config.mongodb import MongoDB
from app.infrastructure.pymupdf_processor import PyMuPDFProcessor
from app.repositories.document_repo import DocumentRepository
from app.repositories.health_repo import MongoHealthRepository
from app.services.document_service import DocumentService
from app.services.health_service import HealthService
from app.services.ports import IHealthRepository, IDocumentRepository, IPDFProcessor


def get_mongodb(request: Request) -> MongoDB:
    """Devuelve la instancia de MongoDB creada en el ciclo de vida de la app."""
    return request.app.state.mongodb


def get_document_collection(db: MongoDB = Depends(get_mongodb)) -> AsyncIOMotorCollection:
    """Expone la colección de documentos de MongoDB."""
    return db.get_collection(settings.MONGODB_DB_NAME, settings.MONGODB_COLLECTION)


def get_document_repo(
    collection: AsyncIOMotorCollection = Depends(get_document_collection),
) -> IDocumentRepository:
    return DocumentRepository(collection)


def get_pdf_processor() -> IPDFProcessor:
    """Instancia única del adaptador de PDF, expuesta como abstracción (DIP)."""
    return PyMuPDFProcessor()


def get_document_service(
    repo: IDocumentRepository = Depends(get_document_repo),
    pdf_processor: IPDFProcessor = Depends(get_pdf_processor),
) -> DocumentService:
    return DocumentService(repo, pdf_processor)


def get_health_repo(db: MongoDB = Depends(get_mongodb)) -> IHealthRepository:
    return MongoHealthRepository(client=db.client)


def get_health_service(
    health_repo: IHealthRepository = Depends(get_health_repo),
) -> HealthService:
    return HealthService(health_repo)