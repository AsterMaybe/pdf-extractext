"""
Tests de los endpoints de fallback para errores de infraestructura de Traefik.

Traefik delega los errores 429 (rate limit) y 503 (circuit breaker) hacia estos
endpoints internos (middleware `errors` con `query=/traefik/errors/{status}`).
Estos tests verifican que cada ruta responde RFC 9457 con el `ProblemDetail`
estandarizado, en español, sin depender de Docker ni de MongoDB.
"""

from fastapi import status
from fastapi.testclient import TestClient

from app.main import app


def _assert_problem(response, status_code: int, expected_instance: str) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    for key in ("type", "title", "status", "detail", "instance"):
        assert key in body
    assert body["status"] == status_code
    assert body["detail"]
    assert body["instance"] == expected_instance


class TestTraefikErrorEndpoints:
    def test_429_rate_limited_returns_problem(self):
        with TestClient(app) as client:
            response = client.get("/traefik/errors/429")
        _assert_problem(response, status.HTTP_429_TOO_MANY_REQUESTS, "http://testserver/traefik/errors/429")
        assert "límite" in response.json()["detail"].lower()

    def test_503_service_unavailable_returns_problem(self):
        with TestClient(app) as client:
            response = client.get("/traefik/errors/503")
        _assert_problem(response, status.HTTP_503_SERVICE_UNAVAILABLE, "http://testserver/traefik/errors/503")
        assert "disponible" in response.json()["detail"].lower()