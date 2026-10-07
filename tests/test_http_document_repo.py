"""
Tests para HttpDocumentRepository con cliente HTTP mockeado.

Verifica que el adaptador HTTP convierte correctamente respuestas y errores
en modelos y excepciones de dominio, sin requerir MongoDB ni microservicio Go real.
"""

import httpx
import pytest
import respx

from app.domain.document import DocumentCreate, DocumentResponse
from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    InvalidDocumentIdError,
    FileSizeExceededError,
    PDFProcessingError,
)
from app.domain.pagination import PageQuery
from app.repositories.http_document_repo import HttpDocumentRepository


class TestHttpDocumentRepository:
    BASE_URL = "http://test-db-service:8080"

    @pytest.fixture
    def mock_client(self):
        """Cliente HTTP mockeado con respx."""
        with respx.mock(assert_all_called=False) as respx_mock:
            client = httpx.AsyncClient(base_url=self.BASE_URL)
            yield client, respx_mock

    @pytest.fixture
    def repo(self, mock_client):
        client, _ = mock_client
        return HttpDocumentRepository(
            base_url=self.BASE_URL,
            timeout=5.0,
            client=client,
        )

    @pytest.fixture
    def sample_doc_create(self):
        return DocumentCreate(
            filename="test.pdf",
            text_content="Contenido de prueba",
            checksum="abcd1234efgh5678",
            file_size_bytes=1024,
        )

    @pytest.fixture
    def sample_doc_response(self):
        return DocumentResponse(
            id="60d5ecb8b392d70008051234",
            filename="test.pdf",
            text_content="Contenido de prueba",
            checksum="abcd1234efgh5678",
            file_size_bytes=1024,
            created_at="2026-05-20T10:00:00Z",
        )

    @pytest.mark.asyncio
    async def test_create_success(self, repo, mock_client, sample_doc_create, sample_doc_response):
        _, respx_mock = mock_client
        route = respx_mock.post("/api/v1/documents").mock(
            return_value=httpx.Response(201, json=sample_doc_response.model_dump(mode="json"))
        )

        result = await repo.create(sample_doc_create)

        assert route.called
        assert result.id == sample_doc_response.id
        assert result.filename == sample_doc_response.filename
        assert result.checksum == sample_doc_response.checksum

    @pytest.mark.asyncio
    async def test_create_duplicate_raises_domain_error(self, repo, mock_client, sample_doc_create):
        _, respx_mock = mock_client
        respx_mock.post("/api/v1/documents").mock(
            return_value=httpx.Response(
                409,
                json={
                    "type": "https://errors.example.com/document-already-exists",
                    "title": "Documento duplicado",
                    "status": 409,
                    "detail": "El documento ya fue cargado previamente.",
                    "instance": "/api/v1/documents",
                },
            )
        )

        with pytest.raises(DocumentAlreadyExistsError) as exc_info:
            await repo.create(sample_doc_create)

        assert exc_info.value.code == "DOCUMENT_ALREADY_EXISTS"
        assert "abcd1234efgh5678" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_invalid_id_raises_domain_error(self, repo, mock_client, sample_doc_create):
        _, respx_mock = mock_client
        respx_mock.post("/api/v1/documents").mock(
            return_value=httpx.Response(
                400,
                json={
                    "type": "https://errors.example.com/invalid-document-id",
                    "title": "ID de documento inválido",
                    "status": 400,
                    "detail": "El identificador proporcionado no tiene un formato válido.",
                    "instance": "/api/v1/documents",
                },
            )
        )

        with pytest.raises(InvalidDocumentIdError) as exc_info:
            await repo.create(sample_doc_create)

        assert exc_info.value.code == "INVALID_DOCUMENT_ID"

    @pytest.mark.asyncio
    async def test_create_file_too_large_raises_domain_error(self, repo, mock_client, sample_doc_create):
        _, respx_mock = mock_client
        respx_mock.post("/api/v1/documents").mock(
            return_value=httpx.Response(
                413,
                json={
                    "type": "https://errors.example.com/too-large",
                    "title": "Archivo demasiado grande",
                    "status": 413,
                    "detail": "El archivo subido supera el tamaño máximo permitido.",
                    "instance": "/api/v1/documents",
                },
            )
        )

        with pytest.raises(FileSizeExceededError):
            await repo.create(sample_doc_create)

    @pytest.mark.asyncio
    async def test_create_service_unavailable_raises_domain_error(self, repo, mock_client, sample_doc_create):
        _, respx_mock = mock_client
        respx_mock.post("/api/v1/documents").mock(
            return_value=httpx.Response(
                503,
                json={
                    "type": "https://errors.example.com/service-unavailable",
                    "title": "Servicio No Disponible",
                    "status": 503,
                    "detail": "Una dependencia requerida está actualmente inaccesible.",
                    "instance": "/api/v1/documents",
                },
            )
        )

        with pytest.raises(PDFProcessingError):
            await repo.create(sample_doc_create)

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repo, mock_client, sample_doc_response):
        _, respx_mock = mock_client
        doc_id = "60d5ecb8b392d70008051234"
        route = respx_mock.get(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(200, json=sample_doc_response.model_dump(mode="json"))
        )

        result = await repo.get_by_id(doc_id)

        assert route.called
        assert result.id == doc_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_raises_domain_error(self, repo, mock_client):
        _, respx_mock = mock_client
        doc_id = "60d5ecb8b392d70008051234"
        respx_mock.get(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(
                404,
                json={
                    "type": "https://errors.example.com/document-not-found",
                    "title": "Documento no encontrado",
                    "status": 404,
                    "detail": "El documento solicitado no existe.",
                    "instance": f"/api/v1/documents/{doc_id}",
                },
            )
        )

        with pytest.raises(DocumentNotFoundError) as exc_info:
            await repo.get_by_id(doc_id)

        assert exc_info.value.code == "DOCUMENT_NOT_FOUND"
        assert doc_id in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_all_success(self, repo, mock_client, sample_doc_response):
        _, respx_mock = mock_client
        route = respx_mock.get("/api/v1/documents").mock(
            return_value=httpx.Response(200, json=[sample_doc_response.model_dump(mode="json")])
        )

        result = await repo.get_all(PageQuery(skip=0, limit=10))

        assert route.called
        assert len(result) == 1
        assert result[0].id == sample_doc_response.id

    @pytest.mark.asyncio
    async def test_update_success(self, repo, mock_client, sample_doc_response):
        _, respx_mock = mock_client
        doc_id = "60d5ecb8b392d70008051234"
        updated = sample_doc_response.model_copy()
        updated.filename = "renombrado.pdf"

        route = respx_mock.patch(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(200, json=updated.model_dump(mode="json"))
        )

        changes = {"filename": "renombrado.pdf"}
        result = await repo.update(doc_id, changes)

        assert route.called
        assert result.filename == "renombrado.pdf"

    @pytest.mark.asyncio
    async def test_update_not_found_raises_domain_error(self, repo, mock_client):
        _, respx_mock = mock_client
        doc_id = "60d5ecb8b392d70008051234"
        respx_mock.patch(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(
                404,
                json={
                    "type": "https://errors.example.com/document-not-found",
                    "title": "Documento no encontrado",
                    "status": 404,
                    "detail": "El documento solicitado no existe.",
                    "instance": f"/api/v1/documents/{doc_id}",
                },
            )
        )

        with pytest.raises(DocumentNotFoundError):
            await repo.update(doc_id, {"filename": "x.pdf"})

    @pytest.mark.asyncio
    async def test_delete_success(self, repo, mock_client):
        _, respx_mock = mock_client
        doc_id = "60d5ecb8b392d70008051234"
        route = respx_mock.delete(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(204)
        )

        await repo.delete(doc_id)

        assert route.called

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_domain_error(self, repo, mock_client):
        _, respx_mock = mock_client
        doc_id = "60d5ecb8b392d70008051234"
        respx_mock.delete(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(
                404,
                json={
                    "type": "https://errors.example.com/document-not-found",
                    "title": "Documento no encontrado",
                    "status": 404,
                    "detail": "El documento solicitado no existe.",
                    "instance": f"/api/v1/documents/{doc_id}",
                },
            )
        )

        with pytest.raises(DocumentNotFoundError):
            await repo.delete(doc_id)

    @pytest.mark.asyncio
    async def test_ensure_indexes_noop(self, repo):
        # No debe lanzar, es no-op en modo HTTP
        await repo.ensure_indexes()

    @pytest.mark.asyncio
    async def test_network_error_raises_domain_error(self, repo, mock_client, sample_doc_create):
        _, respx_mock = mock_client
        respx_mock.post("/api/v1/documents").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(InvalidDocumentIdError):
            await repo.create(sample_doc_create)