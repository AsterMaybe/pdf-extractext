"""
Adaptador concreto de `IHealthRepository` sobre el driver de MongoDB.

Aísla el detalle tecnológico (`AsyncIOMotorClient`, el ping a `admin`) del
servicio de salud: la capa de aplicación sólo conoce el puerto `ping()`.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.services.ports import IHealthRepository

logger = logging.getLogger(__name__)


class MongoHealthRepository(IHealthRepository):
    """Verifica disponibilidad de MongoDB; nunca lanza, devuelve un booleano."""

    def __init__(self, client: AsyncIOMotorClient | None) -> None:
        self._client = client

    async def ping(self) -> bool:
        if self._client is None:
            logger.error("Health check falló: el cliente de MongoDB no está inicializado.")
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            logger.exception("Health check falló al hacer ping a MongoDB")
            return False