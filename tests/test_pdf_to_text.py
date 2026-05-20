"""
Unit tests para el endpoint /extract-text de extract_text.py

Dependencias para correr:
    pip install pymupdf pymupdf4llm fastapi httpx pytest pytest-asyncio
    python-multipart reportlab

Correr:
    pytest test_extract_text.py -v
"""

import io
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfgen import canvas

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


def make_empty_text_pdf() -> bytes:
    """PDF válido pero sin texto (solo página en blanco)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.showPage()
    c.save()
    return buf.getvalue()


def make_multicolumn_pdf() -> bytes:
    """PDF con texto en dos columnas simuladas."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 11)
    # Columna izquierda
    for i, line in enumerate(["Columna Izquierda", "Línea 1", "Línea 2", "Línea 3"]):
        c.drawString(50, 750 - i * 20, line)
    # Columna derecha
    for i, line in enumerate(["Columna Derecha", "Dato A", "Dato B", "Dato C"]):
        c.drawString(320, 750 - i * 20, line)
    c.save()
    return buf.getvalue()


# ──────────────────────────────────────────────
# Fixture: cliente de prueba con mocks de fitz y pymupdf4llm
# ──────────────────────────────────────────────

@pytest.fixture
def client():
    """
    Retorna un TestClient de FastAPI con fitz y pymupdf4llm mockeados.
    Los mocks están configurados para simular extracción real de texto
    a partir de los bytes del PDF usando pypdf como backend alternativo.
    """
    from app.services import pdf_to_text as app_module
    with (
        patch.object(app_module, "fitz") as mock_fitz,
        patch.object(app_module, "pymupdf4llm") as mock_md,
    ):
        # fitz.open() devuelve un doc mock con 1 página por defecto
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_fitz.open.return_value = mock_doc

        # pymupdf4llm.to_markdown() extrae texto real usando pymupdf4llm real
        # sobre los bytes originales del PDF, sin persistencia en disco
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

        from fastapi.testclient import TestClient
        yield TestClient(app_module.app), mock_fitz, mock_md


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestExtractTextEndpoint:

    # ── 1. Casos válidos ──────────────────────

    def test_simple_pdf_returns_200(self, client):
        """PDF de una página con texto simple: responde 200."""
        tc, _, _ = client
        pdf_bytes = make_simple_pdf("Hello World")
        response = tc.post(
            "/extract-text",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200

    def test_simple_pdf_contains_text(self, client):
        """El texto extraído contiene el contenido esperado."""
        tc, _, _ = client
        pdf_bytes = make_simple_pdf("Texto de prueba unitaria")
        response = tc.post(
            "/extract-text",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        )
        body = response.json()
        assert "text" in body
        assert "Texto de prueba unitaria" in body["text"]

    def test_returns_filename(self, client):
        """La respuesta incluye el nombre del archivo enviado."""
        tc, _, _ = client
        pdf_bytes = make_simple_pdf()
        response = tc.post(
            "/extract-text",
            files={"file": ("mi_documento.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.json()["filename"] == "mi_documento.pdf"

    def test_multipage_pdf(self, client):
        """PDF de varias páginas: extrae texto de todas las páginas."""
        tc, mock_fitz, _ = client
        pages_text = ["Página uno del documento", "Página dos del documento", "Página tres"]
        pdf_bytes = make_multipage_pdf(pages_text)

        # Actualiza el mock para 3 páginas
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3
        mock_fitz.open.return_value = mock_doc

        response = tc.post(
            "/extract-text",
            files={"file": ("multipage.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        extracted = response.json()["text"]
        for expected in pages_text:
            assert expected in extracted

    def test_rich_text_pdf(self, client):
        """PDF con estilos (títulos, párrafos): extrae el contenido textual."""
        tc, _, _ = client
        pdf_bytes = make_rich_text_pdf()
        response = tc.post(
            "/extract-text",
            files={"file": ("informe.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        text = response.json()["text"]
        assert "Informe Anual 2024" in text
        assert "4.200 millones" in text

    def test_multicolumn_pdf(self, client):
        """PDF con columnas: el texto de ambas columnas está presente."""
        tc, _, _ = client
        pdf_bytes = make_multicolumn_pdf()
        response = tc.post(
            "/extract-text",
            files={"file": ("columnas.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        text = response.json()["text"]
        assert "Columna Izquierda" in text
        assert "Columna Derecha" in text

    def test_empty_text_pdf_returns_empty_string(self, client):
        """PDF sin texto produce string vacío (no error)."""
        tc, _, mock_md = client
        mock_md.to_markdown.side_effect = None
        mock_md.to_markdown.return_value = ""

        pdf_bytes = make_empty_text_pdf()
        response = tc.post(
            "/extract-text",
            files={"file": ("blank.pdf", pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 200
        assert response.json()["text"] == ""

    def test_fitz_called_with_stream_not_path(self, client):
        """fitz.open() debe recibir stream= (en memoria), nunca una ruta."""
        tc, mock_fitz, _ = client
        pdf_bytes = make_simple_pdf("in-memory check")
        tc.post(
            "/extract-text",
            files={"file": ("check.pdf", pdf_bytes, "application/pdf")},
        )
        call_kwargs = mock_fitz.open.call_args.kwargs
        # Verifica que NO se pasó filepath y SÍ se pasó stream
        assert "stream" in call_kwargs
        assert call_kwargs.get("filetype") == "pdf"

    def test_fitz_receives_correct_bytes(self, client):
        """Los bytes pasados a fitz.open() son exactamente los del PDF enviado."""
        tc, mock_fitz, _ = client
        pdf_bytes = make_simple_pdf("bytes integrity check")
        tc.post(
            "/extract-text",
            files={"file": ("bytes.pdf", pdf_bytes, "application/pdf")},
        )
        received_bytes = mock_fitz.open.call_args.kwargs["stream"]
        assert received_bytes == pdf_bytes

    def test_doc_is_closed_after_extraction(self, client):
        """doc.close() se llama siempre, incluso en el camino feliz."""
        tc, mock_fitz, _ = client
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 1
        mock_fitz.open.return_value = mock_doc

        tc.post(
            "/extract-text",
            files={"file": ("close.pdf", make_simple_pdf(), "application/pdf")},
        )
        mock_doc.close.assert_called_once()

    def test_to_markdown_called_with_no_images(self, client):
        """pymupdf4llm.to_markdown() se invoca con write_images=False y embed_images=False."""
        tc, _, mock_md = client
        mock_md.to_markdown.side_effect = None
        mock_md.to_markdown.return_value = "texto"

        tc.post(
            "/extract-text",
            files={"file": ("flags.pdf", make_simple_pdf(), "application/pdf")},
        )
        _, kwargs = mock_md.to_markdown.call_args
        assert kwargs.get("write_images") is False
        assert kwargs.get("embed_images") is False

    # ── 2. Casos de error ────────────────────

    def test_non_pdf_file_returns_400(self, client):
        """Un archivo que no es .pdf devuelve HTTP 400."""
        tc, _, _ = client
        response = tc.post(
            "/extract-text",
            files={"file": ("document.txt", b"no es un pdf", "text/plain")},
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_non_pdf_extension_returns_400(self, client):
        """Archivo con extensión .docx devuelve 400 aunque el contenido sea válido."""
        tc, _, _ = client
        response = tc.post(
            "/extract-text",
            files={"file": ("archivo.docx", make_simple_pdf(), "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_corrupt_pdf_returns_500(self, client):
        """Bytes corruptos (no PDF válido) producen HTTP 500."""
        tc, mock_fitz, _ = client
        mock_fitz.open.side_effect = Exception("PDF corrupto")

        response = tc.post(
            "/extract-text",
            files={"file": ("corrupto.pdf", b"%PDF-broken-data", "application/pdf")},
        )
        assert response.status_code == 500
        assert "Error al procesar el PDF" in response.json()["detail"]

    def test_empty_bytes_returns_500(self, client):
        """Archivo vacío produce HTTP 500."""
        tc, mock_fitz, _ = client
        mock_fitz.open.side_effect = Exception("empty stream")

        response = tc.post(
            "/extract-text",
            files={"file": ("vacio.pdf", b"", "application/pdf")},
        )
        assert response.status_code == 500

    def test_pymupdf4llm_exception_returns_500(self, client):
        """Si pymupdf4llm falla, el endpoint devuelve 500 con mensaje de error."""
        tc, _, mock_md = client
        mock_md.to_markdown.side_effect = RuntimeError("fallo interno de extracción")

        response = tc.post(
            "/extract-text",
            files={"file": ("error.pdf", make_simple_pdf(), "application/pdf")},
        )
        assert response.status_code == 500
        assert "Error al procesar el PDF" in response.json()["detail"]

    def test_no_file_field_returns_422(self, client):
        """Llamar al endpoint sin el campo 'file' devuelve 422 (validación FastAPI)."""
        tc, _, _ = client
        response = tc.post("/extract-text")
        assert response.status_code == 422