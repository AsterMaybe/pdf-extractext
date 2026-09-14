"""
Unit tests para app/services/pdf_to_text.py (extract_text).

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
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfgen import canvas

from app.controllers.document_controller import get_document_repo
from app.main import app
from app.services import pdf_to_text as pdf_to_text_module

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


def make_multipage_pdf(pages: list[str]) -> bytes:
    """PDF con múltiples páginas, una frase por página."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in pages:
        c.setFont("Helvetica", 12)
        c.drawString(72, 750, text)
        c.showPage()
    c.save()
    return buf.getvalue()


def make_rich_text_pdf() -> bytes:
    """PDF con párrafos largos usando platypus (simula un doc real)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Informe Anual 2024", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            "Este documento contiene el resumen ejecutivo del informe anual "
            "correspondiente al ejercicio fiscal 2024. Los resultados obtenidos "
            "superaron las expectativas del mercado en todos los segmentos.",
            styles["BodyText"],
        ),
        Spacer(1, 12),
        Paragraph("Sección 1: Resultados Financieros", styles["Heading2"]),
        Paragraph(
            "Los ingresos totales alcanzaron los 4.200 millones de pesos, "
            "representando un crecimiento del 18% respecto al año anterior.",
            styles["BodyText"],
        ),
    ]
    doc.build(story)
    return buf.getvalue()


# ──────────────────────────────────────────────
# Fixture: mocks de fitz y pymupdf4llm
# ──────────────────────────────────────────────

@pytest.fixture
def mocks():
    """
    Retorna (mock_fitz, mock_md) con el módulo pdf_to_text parcheado.
    Por defecto pymupdf4llm.to_markdown() extrae texto real desde los bytes
    originales del PDF (persistencia cero, en memoria).
    """
    with (
        patch.object(pdf_to_text_module, "fitz") as mock_fitz,
        patch.object(pdf_to_text_module, "pymupdf4llm") as mock_md,
    ):
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_fitz.open.return_value = mock_doc

        def smart_to_markdown(doc, **kwargs):
            """Extrae texto real con pymupdf4llm para validar contenido."""
            import fitz as _fitz
            import pymupdf4llm as _pymupdf4llm
            call_args = mock_fitz.open.call_args
            pdf_bytes = call_args.kwargs.get("stream") or (call_args.args[0] if call_args.args else b"")
            try:
                real_doc = _fitz.open(stream=pdf_bytes, filetype="pdf")
                text = _pymupdf4llm.to_markdown(
                    real_doc,
                    pages=list(range(len(real_doc))),
                    page_chunks=False,
                    write_images=False,
                    embed_images=False,
                    graphics_limit=0,
                )
                real_doc.close()
                return text
            except Exception:
                return ""

        mock_md.to_markdown.side_effect = smart_to_markdown
        yield mock_fitz, mock_md


# ──────────────────────────────────────────────
# Tests unitarios: extract_text
# ──────────────────────────────────────────────

class TestExtractText:

    def test_simple_pdf_returns_content(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.side_effect = None
        mock_md.to_markdown.return_value = "Hello World"
        assert pdf_to_text_module.extract_text(make_simple_pdf("Hello World")) == "Hello World"

    def test_strips_surrounding_whitespace(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.side_effect = None
        mock_md.to_markdown.return_value = "  texto con espacios  \n\n"
        assert pdf_to_text_module.extract_text(b"whatever") == "texto con espacios"

    def test_multipage_pdf_extracts_all_pages(self, mocks):
        mock_fitz, mock_md = mocks
        pages_text = ["Página uno del documento", "Página dos del documento", "Página tres"]
        pdf_bytes = make_multipage_pdf(pages_text)

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3
        mock_fitz.open.return_value = mock_doc

        extracted = pdf_to_text_module.extract_text(pdf_bytes)
        for expected in pages_text:
            assert expected in extracted

    def test_rich_text_pdf_extracts_content(self, mocks):
        pdf_bytes = make_rich_text_pdf()
        extracted = pdf_to_text_module.extract_text(pdf_bytes)
        assert "Informe Anual 2024" in extracted
        assert "4.200 millones" in extracted

    def test_fitz_called_with_stream_not_path(self, mocks):
        mock_fitz, _ = mocks
        pdf_to_text_module.extract_text(make_simple_pdf("in-memory check"))
        call_kwargs = mock_fitz.open.call_args.kwargs
        assert "stream" in call_kwargs
        assert call_kwargs.get("filetype") == "pdf"

    def test_fitz_receives_correct_bytes(self, mocks):
        mock_fitz, _ = mocks
        pdf_bytes = make_simple_pdf("bytes integrity check")
        pdf_to_text_module.extract_text(pdf_bytes)
        received_bytes = mock_fitz.open.call_args.kwargs["stream"]
        assert received_bytes == pdf_bytes

    def test_doc_is_closed_after_extraction(self, mocks):
        mock_fitz, _ = mocks
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_fitz.open.return_value = mock_doc

        pdf_to_text_module.extract_text(make_simple_pdf())
        mock_doc.close.assert_called_once()

    def test_to_markdown_called_with_no_images(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.side_effect = None
        mock_md.to_markdown.return_value = "texto"

        pdf_to_text_module.extract_text(make_simple_pdf())
        _, kwargs = mock_md.to_markdown.call_args
        assert kwargs.get("write_images") is False
        assert kwargs.get("embed_images") is False

    def test_empty_text_returns_empty_string(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.side_effect = None
        mock_md.to_markdown.return_value = ""
        assert pdf_to_text_module.extract_text(make_simple_pdf()) == ""

    def test_extraction_error_propagates(self, mocks):
        mock_fitz, mock_md = mocks
        mock_md.to_markdown.side_effect = RuntimeError("fallo interno de extracción")
        with pytest.raises(RuntimeError):
            pdf_to_text_module.extract_text(make_simple_pdf())

    def test_open_error_propagates(self, mocks):
        mock_fitz, _ = mocks
        mock_fitz.open.side_effect = Exception("PDF corrupto")
        with pytest.raises(Exception):
            pdf_to_text_module.extract_text(b"%PDF-broken-data")


# ──────────────────────────────────────────────
# Capa HTTP: un error de extracción devuelve 500 problem+json
# ──────────────────────────────────────────────

class _StubRepo:
    async def exists_by_checksum(self, checksum: str) -> bool:
        return False

    async def create(self, doc):
        raise NotImplementedError


class TestExtractionErrorHttp:
    def test_extraction_error_returns_500_problem(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with (
                patch("app.services.document_service.extract_text",
                      side_effect=RuntimeError("fallo interno de extracción")),
                TestClient(app, raise_server_exceptions=False) as client,
            ):
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("sample.pdf", make_simple_pdf("OK"), "application/pdf")},
                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.headers["content-type"].startswith("application/problem+json")
        assert "inesperado" in response.json()["detail"]