"""
Tests unitarios del modelo RFC 9457 (ProblemDetail) y del registro de
estados HTTP que alimenta los handlers consolidados.
"""

from fastapi import status

from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    FileSizeExceededError,
    InvalidPDFFormatError,
    PDFProcessingError,
)
from app.domain.problem_detail import ProblemDetail


class TestProblemDetailModel:
    """El modelo debe cumplir el contrato mínimo de RFC 9457."""

    def test_type_defaults_to_about_blank(self):
        problem = ProblemDetail(title="Bad Request", status=400, detail="detalle")
        assert problem.type == "about:blank"

    def test_optional_fields_are_none_by_default(self):
        problem = ProblemDetail(title="Bad Request", status=400, detail="detalle")
        assert problem.instance is None
        assert problem.errors is None

    def test_all_fields_are_set(self):
        problem = ProblemDetail(
            type="https://example.com/errors/custom",
            title="Conflict",
            status=409,
            detail="duplicado",
            instance="/api/v1/documents/upload",
            errors=[{"loc": ["body"], "msg": "x"}],
        )
        assert problem.type == "https://example.com/errors/custom"
        assert problem.title == "Conflict"
        assert problem.status == 409
        assert problem.detail == "duplicado"
        assert problem.instance == "/api/v1/documents/upload"
        assert problem.errors == [{"loc": ["body"], "msg": "x"}]

    def test_dump_excludes_none_fields(self):
        problem = ProblemDetail(title="Bad Request", status=400, detail="detalle")
        data = problem.model_dump(exclude_none=True)
        assert data["type"] == "about:blank"
        assert data["title"] == "Bad Request"
        assert data["status"] == 400
        assert data["detail"] == "detalle"
        assert "instance" not in data
        assert "errors" not in data


class TestHttpStatusByCodeMap:
    """Todo error de dominio debe tener su código HTTP en el registro (OCP)."""

    def test_document_not_found_is_404(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_CODE

        assert HTTP_STATUS_BY_CODE[DocumentNotFoundError.code] == status.HTTP_404_NOT_FOUND

    def test_already_exists_is_409(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_CODE

        assert HTTP_STATUS_BY_CODE[DocumentAlreadyExistsError.code] == status.HTTP_409_CONFLICT

    def test_file_size_exceeded_is_400(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_CODE

        assert HTTP_STATUS_BY_CODE[FileSizeExceededError.code] == status.HTTP_400_BAD_REQUEST

    def test_invalid_pdf_format_is_400(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_CODE

        assert HTTP_STATUS_BY_CODE[InvalidPDFFormatError.code] == status.HTTP_400_BAD_REQUEST

    def test_pdf_processing_error_is_422(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_CODE

        assert HTTP_STATUS_BY_CODE[PDFProcessingError.code] == status.HTTP_422_UNPROCESSABLE_CONTENT