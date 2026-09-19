"""
Unit tests para app/infrastructure/remote_pdf_processor.py.

Cubren el adaptador de `IPDFProcessor` que delega la extracción al
microservicio Go, sin levantar red real (httpx se parchea por completo).
"""

import hashlib
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.domain.exceptions import InvalidPDFFormatError, PDFProcessingError
from app.infrastructure.remote_pdf_processor import (
    RemotePdfProcessor,
    compute_checksum,
    validate_pdf_format,
)

SERVICE_URL = "http://api:8080"
PDF_BYTES = b"%PDF-1.7 fake content"
UPLOAD_FILES = {
    "file": ("document.pdf", PDF_BYTES, "application/pdf"),
}


class TestValidateFormat:
    def test_accepts_pdf_magic_bytes(self):
        validate_pdf_format(b"%PDF-1.7 data")

    def test_rejects_non_pdf_bytes(self):
        with pytest.raises(InvalidPDFFormatError):
            validate_pdf_format(b"not a pdf")


class TestComputeChecksum:
    def test_returns_sha256_hexdigest(self):
        assert compute_checksum(b"hola") == hashlib.sha256(b"hola").hexdigest()


class TestRemotePdfProcessorExtractText:
    def _processor(self):
        return RemotePdfProcessor(base_url=SERVICE_URL)

    @pytest.mark.asyncio
    async def test_sends_multipart_upload_and_returns_text(self):
        with patch(
            "app.infrastructure.remote_pdf_processor.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = mock_client_cls.return_value.__aenter__.return_value
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                "filename": "document.pdf",
                "extension": "pdf",
                "mime_type": "application/pdf",
                "text": "contenido extraído",
            }
            mock_client.post.return_value = mock_response

            result = await self._processor().extract_text(PDF_BYTES)

        mock_client.post.assert_called_once_with(
            f"{SERVICE_URL}/api/v1/extract", files=UPLOAD_FILES
        )
        assert result == "contenido extraído"

    @pytest.mark.asyncio
    async def test_unreachable_service_becomes_pdf_processing_error(self):
        with patch(
            "app.infrastructure.remote_pdf_processor.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = mock_client_cls.return_value.__aenter__.return_value
            mock_client.post.side_effect = httpx.ConnectError("no route to host")

            with pytest.raises(PDFProcessingError):
                await self._processor().extract_text(PDF_BYTES)

    @pytest.mark.parametrize("status", [400, 422])
    @pytest.mark.asyncio
    async def test_rejected_pdf_becomes_invalid_pdf_format_error(self, status):
        with patch(
            "app.infrastructure.remote_pdf_processor.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = mock_client_cls.return_value.__aenter__.return_value
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "client error",
                request=httpx.Request("POST", f"{SERVICE_URL}/api/v1/extract"),
                response=httpx.Response(
                    status, request=httpx.Request("POST", f"{SERVICE_URL}/api/v1/extract")
                ),
            )
            mock_client.post.return_value = mock_response

            with pytest.raises(InvalidPDFFormatError):
                await self._processor().extract_text(PDF_BYTES)

    @pytest.mark.asyncio
    async def test_other_http_error_becomes_pdf_processing_error(self):
        with patch(
            "app.infrastructure.remote_pdf_processor.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = mock_client_cls.return_value.__aenter__.return_value
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "server error",
                request=httpx.Request("POST", f"{SERVICE_URL}/api/v1/extract"),
                response=httpx.Response(503, request=httpx.Request("POST", f"{SERVICE_URL}/api/v1/extract")),
            )
            mock_client.post.return_value = mock_response

            with pytest.raises(PDFProcessingError):
                await self._processor().extract_text(PDF_BYTES)