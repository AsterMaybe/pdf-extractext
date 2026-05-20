"""
Unit tests for app/services/pdf_processor.py
Covers: compute_checksum, validate_pdf, read_upload_bytes
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
    read_upload_bytes,
    validate_pdf,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLES = Path(__file__).parent / "sample_pdfs"

def _load_sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()

def _make_pdf_bytes(text: str = "Hello world", n_pages: int = 1) -> bytes:
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
        pdf_bytes = _load_sample("simple_text.pdf")
        result = compute_checksum(pdf_bytes)
        assert len(result) == 64
        assert result == compute_checksum(pdf_bytes)

# ---------------------------------------------------------------------------
# validate_pdf
# ---------------------------------------------------------------------------

class TestValidatePdf:
    # ── Valid cases ──────────────────────────────────────────────────────────

    def test_valid_simple_text_pdf(self):
        validate_pdf(_load_sample("simple_text.pdf"), "simple_text.pdf")

    def test_valid_multipage_pdf(self):
        validate_pdf(_load_sample("multipage_text.pdf"), "multipage_text.pdf")

    def test_valid_mixed_content_pdf(self):
        validate_pdf(_load_sample("mixed_content.pdf"), "mixed_content.pdf")

    def test_valid_empty_pdf(self):
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
        fake_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(fake_jpg, "photo.jpg")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_empty_bytes(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(b"", "empty.pdf")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_truncated_pdf(self):
        corrupt = b"%PDF-1.4\n%%EOF"
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(corrupt, "corrupt.pdf")
        assert exc_info.value.status_code == 400

    def test_raises_400_for_pdf_magic_with_garbage_body(self):
        garbage = b"%PDF-1.4\n" + b"\x00\x01\x02\x03" * 50
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(garbage, "garbage.pdf")
        assert exc_info.value.status_code == 400

    # ── Oversized file ───────────────────────────────────────────────────────

    @patch("app.services.pdf_processor.MAX_SIZE_BYTES", 5 * 1024 * 1024)
    @patch("app.services.pdf_processor.settings")
    def test_raises_400_when_file_exceeds_max_size(self, mock_settings):
        mock_settings.PDF_MAX_SIZE_MB = 5
        oversized = _make_oversized_pdf(5)
        with pytest.raises(HTTPException) as exc_info:
            validate_pdf(oversized, "big.pdf")
        assert exc_info.value.status_code == 400
        assert "MB" in exc_info.value.detail

    @patch("app.services.pdf_processor.MAX_SIZE_BYTES", 1 * 1024 * 1024)
    @patch("app.services.pdf_processor.settings")
    def test_exactly_at_max_size_does_not_raise(self, mock_settings):
        mock_settings.PDF_MAX_SIZE_MB = 1
        max_bytes = 1 * 1024 * 1024
        base = _make_pdf_bytes("limit test")
        if len(base) <= max_bytes:
            validate_pdf(base, "at_limit.pdf")

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
# Integration-style: Validation Pipeline
# ---------------------------------------------------------------------------

class TestValidationPipeline:
    """
    Simulate the real service flow up to extraction:
        read bytes → validate → compute checksum
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
    def test_pipeline_succeeds_for_validation(self, filename: str):
        raw = _load_sample(filename)
        validate_pdf(raw, filename)
        checksum = compute_checksum(raw)
        assert len(checksum) == 64

    def test_duplicate_detection_via_checksum(self):
        raw = _load_sample("simple_text.pdf")
        assert compute_checksum(raw) == compute_checksum(raw)

    def test_different_files_have_different_checksums(self):
        a = _load_sample("simple_text.pdf")
        b = _load_sample("multipage_text.pdf")
        assert compute_checksum(a) != compute_checksum(b)