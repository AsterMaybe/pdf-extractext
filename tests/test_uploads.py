"""
Unit tests para app/api/uploads.py (read_upload_bytes).

El adapter de presentación convierte `UploadFile` en `bytes` leyendo por chunks
y abortando temprano si el archivo supera el tamaño máximo configurado.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.uploads import read_upload_bytes
from app.domain.exceptions import FileSizeExceededError


class TestReadUploadBytes:

    @pytest.mark.asyncio
    async def test_returns_bytes_from_upload_file(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(side_effect=[b"pdf bytes here", b""])
        result = await read_upload_bytes(mock_upload)
        assert result == b"pdf bytes here"

    @pytest.mark.asyncio
    async def test_reads_in_chunks_until_eof(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", b""])
        result = await read_upload_bytes(mock_upload)
        assert result == b"chunk1chunk2"

    @pytest.mark.asyncio
    async def test_read_called_with_chunk_size(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(side_effect=[b"x", b""])
        await read_upload_bytes(mock_upload)
        first_args = mock_upload.read.await_args_list[0].args
        assert first_args == (1024 * 1024,)

    @pytest.mark.asyncio
    async def test_returns_empty_bytes_for_empty_upload(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(side_effect=[b""])
        result = await read_upload_bytes(mock_upload)
        assert result == b""

    @pytest.mark.asyncio
    async def test_raises_when_file_exceeds_max_size(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(side_effect=[b"a" * (1024 * 1024), b"a", b""])
        with (
            patch("app.api.uploads.settings") as mock_settings,
            pytest.raises(FileSizeExceededError) as exc_info,
        ):
            mock_settings.UPLOAD_CHUNK_SIZE_MB = 1
            mock_settings.PDF_MAX_SIZE_MB = 1
            await read_upload_bytes(mock_upload)
        assert "1 MB" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exactly_at_max_size_does_not_raise(self):
        mock_upload = AsyncMock()
        mock_upload.read = AsyncMock(side_effect=[b"a" * (1024 * 1024), b""])
        with patch("app.api.uploads.settings") as mock_settings:
            mock_settings.UPLOAD_CHUNK_SIZE_MB = 1
            mock_settings.PDF_MAX_SIZE_MB = 1
            result = await read_upload_bytes(mock_upload)
        assert len(result) == 1024 * 1024