"""
Tests para HttpHealthRepository con cliente HTTP mockeado.

Verifica que el adaptador HTTP consulta correctamente el endpoint de readiness
del microservicio Go y convierte respuestas en booleanos, sin requerir
MongoDB ni microservicio Go real.
"""

import httpx
import pytest
import respx

from app.repositories.http_health_repo import HttpHealthRepository


class TestHttpHealthRepository:
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
        return HttpHealthRepository(
            base_url=self.BASE_URL,
            timeout=5.0,
            client=client,
        )

    @pytest.mark.asyncio
    async def test_ping_healthy(self, repo, mock_client):
        _, respx_mock = mock_client
        route = respx_mock.get("/health").mock(
            return_value=httpx.Response(
                200,
                json={"status": "ok", "app": "ok", "database": "ok"},
            )
        )

        result = await repo.ping()

        assert route.called
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_unhealthy_503(self, repo, mock_client):
        _, respx_mock = mock_client
        route = respx_mock.get("/health").mock(
            return_value=httpx.Response(
                503,
                json={
                    "type": "https://errors.example.com/service-unavailable",
                    "title": "Servicio No Disponible",
                    "status": 503,
                    "detail": "La base de datos no está disponible.",
                    "instance": "/health",
                },
            )
        )

        result = await repo.ping()

        assert route.called
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_unhealthy_404(self, repo, mock_client):
        _, respx_mock = mock_client
        route = respx_mock.get("/health").mock(
            return_value=httpx.Response(404)
        )

        result = await repo.ping()

        assert route.called
        assert result is False

    @pytest.mark.asyncio
    async def test_ping_network_error_returns_false(self, repo, mock_client):
        _, respx_mock = mock_client
        respx_mock.get("/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await repo.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_timeout_returns_false(self, repo, mock_client):
        _, respx_mock = mock_client
        respx_mock.get("/health").mock(
            side_effect=httpx.TimeoutException("Request timeout")
        )

        result = await repo.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_unexpected_error_returns_false(self, repo, mock_client):
        _, respx_mock = mock_client
        respx_mock.get("/health").mock(
            side_effect=RuntimeError("Unexpected error")
        )

        result = await repo.ping()

        assert result is False