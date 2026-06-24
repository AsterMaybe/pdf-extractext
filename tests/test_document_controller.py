"""
Tests de integración para el controlador de documentos.
Usamos TestClient de FastAPI y sobrescribimos la dependencia del repositorio
para simular las respuestas de la base de datos sin conectarnos a ella.
"""

import io
from unittest.mock import AsyncMock

import fitz
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.controllers.document_controller import get_document_repo
from app.domain.document import DocumentResponse
from app.main import app


# ── Helpers ───────────────────────────────────────────────────────────────

def make_dummy_pdf() -> bytes:
    """Genera un PDF válido en memoria para las pruebas."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Texto de prueba de integración")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repo():
    """Crea un mock asíncrono para el repositorio."""
    return AsyncMock()


@pytest.fixture
def client(mock_repo):
    """
    Cliente de pruebas de FastAPI con el repositorio mockeado.
    Esto intercepta `Depends(get_document_repo)` en las rutas.
    """
    app.dependency_overrides[get_document_repo] = lambda: mock_repo
    with TestClient(app) as test_client:
        yield test_client
    # Limpiar overrides después del test
    app.dependency_overrides.clear()


@pytest.fixture
def sample_doc_response():
    """Un modelo de respuesta simulado."""
    return DocumentResponse(
        id="60d5ecb8b392d70008051234",
        filename="dummy.pdf",
        text_content="Texto de prueba de integración",
        checksum="fakechecksum1234567890",
        file_size_bytes=1024,
        created_at="2026-05-20T10:00:00Z"
    )


# ── Tests ────────────────────────────────────────────────────────────────

class TestDocumentController:

    def test_upload_document_success(self, client, mock_repo, sample_doc_response):
        """Caso feliz: Se sube un PDF nuevo y se persiste."""
        # 1. Configurar los mocks
        mock_repo.exists_by_checksum.return_value = False
        mock_repo.create.return_value = sample_doc_response

        # 2. Ejecutar la petición
        pdf_bytes = make_dummy_pdf()
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("dummy.pdf", pdf_bytes, "application/pdf")}
        )

        # 3. Validar resultados
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["filename"] == "dummy.pdf"
        assert data["id"] == sample_doc_response.id

        # Verificar que el controlador llamó a los métodos correctos
        mock_repo.exists_by_checksum.assert_awaited_once()
        mock_repo.create.assert_awaited_once()

    def test_upload_document_duplicate_returns_409(self, client, mock_repo):
        """Si el checksum ya existe, debe retornar 409 Conflict."""
        # Simular que el repositorio encuentra el documento
        mock_repo.exists_by_checksum.return_value = True

        pdf_bytes = make_dummy_pdf()
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("dummy.pdf", pdf_bytes, "application/pdf")}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "ya fue cargado previamente" in response.json()["detail"]

        # Confirmar que nunca intentó guardar
        mock_repo.create.assert_not_called()

    def test_list_documents(self, client, mock_repo, sample_doc_response):
        """Listar todos los documentos devuelve un array (GET /)."""
        mock_repo.get_all.return_value = [sample_doc_response]

        response = client.get("/api/v1/documents/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == sample_doc_response.id

    def test_get_document_by_id(self, client, mock_repo, sample_doc_response):
        """Obtener un documento específico por ID."""
        mock_repo.get_by_id.return_value = sample_doc_response

        response = client.get(f"/api/v1/documents/{sample_doc_response.id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == sample_doc_response.id
        mock_repo.get_by_id.assert_awaited_once_with(sample_doc_response.id)

    def test_update_document(self, client, mock_repo, sample_doc_response):
        """Actualizar un documento exitosamente."""
        mock_repo.update.return_value = sample_doc_response

        response = client.patch(
            f"/api/v1/documents/{sample_doc_response.id}",
            json={"filename": "nuevo_nombre.pdf"}
        )

        assert response.status_code == status.HTTP_200_OK
        mock_repo.update.assert_awaited_once()

    def test_delete_document(self, client, mock_repo, sample_doc_response):
        """Eliminar un documento retorna 204 sin contenido."""
        # delete no retorna nada en el repositorio
        mock_repo.delete.return_value = None

        response = client.delete(f"/api/v1/documents/{sample_doc_response.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_repo.delete.assert_awaited_once_with(sample_doc_response.id)

    def test_upload_document_exceeds_size_limit(self, client, mock_repo):
        """Si el documento supera los 5MB, debe retornar 400 Bad Request sin intentar guardarlo."""
        # Simulamos un archivo de exactamente 5 MB + 1 byte
        oversized_pdf_bytes = b"0" * (5 * 1024 * 1024 + 1)

        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("large_dummy.pdf", oversized_pdf_bytes, "application/pdf")}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "supera el límite" in response.json()["detail"].lower()
