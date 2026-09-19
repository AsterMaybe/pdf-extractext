"""
Gestión de la conexión a MongoDB.

La conexión se abre al arrancar la app y se cierra al apagarse, aprovechando
los eventos de ciclo de vida de FastAPI (lifespan).

La clase no conoce configuración de la aplicación (SRP): la URL y el timeout se
inyectan por parámetro en `connect()`, y las colecciones se obtienen por nombre
vía `get_collection()`, sin fijar un dominio de negocio concreto.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

logger = logging.getLogger(__name__)


class MongoDB:
    """Encapsula el cliente de MongoDB e inyecta sus dependencias por parámetro."""

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None

    async def connect(self, db_url: str, timeout_ms: int = 5000) -> None:
        """Abre la conexión al servidor MongoDB."""
        client = AsyncIOMotorClient(db_url, serverSelectionTimeoutMS=timeout_ms)
        try:
            logger.info("Connecting to MongoDB...")
            await client.admin.command("ping")
        except Exception:
            logger.exception("MongoDB connection failed")
            client.close()
            raise RuntimeError("No se pudo conectar a MongoDB.")

        self._client = client
        logger.info("MongoDB connected successfully.")

    async def disconnect(self) -> None:
        """Cierra la conexión al servidor MongoDB."""
        if self._client is not None:
            logger.info("Closing MongoDB connection...")
            self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncIOMotorClient | None:
        """Cliente activo de MongoDB (None si aún no se conectó)."""
        return self._client

    def get_collection(self, db_name: str, col_name: str) -> AsyncIOMotorCollection:
        """Devuelve una colección por nombre, sin acoplarse a un dominio."""
        if self._client is None:
            raise RuntimeError("MongoDB no está conectado. Llamá a connect() primero.")
        return self._client[db_name][col_name]