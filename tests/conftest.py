"""
Fixtures globales de la suite.

Neutraliza el ciclo de vida de MongoDB para que todos los tests corran de forma
hermética (sin necesidad de una instancia real levantada). Al no existir un
singleton global, se parchean los métodos de clase `connect`/`disconnect` para
que el lifespan de FastAPI pueda crear la instancia sin efectos de red, y
`get_collection` para que el arranque (creación de índices) resuelva una
colección simulada.
"""
from unittest.mock import AsyncMock

import pytest

from app.config.mongodb import MongoDB


@pytest.fixture(autouse=True)
def _neutralize_mongodb(monkeypatch):
    """Convierte `connect`/`disconnect` de MongoDB en no-ops para los tests."""

    async def _noop_connect(self, db_url: str, timeout_ms: int = 5000) -> None:
        return None

    async def _noop_disconnect(self) -> None:
        return None

    def _fake_get_collection(self, db_name: str, col_name: str):
        """Devuelve una colección simulada para el arranque/lifespan."""
        return AsyncMock()

    monkeypatch.setattr(MongoDB, "connect", _noop_connect)
    monkeypatch.setattr(MongoDB, "disconnect", _noop_disconnect)
    monkeypatch.setattr(MongoDB, "get_collection", _fake_get_collection)