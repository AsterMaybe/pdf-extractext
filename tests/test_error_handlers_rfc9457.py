"""
Tests de integración de los handlers de error RFC 9457.

Verifica que todos los errores responden en `application/problem+json` con el
cuerpo estandarizado, y que el comportamiento observable se conserva tras la
consolidación de los handlers duplicados.
"""

from fastapi import status
from fastapi.testclient import TestClient

from app.api.dependencies import get_document_repo
from app.domain.exceptions import DocumentNotFoundError
from app.main import app


def _make_dummy_pdf() -> bytes:
    """Genera un PDF válido en memoria para las pruebas."""
    import io

    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Texto de prueba")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class _StubRepo:
    """Doble de repositorio: no llama a MongoDB para que la DI no reviente."""

    async def exists_by_checksum(self, checksum: str) -> bool:
        return False

    async def get_by_id(self, doc_id: str):
        raise DocumentNotFoundError(doc_id)

    async def create(self, doc):
        raise NotImplementedError


def _assert_problem(response, status_code: int) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    for key in ("type", "title", "status", "detail"):
        assert key in body
    assert body["status"] == status_code
    assert body["title"]


class TestRfc9457Handlers:
    def test_unknown_route_returns_404_problem(self):
        with TestClient(app) as client:
            response = client.get("/ruta/inexistente")
        _assert_problem(response, status.HTTP_404_NOT_FOUND)

    def test_validation_error_returns_422_problem_with_errors(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with TestClient(app) as client:
                response = client.post("/api/v1/documents/upload")
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert "errors" in response.json()

    def test_document_not_found_returns_404_problem(self):
        class NotFoundRepo(_StubRepo):
            async def get_by_id(self, doc_id: str):
                raise DocumentNotFoundError(doc_id)

        app.dependency_overrides[get_document_repo] = lambda: NotFoundRepo()
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/documents/60d5ecb8b392d70008051234")
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_404_NOT_FOUND)

    def test_duplicate_document_returns_409_problem(self):
        class DuplicateRepo(_StubRepo):
            async def exists_by_checksum(self, checksum: str) -> bool:
                return True

        app.dependency_overrides[get_document_repo] = lambda: DuplicateRepo()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("dup.pdf", _make_dummy_pdf(), "application/pdf")},
                )
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_409_CONFLICT)

    def test_oversized_file_returns_400_problem(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("big.pdf", b"0" * (5 * 1024 * 1024 + 1), "application/pdf")},
                )
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_400_BAD_REQUEST)

    def test_invalid_pdf_format_returns_400_problem(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("doc.txt", b"This is not a pdf", "application/octet-stream")},
                )
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_400_BAD_REQUEST)

    def test_unhandled_error_returns_500_problem(self):
        class ExplodingRepo(_StubRepo):
            async def get_by_id(self, doc_id: str):
                raise RuntimeError("boom")

        app.dependency_overrides[get_document_repo] = lambda: ExplodingRepo()
        # ServerErrorMiddleware re-raisea tras enviar la 500; lo desactivamos
        # para poder inspeccionar la respuesta problem+json.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/documents/60d5ecb8b392d70008051234")
        app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_500_INTERNAL_SERVER_ERROR)
        assert "inesperado" in response.json()["detail"].lower()