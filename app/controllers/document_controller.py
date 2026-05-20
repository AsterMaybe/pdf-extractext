from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorCollection

from app.config.mongodb import mongodb
from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.repositories.document_repo import DocumentRepository
from app.services.pdf_processor import compute_checksum, read_upload_bytes, validate_pdf
from app.services.pdf_to_text import extract_text

router = APIRouter()


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
    """
    Sube un PDF, lo valida, extrae el texto y lo persiste.
    """
    # 1. Leer en memoria (cumple regla de no persistir temporalmente)
    file_bytes = await read_upload_bytes(file)

    # 2. Validar formato y tamaño
    validate_pdf(file_bytes, file.filename)

    # 3. Generar Checksum y evitar duplicados
    checksum = compute_checksum(file_bytes)
    if await repo.exists_by_checksum(checksum):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento ya fue cargado previamente (Checksum duplicado)."
        )

    # 4. Extraer texto usando el servicio especializado
    extracted_text = extract_text(file_bytes)

    # 5. Armar modelo y persistir
    doc_create = DocumentCreate(
        filename=file.filename,
        text_content=extracted_text,
        checksum=checksum,
        file_size_bytes=len(file_bytes)
    )

    return await repo.create(doc_create)


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(repo: DocumentRepository = Depends(get_document_repo)):
    """Obtiene todos los documentos persistidos."""
    return await repo.get_all()


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str, repo: DocumentRepository = Depends(get_document_repo)):
    """Obtiene un documento específico por su ID."""
    return await repo.get_by_id(doc_id)


@router.patch("/{doc_id}", response_model=DocumentResponse)
async def update_document(
        doc_id: str,
        update_data: DocumentUpdate,
        repo: DocumentRepository = Depends(get_document_repo)
):
    """Actualiza parcialmente un documento (ej. corregir el filename)."""
    return await repo.update(doc_id, update_data)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: str, repo: DocumentRepository = Depends(get_document_repo)):
    """Elimina un documento de la base de datos."""
    await repo.delete(doc_id)