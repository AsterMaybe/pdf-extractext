"""Orquesta la lógica de negocio de documentos sobre sus puertos (DIP)."""

from typing import Any

from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.domain.exceptions import DocumentAlreadyExistsError
from app.domain.pagination import PageQuery
from app.services.ports import IDocumentRepository, IPDFProcessor


class DocumentService:
    """Orquesta la lógica de negocio de documentos sobre sus puertos (DIP)."""

    def __init__(
        self,
        repo: IDocumentRepository,
        pdf_processor: IPDFProcessor,
        document_gateway: IPDFProcessor | None = None,
    ) -> None:
        self._repo = repo
        self._pdf_processor = pdf_processor
        self._document_gateway = document_gateway

    async def process_and_store_document(self, file_bytes: bytes, filename: str) -> DocumentResponse:
        """
        Orquesta el flujo completo: valida formato → guarda metadata en gateway
        → extrae texto → persiste en BD.

        Flujo:
        1️⃣ Validar formato (local, sin round-trip)
        2️⃣ Guardar metadatos en Document Gateway Service (microservicio-io)
        3️⃣ Extraer texto del Extract Service (microservicio-extract-go)
        4️⃣ Pre-check duplicados + persistir en MongoDB
        5️⃣ Retornar respuesta completa

        Raises:
            InvalidPDFFormatError: si el archivo no es un PDF vǭlido.
            PDFProcessingError: si no se pudo extraer el texto.
            DocumentAlreadyExistsError: si el checksum ya fue cargado antes.
        """
        # Paso 1: Validar formato (local, rápido, sin round-trip)
        await self._pdf_processor.validate_format(file_bytes)

        checksum = await self._pdf_processor.compute_checksum(file_bytes)

        # Paso 2: Guardar metadatos en Document Gateway Service (opcional)
        if self._document_gateway is not None:
            await self._document_gateway.extract_text(file_bytes)

        # Optimización: pre-check para evitar la costosa extracciòn de texto.
        # La garantía atómica la da el índice único + DuplicateKey del repo
        # (red de seguridad anti-carrera TOCTOU), no este chequeo.
        if await self._repo.exists_by_checksum(checksum):
            raise DocumentAlreadyExistsError(checksum)

        # Paso 3: Extraer texto del Extract Service (microservicio-extract-go)
        extracted_text = await self._pdf_processor.extract_text(file_bytes)

        # Paso 4: Persistir en MongoDB con texto extraído
        doc_create = DocumentCreate(
            filename=filename,
            text_content=extracted_text,
            checksum=checksum,
            file_size_bytes=len(file_bytes),
        )
        created = await self._repo.create(doc_create)

        # Paso 5: Retornar respuesta completa al cliente
        return DocumentResponse(
            id=str(created.id),
            filename=created.filename,
            text_content=created.text_content,
            checksum=created.checksum,
            file_size_bytes=created.file_size_bytes,
            created_at=str(created.created_at) if created.created_at else None,
        )

    async def list_documents(self, query: PageQuery) -> list[DocumentResponse]:
        return await self._repo.get_all(query)

    async def get_by_id(self, doc_id: str) -> DocumentResponse:
        return await self._repo.get_by_id(doc_id)

    async def update_document(self, doc_id: str, update_data: DocumentUpdate) -> DocumentResponse:
        """PATCH semántico: solo actualiza los campos provistos por el cliente."""
        changes = update_data.get_changes()
        if not changes:
            return await self.get_by_id(doc_id)
        return await self._repo.update(doc_id, changes)

    async def delete(self, doc_id: str) -> None:
        await self._repo.delete(doc_id)