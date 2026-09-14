class DocumentNotFoundError(Exception):
    def __init__(self, doc_id: str):
        super().__init__(f"Documento con id '{doc_id}' no encontrado.")


class FileSizeExceededError(Exception):
    def __init__(self, max_size_mb: int):
        super().__init__(f"El archivo supera el límite permitido de {max_size_mb} MB.")


class InvalidPDFFormatError(Exception):
    def __init__(self, detail: str = "El archivo no es un PDF válido."):
        super().__init__(detail)


class DocumentAlreadyExistsError(Exception):
    def __init__(self, checksum: str):
        super().__init__(f"El documento ya fue cargado previamente (checksum: {checksum}).")