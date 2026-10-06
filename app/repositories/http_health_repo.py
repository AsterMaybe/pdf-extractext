"""
Adaptador HTTP que implementa IHealthRepository delegando al microservicio Go.

Este adaptador consulta el endpoint de readiness del microservicio Go de datos.
"""

import logging
from typing import Any

import httpx

from app.services.ports import IHealthRepository

logger = logging.getLogger(__name__)


class HttpHealthRepository(IHealthRepository):
    """
    Implementación de IHealthRepository vía HTTP al microservicio Go.

    Consulta GET /health (readiness) del servicio de persistencia.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Args:
            base_url: URL base del microservicio Go (ej. http://microservicio-db-go:8080)
            timeout: Timeout en segundos para requests HTTP
            client: Cliente HTTP opcional para inyección de dependencias (tests)
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=self._timeout)

    async def _close_if_owned(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def ping(self) -> bool:
        """
        Verifica disponibilidad del microservicio Go y su conexión a la base de datos.

        Returns:
            True si el servicio responde 200 en /health (readiness ok), False en caso contrario.
            Nunca lanza excepciones.
        """
        client = await self._get_client()
        try:
            response = await client.get(
                f"{self._base_url}/health",
                timeout=self._timeout,
            )
            return response.status_code == 200
        except httpx.RequestError:
            logger.exception("Error de red al hacer health check al microservicio Go")
            return False
        except Exception:
            logger.exception("Error inesperado en health check HTTP")
            return False
        finally:
            await self._close_if_owned()