"""
Consul service registration for the monolitico (FastAPI) service.

Uses python-consul2 for Consul API interactions (synchronous client wrapped for async).
"""

import os
import socket
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from contextlib import asynccontextmanager

import consul  # python-consul2 installs as 'consul'

logger = logging.getLogger(__name__)


@dataclass
class ConsulConfig:
    """Configuration for Consul registration."""
    service_name: str = "monolitico"
    service_port: int = 8000
    health_path: str = "/health"
    consul_address: str = "consul:8500"
    consul_token: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)
    # Traefik routing host (e.g., "api.localhost")
    domain_host: str = "api.localhost"

    def __post_init__(self):
        # Override from environment if present
        self.service_name = os.getenv("CONSUL_SERVICE_NAME", self.service_name)
        self.service_port = int(os.getenv("CONSUL_SERVICE_PORT", str(self.service_port)))
        self.health_path = os.getenv("CONSUL_HEALTH_PATH", self.health_path)
        self.consul_address = os.getenv("CONSUL_HTTP_ADDR", self.consul_address)
        self.consul_token = os.getenv("CONSUL_HTTP_TOKEN", self.consul_token)
        self.domain_host = os.getenv("DOMAIN_HOST", self.domain_host)


class ConsulRegistrar:
    """
    Handles service registration and health checks with Consul.
    
    Usage:
        registrar = ConsulRegistrar(config)
        await registrar.register()
        # ... run service ...
        await registrar.deregister()
    """

    def __init__(self, config: Optional[ConsulConfig] = None):
        self.config = config or ConsulConfig()
        self._client: Optional[consul.Consul] = None
        self._service_id: Optional[str] = None
        self._local_ip: Optional[str] = None

    @property
    def client(self) -> consul.Consul:
        """Lazy-initialized Consul client."""
        if self._client is None:
            self._client = consul.Consul(
                host=self.config.consul_address.split(":")[0],
                port=int(self.config.consul_address.split(":")[1]) if ":" in self.config.consul_address else 8500,
                token=self.config.consul_token,
            )
        return self._client

    @property
    def service_id(self) -> str:
        """Unique service ID for this instance."""
        if self._service_id is None:
            hostname = socket.gethostname()
            pid = os.getpid()
            self._service_id = f"{self.config.service_name}-{hostname}-{pid}"
        return self._service_id

    @property
    def local_ip(self) -> str:
        """Get the non-loopback IP address of the container."""
        if self._local_ip is None:
            self._local_ip = self._get_local_ip()
        return self._local_ip

    def _get_local_ip(self) -> str:
        """Determine the container's IP address."""
        try:
            # Try to get IP from hostname resolution
            hostname = socket.gethostname()
            ips = socket.getaddrinfo(hostname, None, socket.AF_INET)
            for ip in ips:
                addr = ip[4][0]
                if not addr.startswith("127."):
                    return addr
        except Exception as e:
            logger.warning(f"Could not determine local IP via hostname: {e}")

        try:
            # Fallback: connect to a remote address to get local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception as e:
            logger.warning(f"Could not determine local IP via connection: {e}")

        # Last resort: return empty string (Consul will use agent's IP)
        logger.warning("Using empty address; Consul agent will fill in node IP")
        return ""

    def _build_registration(self) -> dict:
        """Build the service registration payload."""
        # Use liveness endpoint for Consul health check (doesn't require downstream services)
        liveness_path = "/health/live"
        health_check = {
            "http": f"http://{self.local_ip}:{self.config.service_port}{liveness_path}",
            "interval": "10s",
            "timeout": "5s",
            "deregister_critical_service_after": "30s",
            "header": {"Host": [self.config.service_name]},
        }
        return {
            "name": self.config.service_name,
            "service_id": self.service_id,
            "address": self.local_ip,
            "port": self.config.service_port,
            "tags": self._build_tags(),
            "check": health_check,
            "meta": self._build_meta(),
            "enable_tag_override": False,
        }

    def _build_tags(self) -> List[str]:
        """Build tags for service registration."""
        tags = ["consul-registered"]
        tags.extend(self.config.tags)
        # Add explicit Traefik tags with service binding
        # Required when explicit tags are present (Traefik v3 behavior)
        # Use domain_host from config (set via DOMAIN_HOST env var, default: api.localhost)
        tags.append("traefik.enable=true")
        tags.append(f"traefik.http.routers.monolitico.rule=Host(`{self.config.domain_host}`)")
        tags.append("traefik.http.routers.monolitico.entrypoints=web")
        tags.append("traefik.http.routers.monolitico.service=monolitico")
        tags.append("traefik.http.services.monolitico.loadbalancer.server.port=8000")
        return tags

    def _build_meta(self) -> Dict[str, str]:
        """Build metadata for service registration."""
        import datetime
        meta = {
            "registered_at": datetime.datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0",
        }
        meta.update(self.config.meta)
        return meta

    def _register_sync(self) -> None:
        """Synchronous registration (called in thread pool)."""
        registration = self._build_registration()
        self.client.agent.service.register(**registration)
        logger.info(
            "Registered service %s (ID: %s) with Consul at %s:%d%s",
            self.config.service_name,
            self.service_id,
            self.local_ip or "<agent-ip>",
            self.config.service_port,
            self.config.health_path,
        )

    def _deregister_sync(self) -> None:
        """Synchronous deregistration (called in thread pool)."""
        self.client.agent.service.deregister(self.service_id)
        logger.info(
            "Deregistered service %s (ID: %s) from Consul",
            self.config.service_name,
            self.service_id,
        )

    async def register(self) -> None:
        """Register the service with Consul (async wrapper)."""
        try:
            await asyncio.to_thread(self._register_sync)
        except Exception as e:
            logger.error(f"Failed to register service with Consul: {e}")
            raise

    async def deregister(self) -> None:
        """Deregister the service from Consul (async wrapper)."""
        try:
            await asyncio.to_thread(self._deregister_sync)
        except Exception as e:
            logger.error(f"Failed to deregister service from Consul: {e}")
            # Don't raise - best effort during shutdown

    async def health_check_passing(self) -> bool:
        """Check if the service's health check is passing in Consul."""
        try:
            checks = await asyncio.to_thread(self.client.health.checks, self.config.service_name)
            for check in checks:
                if check.get("ServiceID") == self.service_id:
                    return check.get("Status") == "passing"
            return False
        except Exception:
            return False


@asynccontextmanager
async def consul_lifespan(config: Optional[ConsulConfig] = None):
    """
    Async context manager for Consul registration lifecycle.
    
    Usage:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with consul_lifespan(config):
                yield
    """
    registrar = ConsulRegistrar(config)
    try:
        await registrar.register()
        yield registrar
    finally:
        await registrar.deregister()


def create_registrar_from_env() -> ConsulRegistrar:
    """Create a ConsulRegistrar from environment variables."""
    return ConsulRegistrar(ConsulConfig())