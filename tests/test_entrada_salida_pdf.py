"""
Unit tests for app/infrastructure/pymupdf_processor.py
Covers: compute_checksum, validate_pdf_format
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import fitz
import pytest

from app.domain.exceptions import InvalidPDFFormatError
from app.infrastructure.pymupdf_processor import (
    compute_checksum,
    validate_pdf_format,
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
# validate_pdf_format
# ---------------------------------------------------------------------------

class TestValidatePdfFormat:
    # ── Valid cases ──────────────────────────────────────────────────────────

    def test_valid_simple_text_pdf(self):
        validate_pdf_format(_load_sample("simple_text.pdf"))

    def test_valid_multipage_pdf(self):
        validate_pdf_format(_load_sample("multipage_text.pdf"))

    def test_valid_mixed_content_pdf(self):
        validate_pdf_format(_load_sample("mixed_content.pdf"))

    def test_valid_empty_pdf(self):
        validate_pdf_format(_load_sample("empty.pdf"))

    def test_valid_special_chars_pdf(self):
        validate_pdf_format(_load_sample("special_chars.pdf"))

    def test_valid_table_content_pdf(self):
        validate_pdf_format(_load_sample("table_content.pdf"))

    def test_valid_spaces_only_pdf(self):
        validate_pdf_format(_load_sample("spaces_only.pdf"))

    def test_valid_image_content_pdf(self):
        validate_pdf_format(_load_sample("image_content.pdf"))

    def test_valid_in_memory_pdf(self):
        validate_pdf_format(_make_pdf_bytes("Hello"))

    # ── Invalid format ───────────────────────────────────────────────────────

    def test_raises_for_plain_text_file(self):
        with pytest.raises(InvalidPDFFormatError):
            validate_pdf_format(b"This is not a pdf")

    def test_raises_for_jpeg_file(self):
        fake_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        with pytest.raises(InvalidPDFFormatError):
            validate_pdf_format(fake_jpg)

    def test_raises_for_empty_bytes(self):
        with pytest.raises(InvalidPDFFormatError):
            validate_pdf_format(b"")

    def test_raises_for_truncated_pdf(self):
        corrupt = b"%PDF-1.4\n%%EOF"
        with pytest.raises(InvalidPDFFormatError):
            validate_pdf_format(corrupt)

    def test_raises_for_pdf_magic_with_garbage_body(self):
        garbage = b"%PDF-1.4\n" + b"\x00\x01\x02\x03" * 50
        with pytest.raises(InvalidPDFFormatError):
            validate_pdf_format(garbage)

# ---------------------------------------------------------------------------
# Integration-style: Validation Pipeline
# ---------------------------------------------------------------------------

class TestValidationPipeline:
    """
    Simulate the real service flow up to extraction:
        read bytes → validate format → compute checksum
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
        validate_pdf_format(raw)
        checksum = compute_checksum(raw)
        assert len(checksum) == 64

    def test_duplicate_detection_via_checksum(self):
        raw = _load_sample("simple_text.pdf")
        assert compute_checksum(raw) == compute_checksum(raw)

    def test_different_files_have_different_checksums(self):
        a = _load_sample("simple_text.pdf")
        b = _load_sample("multipage_text.pdf")
        assert compute_checksum(a) != compute_checksum(b)