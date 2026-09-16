"""
Servicio de salud: orquesta el ping a la base a través del puerto
`IHealthRepository` (DIP), sin conocer la tecnología subyacente.
"""

from app.services.ports import IHealthRepository


class HealthService:
    """Responde si la base de datos está disponible (readiness probe)."""

    def __init__(self, health_repo: IHealthRepository) -> None:
        self._health_repo = health_repo

    async def database_is_healthy(self) -> bool:
        """`True` si la base responde al ping; nunca lanza."""
        return await self._health_repo.ping()