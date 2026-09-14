"""
Tests del health controller.

- `/health/live` es un liveness para Traefik: responde 200 sin depender de MongoDB.
- `/health` es un readiness: verifica el estado de MongoDB (200 ok / 503 error).
"""

from unittest.mock import AsyncMock

from fastapi import status
from fastapi.testclient import TestClient

from app.config.mongodb import mongodb
from app.main import app


class TestHealthLiveness:
    def test_live_returns_200_without_database(self):
        mongodb.client = None
        with TestClient(app) as client:
            response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestHealthReadiness:
    def test_health_returns_503_when_database_offline(self):
        mongodb.client = None
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["database"] == "error"

    def test_health_returns_200_when_database_online(self):
        mongodb.client = AsyncMock()
        mongodb.client.admin.command = AsyncMock(return_value={"ok": 1})
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"
        assert response.json()["app"] == "ok"
        assert response.json()["database"] == "ok"