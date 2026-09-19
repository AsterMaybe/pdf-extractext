from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.domain.exceptions import DocumentAlreadyExistsError
from app.domain.pagination import PageQuery
from app.services.ports import IDocumentRepository, IPDFProcessor


class DocumentService:
    """Orquesta la lógica de negocio de documentos sobre sus puertos (DIP)."""

    def __init__(self, repo: IDocumentRepository, pdf_processor: IPDFProcessor) -> None:
        self._repo = repo
        self._pdf_processor = pdf_processor

    async def process_and_store_document(self, file_bytes: bytes, filename: str) -> DocumentResponse:
        """
        Valida, extrae texto y persiste un PDF recibido como bytes.

        El límite de tamaño ya fue aplicado por la capa de presentación
        (`read_upload_bytes`), por lo que aquí sólo se valida el formato.

        Raises:
            InvalidPDFFormatError: si el archivo no es un PDF válido.
            PDFProcessingError: si no se pudo extraer el texto.
            DocumentAlreadyExistsError: si el checksum ya fue cargado antes.
        """
        await self._pdf_processor.validate_format(file_bytes)

        checksum = await self._pdf_processor.compute_checksum(file_bytes)

        # Optimización: pre-check para evitar la costosa extracción de texto.
        # La garantía atómica la da el índice único + DuplicateKey del repo
        # (red de seguridad anti-carrera TOCTOU), no este chequeo.
        if await self._repo.exists_by_checksum(checksum):
            raise DocumentAlreadyExistsError(checksum)

        doc_create = DocumentCreate(
            filename=filename,
            text_content=await self._pdf_processor.extract_text(file_bytes),
            checksum=checksum,
            file_size_bytes=len(file_bytes),
        )
        return await self._repo.create(doc_create)

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