"""
Fixtures globales de la suite.

Neutraliza la conexión a MongoDB para que todos los tests corran de forma
hermética (sin necesidad de una instancia real levantada), en línea con la
intención del repo de mockear la base de datos en los tests unitarios e
integración.
"""
import pytest


@pytest.fixture(autouse=True)
def _neutralize_mongodb(monkeypatch):
    """Desactiva connect/disconnect del singleton de MongoDB y deja el cliente en None."""
    from app.config.mongodb import mongodb

    async def _noop_connect() -> None:
        return None

    async def _noop_disconnect() -> None:
        return None

    monkeypatch.setattr(mongodb, "connect", _noop_connect)
    monkeypatch.setattr(mongodb, "disconnect", _noop_disconnect)
    monkeypatch.setattr(mongodb, "client", None)