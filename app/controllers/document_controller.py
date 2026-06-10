import logging
from app.config.logging_config import setup_logging
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from app.config.mongodb import mongodb
from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.repositories.document_repo import DocumentRepository
from app.services.pdf_processor import compute_checksum, read_upload_bytes, validate_pdf
from app.services.pdf_to_text import extract_text

router = APIRouter()

# ── Iniciar logger ────────────────────

logger = logging.getLogger(__name__)


# ── Dependencias ─────────────────────────────────────────────────────────────

def get_document_repo() -> DocumentRepository:
    """
    Inyecta el repositorio en las rutas instanciándolo con la colección global.
    """
    return DocumentRepository(mongodb.collection)


# ── Rutas / Endpoints ────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
        file: UploadFile = File(...),
        repo: DocumentRepository = Depends(get_document_repo)
):
    safe_filename = file.filename or "unnamed_document.pdf"

    logger.info(f"Starting upload process for file: {safe_filename}")

    file_bytes = await read_upload_bytes(file)

    logger.debug(f"Read {len(file_bytes)} bytes from {safe_filename}")

    validate_pdf(file_bytes, safe_filename)

    checksum = compute_checksum(file_bytes)
    if await repo.exists_by_checksum(checksum):
        logger.warning(f"Upload rejected: Duplicate checksum {checksum} for file {safe_filename}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento ya fue cargado previamente (Checksum duplicado)."
        )

    logger.debug(f"Extracting text from {safe_filename}")
    extracted_text = extract_text(file_bytes)

    doc_create = DocumentCreate(
        filename=safe_filename,
        text_content=extracted_text,
        checksum=checksum,
        file_size_bytes=len(file_bytes)
    )

    created_doc = await repo.create(doc_create)
    logger.info(
        f"Successfully processed and stored document: {safe_filename} (ID: {getattr(created_doc, 'id', 'unknown')})")

    return created_doc


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(repo: DocumentRepository = Depends(get_document_repo)):
    """Obtiene todos los documentos persistidos."""
    logger.debug("Fetching all documents")
    return await repo.get_all()


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, repo: DocumentRepository = Depends(get_document_repo)):
    """Obtiene un documento especifico por id"""
    logger.debug(f"Fetching document ID: {doc_id}")
    return await repo.get_by_id(doc_id)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
        doc_id: str,
        update_data: DocumentUpdate,
        repo: DocumentRepository = Depends(get_document_repo)
):

    logger.info(f"Updating document ID {doc_id} with data: {update_data.model_dump(exclude_unset=True)}")

    updated_doc = await repo.update(doc_id, update_data)

    if not updated_doc:
        logger.warning(f"Update failed: Document ID {doc_id} not found")

    return updated_doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: str, repo: DocumentRepository = Depends(get_document_repo)):
    logger.info(f"Deleting document ID: {doc_id}")
    await repo.delete(doc_id)