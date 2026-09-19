"""
Unit tests para app/infrastructure/pymupdf_processor.py (extract_text).

Dependencias para correr:
    uv sync / pip install pymupdf pymupdf4llm fastapi httpx pytest pytest-asyncio

Correr:
    uv run pytest tests/test_pdf_to_text.py -v
"""

import io
import pytest
from unittest.mock import MagicMock, patch
from fastapi import status
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.api.dependencies import get_document_repo, get_pdf_processor
from app.domain.exceptions import PDFProcessingError
from app.infrastructure import pymupdf_processor as pymupdf_processor_module
from app.main import app

# ──────────────────────────────────────────────
# Factories de PDFs de muestra (en memoria)
# ──────────────────────────────────────────────

def make_simple_pdf(text: str = "Hello World") -> bytes:
    """PDF de una página con texto simple."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 14)
    c.drawString(100, 750, text)
    c.save()
    return buf.getvalue()


# ──────────────────────────────────────────────
# Fixture: mocks de fitz y pymupdf4llm
# ──────────────────────────────────────────────

@pytest.fixture
def mocks():
    """
    Retorna (mock_fitz, mock_md) con el módulo pymupdf_processor parcheado.

    Es un stub 100% determinista: NO re-ejecuta la lógica interna de PyMuPDF
    (anti-patrón over-mocking). La extracción real de texto se cubre en los
    tests de integración con PDFs de muestra, no aquí.
    """
    with (
        patch.object(pymupdf_processor_module, "fitz") as mock_fitz,
        patch.object(pymupdf_processor_module, "pymupdf4llm") as mock_md,
    ):
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_fitz.open.return_value = mock_doc

        mock_md.to_markdown.return_value = "Mocked PDF text content"

        yield mock_fitz, mock_md


# ──────────────────────────────────────────────
# Tests unitarios: extract_text
# ──────────────────────────────────────────────

class TestExtractText:

    def test_simple_pdf_returns_content(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.return_value = "Hello World"
        assert pymupdf_processor_module.extract_text(make_simple_pdf("Hello World")) == "Hello World"

    def test_strips_surrounding_whitespace(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.return_value = "  texto con espacios  \n\n"
        assert pymupdf_processor_module.extract_text(b"whatever") == "texto con espacios"

    def test_multipage_pdf_calls_library_for_all_pages(self, mocks):
        """Verifica que se le piden todas las páginas a la librería (stub puro)."""
        mock_fitz, mock_md = mocks
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3
        mock_fitz.open.return_value = mock_doc
        mock_md.to_markdown.return_value = ""

        result = pymupdf_processor_module.extract_text(b"%PDF-3-pages")

        assert result == ""
        assert mock_md.to_markdown.call_args.kwargs["pages"] == [0, 1, 2]

    def test_default_stub_output_is_deterministic(self, mocks):
        """El stub por defecto es predecible y no re-ejecuta lógica real."""
        _, mock_md = mocks
        assert mock_md.to_markdown.return_value == "Mocked PDF text content"
        result = pymupdf_processor_module.extract_text(b"%PDF-stub")
        assert result == "Mocked PDF text content"

    def test_fitz_called_with_stream_not_path(self, mocks):
        mock_fitz, _ = mocks
        pymupdf_processor_module.extract_text(make_simple_pdf("in-memory check"))
        call_kwargs = mock_fitz.open.call_args.kwargs
        assert "stream" in call_kwargs
        assert call_kwargs.get("filetype") == "pdf"

    def test_fitz_receives_correct_bytes(self, mocks):
        mock_fitz, _ = mocks
        pdf_bytes = make_simple_pdf("bytes integrity check")
        pymupdf_processor_module.extract_text(pdf_bytes)
        received_bytes = mock_fitz.open.call_args.kwargs["stream"]
        assert received_bytes == pdf_bytes

    def test_doc_is_closed_after_extraction(self, mocks):
        mock_fitz, _ = mocks
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_fitz.open.return_value = mock_doc

        pymupdf_processor_module.extract_text(make_simple_pdf())
        mock_doc.close.assert_called_once()

    def test_to_markdown_called_with_no_images(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.return_value = "texto"

        pymupdf_processor_module.extract_text(make_simple_pdf())
        _, kwargs = mock_md.to_markdown.call_args
        assert kwargs.get("write_images") is False
        assert kwargs.get("embed_images") is False

    def test_empty_text_returns_empty_string(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.return_value = ""
        assert pymupdf_processor_module.extract_text(make_simple_pdf()) == ""

    def test_extraction_error_becomes_domain_error(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.side_effect = RuntimeError("fallo interno de extracción")
        with pytest.raises(PDFProcessingError):
            pymupdf_processor_module.extract_text(make_simple_pdf())

    def test_open_error_becomes_domain_error(self, mocks):
        mock_fitz, _ = mocks
        mock_fitz.open.side_effect = Exception("PDF corrupto")
        with pytest.raises(PDFProcessingError):
            pymupdf_processor_module.extract_text(b"%PDF-broken-data")


# ──────────────────────────────────────────────
# Capa HTTP: un error de extracción devuelve 500 problem+json
# ──────────────────────────────────────────────

class _StubRepo:
    async def exists_by_checksum(self, checksum: str) -> bool:
        return False

    async def create(self, doc):
        raise NotImplementedError


class _ExplodingProcessor:
    """Doble de `IPDFProcessor`: falla de forma controlada al extraer texto."""

    async def validate_format(self, file_bytes: bytes) -> None:
        return None

    async def compute_checksum(self, file_bytes: bytes) -> str:
        return "stub-checksum"

    async def extract_text(self, file_bytes: bytes) -> str:
        raise RuntimeError("fallo interno de extracción")


class TestExtractionErrorHttp:
    def test_extraction_error_returns_500_problem(self):
        # Se inyecta un doble de IPDFProcessor en vez de monkeypatchear el
        # módulo: el servicio depende de la abstracción, no del import.
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        app.dependency_overrides[get_pdf_processor] = lambda: _ExplodingProcessor()
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("sample.pdf", make_simple_pdf("OK"), "application/pdf")},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "inesperado" in response.json()["detail"]