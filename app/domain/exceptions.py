class DomainError(Exception):
    """Base de todos los errores de dominio.

    `code` es un identificador estable y legible del problema (usado por la
    capa de API para resolver el `status` HTTP sin acoplar dominio e HTTP).
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        return self.detail


class DocumentNotFoundError(DomainError):
    code = "DOCUMENT_NOT_FOUND"

    def __init__(self, doc_id: str) -> None:
        super().__init__(self.code, f"Documento con id '{doc_id}' no encontrado.")


class InvalidDocumentIdError(DomainError):
    code = "INVALID_DOCUMENT_ID"

    def __init__(self, doc_id: str) -> None:
        super().__init__(self.code, f"'{doc_id}' no es un ID válido.")


class FileSizeExceededError(DomainError):
    code = "FILE_SIZE_EXCEEDED"

    def __init__(self, max_size_mb: int) -> None:
        super().__init__(self.code, f"El archivo supera el límite permitido de {max_size_mb} MB.")


class InvalidPDFFormatError(DomainError):
    code = "INVALID_PDF_FORMAT"

    def __init__(self, detail: str = "El archivo no es un PDF válido.") -> None:
        super().__init__(self.code, detail)


class PDFProcessingError(DomainError):
    code = "PDF_PROCESSING_ERROR"

    def __init__(self, detail: str = "No se pudo extraer el texto del PDF.") -> None:
        super().__init__(self.code, detail)


class DocumentAlreadyExistsError(DomainError):
    code = "DOCUMENT_ALREADY_EXISTS"

    def __init__(self, checksum: str) -> None:
        super().__init__(self.code, f"El documento ya fue cargado previamente (checksum: {checksum}).")