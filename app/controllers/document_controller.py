import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.dependencies import get_document_service
from app.api.uploads import read_upload_bytes
from app.domain.document import DocumentResponse, DocumentUpdate
from app.domain.pagination import PageQuery
from app.services.document_service import DocumentService

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_FILENAME = "unnamed_document.pdf"

# ── Rutas / Endpoints ────────────────────────────────────────────────────────


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    safe_filename = file.filename or DEFAULT_FILENAME
    logger.info("Starting upload process for file: %s", safe_filename)
    created_doc = await service.process_and_store_document(await read_upload_bytes(file), safe_filename)
    logger.info(
        "Successfully processed and stored document: %s (ID: %s)",
        safe_filename,
        created_doc.id,
    )
    return created_doc


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0, description="Número de documentos a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima por página"),
    service: DocumentService = Depends(get_document_service),
):
    """Obtiene los documentos persistidos con paginación."""
    logger.debug("Fetching documents: skip=%s limit=%s", skip, limit)
    return await service.list_documents(PageQuery(skip=skip, limit=limit))


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, service: DocumentService = Depends(get_document_service)):
    """Obtiene un documento especifico por id"""
    logger.debug("Fetching document ID: %s", doc_id)
    return await service.get_by_id(doc_id)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: str,
    update_data: DocumentUpdate,
    service: DocumentService = Depends(get_document_service),
):
    """Actualiza parcialmente un documento (PATCH semántico)."""
    logger.info("Updating document ID %s", doc_id)
    return await service.update_document(doc_id, update_data)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: str, service: DocumentService = Depends(get_document_service)):
    logger.info("Deleting document ID: %s", doc_id)
    await service.delete(doc_id)