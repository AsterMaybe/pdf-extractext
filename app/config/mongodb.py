"""
Gestión de la conexión a MongoDB.
La conexión se abre al arrancar la app y se cierra al apagarse,
aprovechando los eventos de ciclo de vida de FastAPI (lifespan).

"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from app.config.config import settings


class MongoDB:
    """Encapsula el cliente y expone la colección de documentos."""

    client: AsyncIOMotorClient | None = None

    def connect(self) -> None:
        """Abre la conexión al servidor MongoDB."""
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)

    def disconnect(self) -> None:
        """Cierra la conexión al servidor MongoDB."""
        if self.client:
            self.client.close()

    @property
    def collection(self) -> AsyncIOMotorCollection:
        """
        Devuelve la colección de documentos.
        Lanza un error claro si se usa antes de conectar.
        """
        if not self.client:
            raise RuntimeError("MongoDB no está conectado. Llamá a connect() primero.")
        return self.client[settings.MONGODB_DB_NAME][settings.MONGODB_COLLECTION]


# Instancia global: importar siempre desde acá.
mongodb = MongoDB()
