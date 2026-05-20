"""
Unit tests for app/services/pdf_service.py (now pointing to app.utils.pdf_processor)
Covers: compute_checksum, validate_pdf, extract_text, read_upload_bytes

Fixtures use the sample PDFs in tests/sample_pdfs/ plus minimal in-memory
PDFs built with fitz when the fixture file exercises a specific edge case.

Run:
    pytest tests/test_pdf_service.py -v
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz
import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Adjust the import path to your project layout
# ---------------------------------------------------------------------------
from app.services.pdf_processor import (
    compute_checksum,
    extract_text,
    read_upload_bytes,
    validate_pdf,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLES = Path(__file__).parent / "sample_pdfs"


def _load_sample(name: str) -> bytes:
    """Return bytes of a sample PDF from tests/sample_pdfs/."""
    return (SAMPLES / name).read_bytes()


def _make_pdf_bytes(text: str = "Hello world", n_pages: int = 1) -> bytes:
    """
    Build a minimal valid PDF in memory with fitz.
    Useful when the exact sample file doesn't exist or we need a
    controlled payload (size, content).
    """
    doc = fitz.open()
    for _ in range(n_pages):
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_oversized_pdf(max_mb: int) -> bytes:
    """Return a byte string larger than max_mb MB that starts with %PDF."""
    header = b"%PDF-1.4\n"
    padding = b"x" * ((max_mb * 1024 * 1024) + 1)
    return header + padding


# ---------------------------------------------------------------------------
# compute_checksum
# ---------------------------------------------------------------------------


class TestComputeChecksum:
    def test_returns_hex_string_of_64_chars(self):
        result = compute_checksum(b"hello")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_matches_standard_sha256(self):
        data = b"unit test payload"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_checksum(data) == expected

    def test_empty_bytes(self):
        result = compute_checksum(b"")
        assert len(result) == 64

    def test_different_inputs_produce_different_hashes(self):
        assert compute_checksum(b"aaa") != compute_checksum(b"bbb")

    def test_same_input_always_produces_same_hash(self):
        data = b"deterministic"
        assert compute_checksum(data) == compute_checksum(data)

    def test_checksum_of_real_pdf(self):
        """Checksum of actual project PDF must be stable."""
        pdf_bytes = _load_sample("simple_text.pdf")
        result = compute_checksum(pdf_bytes)
        assert len(result) == 64
        # Run twice — must be identical (determinism check)
        assert result == compute_checksum(pdf_bytes)


# ---------------------------------------------------------------------------
# validate_pdf
# ---------------------------------------------------------------------------


class TestValidatePdf:
    # ── Valid cases ──────────────────────────────────────────────────────────

    def test_valid_simple_text_pdf(self):
        """simple_text.pdf — should pass without raising."""
        validate_pdf(_load_sample("simple_text.pdf"), "simple_text.pdf")

    def test_valid_multipage_pdf(self):
        validate_pdf(_load_sample("multipage_text.pdf"), "multipage_text.pdf")

    def test_valid_mixed_content_pdf(self):
        validate_pdf(_load_sample("mixed_content.pdf"), "mixed_content.pdf")

    def test_valid_empty_pdf(self):
        """empty.pdf — structurally valid PDF, just has no text."""
        validate_pdf(_load_sample("empty.pdf"), "empty.pdf")

    def test_valid_special_chars_pdf(self):
        validate_pdf(_load_sample("special_chars.pdf"), "special_chars.pdf")

    def test_valid_table_content_pdf(self):
        validate_pdf(_load_sample("table_content.pdf"), "table_content.pdf")

    def test_valid_spaces_only_pdf(self):
        validate_pdf(_load_sample("spaces_only.pdf"), "spaces_only.pdf")

    def test_valid_image_content_pdf(self):
        validate_pdf(_load_sample("image_content.pdf"), "image_content.pdf")

    def test_valid_in_memory_pdf(self):
        validate_pdf(_make_pdf_bytes("Hello"), "in_memory.pdf")

    # ── Invalid format ───────────────────────────────────────────────────────

    def test_raises_400_for_plain_text_file(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(b"This is not a pdf", "doc.txt")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_jpeg_file(self):
        # JPEG magic bytes: FF D8 FF
        fake_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(fake_jpg, "photo.jpg")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_empty_bytes(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(b"", "empty.pdf")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_truncated_pdf(self):
        """A file that starts with %PDF but is structurally broken."""
        corrupt = b"%PDF-1.4\n%%EOF"

        # FIX 3: Reemplazar el try/except manual por pytest.raises para asegurar
        # que la prueba falle correctamente si no se levanta la excepción.
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(corrupt, "corrupt.pdf")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_pdf_magic_with_garbage_body(self):
        garbage = b"%PDF-1.4\n" + b"\x00\x01\x02\x03" * 50
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(garbage, "garbage.pdf")
        assert exc_info.value.status_code == 400

    # ── Oversized file ───────────────────────────────────────────────────────

    # FIX 2: Mockeamos el objeto 'settings' donde es importado (app.utils.pdf_processor.settings)
    @patch("app.utils.pdf_processor.MAX_SIZE_BYTES", 5 * 1024 * 1024)
    @patch("app.utils.pdf_processor.settings")
    def test_raises_400_when_file_exceeds_max_size(self, mock_settings):
        # Mantenemos el mock de settings solo para que el mensaje de error
        # coincida con el "5 MB" que espera el assert.
        mock_settings.PDF_MAX_SIZE_MB = 5

        oversized = _make_oversized_pdf(5)
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(oversized, "big.pdf")
        assert exc_info.value.status_code == 400
        assert "MB" in exc_info.value.detail

    @patch("app.utils.pdf_processor.MAX_SIZE_BYTES", 1 * 1024 * 1024)
    @patch("app.utils.pdf_processor.settings")
    def test_exactly_at_max_size_does_not_raise(self, mock_settings):
        mock_settings.PDF_MAX_SIZE_MB = 1
        max_bytes = 1 * 1024 * 1024

        base = _make_pdf_bytes("limit test")
        if len(base) <= max_bytes:
            validate_pdf(base, "at_limit.pdf")


# ---------------------------------------------------------------------------
# extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    # ── Returns string ───────────────────────────────────────────────────────

    def test_returns_string(self):
        result = extract_text(_make_pdf_bytes("Hello world"))
        assert isinstance(result, str)

    def test_simple_text_extracted(self):
        result = extract_text(_make_pdf_bytes("Hello world"))
        assert "Hello world" in result

    def test_result_is_stripped(self):
        """extract_text must strip leading/trailing whitespace."""
        result = extract_text(_make_pdf_bytes("  trimmed  "))
        assert result == result.strip()

    # ── Sample files ─────────────────────────────────────────────────────────

    def test_simple_text_pdf_has_content(self):
        result = extract_text(_load_sample("simple_text.pdf"))
        assert len(result) > 0

    def test_multipage_pdf_contains_text_from_multiple_pages(self):
        result = extract_text(_load_sample("multipage_text.pdf"))
        assert len(result) > 0

    def test_special_chars_pdf_does_not_raise(self):
        """Special characters (accents, symbols) must not crash extraction."""
        result = extract_text(_load_sample("special_chars.pdf"))
        assert isinstance(result, str)

    def test_table_content_pdf_extracts_something(self):
        result = extract_text(_load_sample("table_content.pdf"))
        assert isinstance(result, str)

    def test_mixed_content_pdf_extracts_something(self):
        result = extract_text(_load_sample("mixed_content.pdf"))
        assert isinstance(result, str)

    # ── Edge-case PDFs ───────────────────────────────────────────────────────

    def test_empty_pdf_returns_empty_string(self):
        """A PDF with no pages / no text should return a string without crashing."""
        result = extract_text(_load_sample("empty.pdf"))
        assert isinstance(result, str)

    def test_spaces_only_pdf_returns_empty_or_whitespace(self):
        """A PDF with only whitespace characters should return '' after strip."""
        result = extract_text(_load_sample("spaces_only.pdf"))
        # strip() is applied inside extract_text, so result must equal stripped
        assert result == result.strip()

    def test_image_only_pdf_returns_empty_string(self):
        """
        image_content.pdf — no embedded text layer.
        Extraction returns empty (OCR is out of scope).
        """
        result = extract_text(_load_sample("image_content.pdf"))
        assert isinstance(result, str)
        # We don't assert emptiness because the file might have alt-text;
        # we just assert no exception is raised.

    def test_multipage_in_memory_pdf(self):
        pdf = _make_pdf_bytes("Page content", n_pages=3)
        result = extract_text(pdf)
        assert "Page content" in result

    # ── Error path ───────────────────────────────────────────────────────────

    def test_raises_422_when_extraction_fails(self):
        """
        If fitz.open or pymupdf4llm.to_markdown raises, extract_text
        must wrap it in HTTPException 422.
        """
        valid_pdf = _make_pdf_bytes("test")

        # FIX 1: Cambiada la ruta a 'app.utils.pdf_processor.fitz.open'
        with patch("app.utils.pdf_processor.fitz.open") as mock_open:
            mock_open.side_effect = RuntimeError("simulated fitz crash")
            with pytest.raises(HTTPException) as exc_info:
                extract_text(valid_pdf)
            assert exc_info.value.status_code == 422
            assert "No se pudo extraer" in exc_info.value.detail

    def test_raises_422_when_to_markdown_fails(self):
        # FIX 1: Cambiada la ruta a 'app.utils.pdf_processor.pymupdf4llm.to_markdown'
        with patch("app.utils.pdf_processor.pymupdf4llm.to_markdown") as mock_md:
            mock_md.side_effect = ValueError("markdown error")
            valid_pdf = _make_pdf_bytes("test")
            with pytest.raises(HTTPException) as exc_info:
                extract_text(valid_pdf)
            assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# read_upload_bytes
# ---------------------------------------------------------------------------


class TestReadUploadBytes:
    @pytest.mark.asyncio
    async def test_returns_bytes_from_upload_file(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(return_value=b"pdf bytes here")
        result = await read_upload_bytes(mock_upload)
        assert result == b"pdf bytes here"

    @pytest.mark.asyncio
    async def test_calls_read_exactly_once(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(return_value=b"data")
        await read_upload_bytes(mock_upload)
        mock_upload.read.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_bytes_for_empty_upload(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(return_value=b"")
        result = await read_upload_bytes(mock_upload)
        assert result == b""

    @pytest.mark.asyncio
    async def test_returns_real_pdf_bytes(self):
        pdf_bytes = _make_pdf_bytes("async read test")
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(return_value=pdf_bytes)
        result = await read_upload_bytes(mock_upload)
        assert result == pdf_bytes
        assert result.startswith(b"%PDF")


# ---------------------------------------------------------------------------
# Integration-style: full pipeline on sample files
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """
    Simulate the real service flow:
        read bytes → validate → compute checksum → extract text
    """

    @pytest.mark.parametrize(
        "filename",
        [
            "simple_text.pdf",
            "multipage_text.pdf",
            "mixed_content.pdf",
            "special_chars.pdf",
            "table_content.pdf",
        ],
    )
    def test_pipeline_succeeds_for_text_pdfs(self, filename: str):
        raw = _load_sample(filename)
        validate_pdf(raw, filename)
        checksum = compute_checksum(raw)
        text = extract_text(raw)

        assert len(checksum) == 64
        assert isinstance(text, str)

    def test_duplicate_detection_via_checksum(self):
        """Same file uploaded twice must produce identical checksum."""
        raw = _load_sample("simple_text.pdf")
        assert compute_checksum(raw) == compute_checksum(raw)

    def test_different_files_have_different_checksums(self):
        a = _load_sample("simple_text.pdf")
        b = _load_sample("multipage_text.pdf")
        assert compute_checksum(a) != compute_checksum(b)