"""
Tests del health controller.

- `/health/live` es un liveness para Traefik: responde 200 sin depender de MongoDB.
- `/health` es un readiness: verifica el estado de MongoDB (200 ok / 503 problem+json).

El estado de la conexión se controla a través de `app.state.mongodb` (la
instancia creada en el lifespan), no de un singleton global.
"""

from unittest.mock import AsyncMock

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


class TestHealthLiveness:
    def test_live_returns_200_without_database(self):
        with TestClient(app) as client:
            response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestHealthReadiness:
    def test_health_returns_503_problem_when_database_offline(self):
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["status"] == status.HTTP_503_SERVICE_UNAVAILABLE
        assert body["detail"]

    def test_health_returns_200_when_database_online(self):
        with TestClient(app) as client:
            db = app.state.mongodb
            db._client = AsyncMock()
            db._client.admin.command = AsyncMock(return_value={"ok": 1})
            response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"
        assert response.json()["app"] == "ok"
        assert response.json()["database"] == "ok"