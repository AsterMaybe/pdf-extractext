"""Tests del liveness y readiness del orquestador."""

from fastapi import status
from fastapi.testclient import TestClient

from app.api.dependencies import get_health_service
from app.main import app


class _StubHealthService:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    async def database_is_healthy(self) -> bool:
        return self.healthy


class TestHealthLiveness:
    def test_live_returns_200_without_database(self):
        with TestClient(app) as client:
            response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestHealthReadiness:
    def test_health_returns_503_problem_when_database_offline(self):
        app.dependency_overrides[get_health_service] = lambda: _StubHealthService(False)
        try:
            with TestClient(app) as client:
                response = client.get("/health")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["status"] == status.HTTP_503_SERVICE_UNAVAILABLE
        assert body["detail"]

    def test_health_returns_200_when_database_online(self):
        app.dependency_overrides[get_health_service] = lambda: _StubHealthService(True)
        try:
            with TestClient(app) as client:
                response = client.get("/health")
        finally:
            app.dependency_overrides.clear()
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"
        assert response.json()["app"] == "ok"
        assert response.json()["database"] == "ok"