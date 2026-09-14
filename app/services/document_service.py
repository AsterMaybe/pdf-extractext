from fastapi import UploadFile

from app.domain.document import DocumentCreate, DocumentResponse
from app.domain.exceptions import DocumentAlreadyExistsError
from app.repositories.document_repo import DocumentRepository
from app.services.pdf_processor import (
    compute_checksum,
    read_and_validate_size,
    validate_file_size,
    validate_pdf_format,
)
from app.services.pdf_to_text import extract_text


class DocumentService:
    def __init__(self, repo: DocumentRepository):
        self.repo = repo

    async def process_and_store_document(self, file: UploadFile, safe_filename: str) -> DocumentResponse:
        file_bytes = await read_and_validate_size(file)
        validate_file_size(file_bytes)
        validate_pdf_format(file_bytes)

        checksum = compute_checksum(file_bytes)
        if await self.repo.exists_by_checksum(checksum):
            raise DocumentAlreadyExistsError(checksum)

        extracted_text = extract_text(file_bytes)
        doc_create = DocumentCreate(
            filename=safe_filename,
            text_content=extracted_text,
            checksum=checksum,
            file_size_bytes=len(file_bytes),
        )
        return await self.repo.create(doc_create)
