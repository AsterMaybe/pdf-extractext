"""
Tests de integración: DocumentService funcionando a través del adaptador HTTP.

Verifica que la lógica de negocio (DocumentService) sigue funcionando correctamente
con HttpDocumentRepository y sin una base de datos conectada directamente.
Estos tests no requieren MongoDB ni microservicio Go real - usan respx para mockear HTTP.
"""

import httpx
import pytest
import respx

from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.domain.exceptions import DocumentAlreadyExistsError
from app.domain.pagination import PageQuery
from app.repositories.http_document_repo import HttpDocumentRepository
from app.repositories.http_health_repo import HttpHealthRepository
from app.services.document_service import DocumentService
from app.services.health_service import HealthService


class TestDocumentServiceViaHttpAdapter:
    """Tests de DocumentService usando HttpDocumentRepository (mock HTTP)."""

    BASE_URL = "http://test-db-service:8080"

    @pytest.fixture
    def mock_clients(self):
        """Cliente HTTP mockeado con respx para ambos repositorios."""
        with respx.mock(assert_all_called=False) as respx_mock:
            doc_client = httpx.AsyncClient(base_url=self.BASE_URL)
            health_client = httpx.AsyncClient(base_url=self.BASE_URL)
            yield doc_client, health_client, respx_mock

    @pytest.fixture
    def doc_repo(self, mock_clients):
        doc_client, _, _ = mock_clients
        return HttpDocumentRepository(
            base_url=self.BASE_URL,
            timeout=5.0,
            client=doc_client,
        )

    @pytest.fixture
    def health_repo(self, mock_clients):
        _, health_client, _ = mock_clients
        return HttpHealthRepository(
            base_url=self.BASE_URL,
            timeout=5.0,
            client=health_client,
        )

    @pytest.fixture
    def document_service(self, doc_repo):
        # Usar un PDF processor fake simple
        from tests.test_document_service import _FakeProcessor
        return DocumentService(repo=doc_repo, pdf_processor=_FakeProcessor())

    @pytest.fixture
    def health_service(self, health_repo):
        return HealthService(health_repo=health_repo)

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
    async def test_process_and_store_document_success(
        self, document_service, mock_clients, sample_doc_create, sample_doc_response
    ):
        """El servicio puede crear documentos vía adaptador HTTP."""
        _, _, respx_mock = mock_clients

        # Mock: pre-check (GET /documents) retorna vacío (no existe)
        respx_mock.get("/api/v1/documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        # Mock: create (POST /documents) retorna documento creado
        respx_mock.post("/api/v1/documents").mock(
            return_value=httpx.Response(201, json=sample_doc_response.model_dump(mode="json"))
        )

        result = await document_service.process_and_store_document(b"%PDF-data", "input.pdf")

        assert result.id == sample_doc_response.id
        assert result.filename == sample_doc_response.filename
        assert result.checksum == sample_doc_response.checksum

    @pytest.mark.asyncio
    async def test_process_and_store_document_duplicate_precheck(
        self, document_service, mock_clients, sample_doc_create
    ):
        """Pre-check via HTTP detecta duplicado antes de crear."""
        _, _, respx_mock = mock_clients

        # Mock: pre-check retorna documento existente
        existing = {"id": "other-id", "checksum": "fake-checksum", "filename": "other.pdf"}
        respx_mock.get("/api/v1/documents").mock(
            return_value=httpx.Response(200, json=[existing])
        )

        with pytest.raises(DocumentAlreadyExistsError) as exc_info:
            await document_service.process_and_store_document(b"%PDF-data", "input.pdf")

        assert exc_info.value.code == "DOCUMENT_ALREADY_EXISTS"

    @pytest.mark.asyncio
    async def test_process_and_store_document_race_condition(
        self, document_service, mock_clients, sample_doc_create, sample_doc_response
    ):
        """Carrera TOCTOU: pre-check pasa pero create falla por duplicado (409)."""
        _, _, respx_mock = mock_clients

        # Mock: pre-check retorna vacío
        respx_mock.get("/api/v1/documents").mock(
            return_value=httpx.Response(200, json=[])
        )
        # Mock: create retorna 409 conflict
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
            await document_service.process_and_store_document(b"%PDF-data", "input.pdf")

        assert exc_info.value.code == "DOCUMENT_ALREADY_EXISTS"

    @pytest.mark.asyncio
    async def test_list_documents(self, document_service, mock_clients, sample_doc_response):
        """Listado de documentos via HTTP."""
        _, _, respx_mock = mock_clients

        respx_mock.get("/api/v1/documents").mock(
            return_value=httpx.Response(200, json=[sample_doc_response.model_dump(mode="json")])
        )

        result = await document_service.list_documents(PageQuery(skip=0, limit=10))

        assert len(result) == 1
        assert result[0].id == sample_doc_response.id

    @pytest.mark.asyncio
    async def test_get_by_id(self, document_service, mock_clients, sample_doc_response):
        """Obtener documento por ID via HTTP."""
        _, _, respx_mock = mock_clients
        doc_id = "60d5ecb8b392d70008051234"

        respx_mock.get(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(200, json=sample_doc_response.model_dump(mode="json"))
        )

        result = await document_service.get_by_id(doc_id)

        assert result.id == doc_id

    @pytest.mark.asyncio
    async def test_update_document(self, document_service, mock_clients, sample_doc_response):
        """Actualización parcial (PATCH) via HTTP."""
        _, _, respx_mock = mock_clients
        doc_id = "60d5ecb8b392d70008051234"

        updated = sample_doc_response.model_copy()
        updated.filename = "renombrado.pdf"
        respx_mock.patch(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(200, json=updated.model_dump(mode="json"))
        )

        update = DocumentUpdate(filename="renombrado.pdf")
        result = await document_service.update_document(doc_id, update)

        assert result.filename == "renombrado.pdf"

    @pytest.mark.asyncio
    async def test_delete_document(self, document_service, mock_clients):
        """Eliminación via HTTP."""
        _, _, respx_mock = mock_clients
        doc_id = "60d5ecb8b392d70008051234"

        respx_mock.delete(f"/api/v1/documents/{doc_id}").mock(
            return_value=httpx.Response(204)
        )

        await document_service.delete(doc_id)
        # No debe lanzar

    @pytest.mark.asyncio
    async def test_health_service_readiness_via_http(self, health_service, mock_clients):
        """HealthService verifica readiness via HTTP al microservicio Go."""
        _, _, respx_mock = mock_clients

        # Healthy
        respx_mock.get("/health").mock(
            return_value=httpx.Response(200, json={"status": "ok", "app": "ok", "database": "ok"})
        )

        result = await health_service.database_is_healthy()
        assert result is True

        # Unhealthy
        respx_mock.get("/health").mock(
            return_value=httpx.Response(503, json={"detail": "DB down"})
        )

        result = await health_service.database_is_healthy()
        assert result is False