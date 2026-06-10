"""
Gestión de la conexión a MongoDB.
La conexión se abre al arrancar la app y se cierra al apagarse,
aprovechando los eventos de ciclo de vida de FastAPI (lifespan).
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from app.config.config import settings
from app.config.logging_config import setup_logging

logger = logging.getLogger(__name__)

class MongoDB:
    """
    Encapsula el cliente y expone la colección de documentos.
    """
    client: AsyncIOMotorClient | None = None


    async def connect(self) -> None:
        """
        Abre la conexión al servidor MongoDB.
        """
        self.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)

        try:
            logger.info("Connecting to MongoDB...")
            await self.client.admin.command("ping")
               
        except Exception:
            logger.error("MongoDB connection failed")
            self.client = None
            raise RuntimeError("No se pudo conectar a MongoDB.")

        logger.info("MongoDB connected successfully.")


    def disconnect(self) -> None:
        """
        Cierra la conexión al servidor MongoDB.
        """
        if self.client is not None:
            logger.info("Closing MongoDB connection...")
            self.client.close()


    @property
    def collection(self) -> AsyncIOMotorCollection:
        """
        Devuelve la colección de documentos.
        """
        if self.client is None:
            raise RuntimeError("MongoDB no está conectado. Llamá a connect() primero.")
        return self.client[settings.MONGODB_DB_NAME][settings.MONGODB_COLLECTION]


# Instancia global: importar siempre desde acá.
mongodb = MongoDB()
