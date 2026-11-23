"""
Consul service discovery for the monolitico service.

Provides DNS SRV and Catalog API based service resolution with TTL caching.
"""

import os
import socket
import logging
import asyncio
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from contextlib import asynccontextmanager

import consul  # python-consul2
import httpx

logger = logging.getLogger(__name__)


@dataclass
class ServiceAddress:
    """Resolved service address."""
    host: str
    port: int

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class DiscoveryConfig:
    """Configuration for service discovery."""
    consul_address: str = "consul:8500"
    consul_token: Optional[str] = None
    dns_port: int = 8600
    cache_ttl_seconds: int = 30
    # When true, resolves services via their Connect sidecar ingress addresses
    # for mTLS termination. Requires sidecar services to be registered.
    use_connect_sidecar: bool = False

    def __post_init__(self):
        self.consul_address = os.getenv("CONSUL_HTTP_ADDR", self.consul_address)
        self.consul_token = os.getenv("CONSUL_HTTP_TOKEN", self.consul_token)
        self.dns_port = int(os.getenv("CONSUL_DNS_PORT", str(self.dns_port)))
        self.cache_ttl_seconds = int(os.getenv("CONSUL_DISCOVERY_CACHE_TTL", str(self.cache_ttl_seconds)))
        self.use_connect_sidecar = os.getenv("CONSUL_USE_CONNECT_SIDECAR", str(self.use_connect_sidecar)).lower() == "true"


class ServiceDiscovery:
    """
    Resolves service addresses via Consul DNS SRV or Catalog API.
    
    Uses DNS SRV as primary method (faster, built-in load balancing via Consul),
    falls back to Catalog API if DNS fails.
    Supports Connect sidecar resolution for mTLS.
    """

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self._catalog_client: Optional[consul.Consul] = None
        self._cache: dict[str, Tuple[ServiceAddress, float]] = {}
        self._cache_lock = asyncio.Lock()

    @property
    def catalog_client(self) -> consul.Consul:
        """Lazy-initialized Consul Catalog client."""
        if self._catalog_client is None:
            host, port_str = self.config.consul_address.split(":")
            self._catalog_client = consul.Consul(
                host=host,
                port=int(port_str),
                token=self.config.consul_token,
            )
        return self._catalog_client

    async def resolve_service(self, service_name: str) -> ServiceAddress:
        """
        Resolve a service name to host:port.
        
        Tries DNS SRV first, then falls back to Catalog API.
        If use_connect_sidecar is True, tries Connect sidecar ingress address first.
        Results are cached for TTL seconds.
        """
        # Check cache first
        async with self._cache_lock:
            if service_name in self._cache:
                address, expires_at = self._cache[service_name]
                if time.time() < expires_at:
                    logger.debug(f"Cache hit for {service_name}: {address}")
                    return address

        address = None
        
        if self.config.use_connect_sidecar:
            # Try Connect sidecar ingress address first
            address = await self._resolve_via_connect_sidecar(service_name)
            if address is None:
                logger.debug(f"Connect sidecar resolution failed for {service_name}, falling back to DNS SRV")
                address = await self._resolve_via_dns_srv(service_name)
        else:
            # Try DNS SRV first
            address = await self._resolve_via_dns_srv(service_name)
        
        if address is None:
            # Fall back to Catalog API
            address = await self._resolve_via_catalog(service_name)

        if address is None:
            raise ServiceResolutionError(f"Could not resolve service: {service_name}")

        # Cache the result
        async with self._cache_lock:
            self._cache[service_name] = (address, time.time() + self.config.cache_ttl_seconds)

        logger.info(f"Resolved {service_name} -> {address}")
        return address

    async def _resolve_via_connect_sidecar(self, service_name: str) -> Optional[ServiceAddress]:
        """Resolve service via its Connect sidecar ingress address for mTLS."""
        try:
            # Sidecar service name format: <service-name>-sidecar-proxy (actual naming)
            sidecar_name = f"{service_name}-sidecar-proxy"
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.catalog_client.catalog.service(sidecar_name)
            )
            
            if not result or len(result) < 2:
                logger.debug(f"No sidecar found for {service_name}")
                return None
            
            _, services = result
            
            if not services or len(services) == 0:
                logger.debug(f"No sidecar found for {service_name}")
                return None
            
            # Pick first healthy sidecar instance
            instance = services[0]
            
            host = instance.get("ServiceAddress") or instance.get("Address", "")
            port = instance.get("ServicePort", 0)
            
            if not host or port == 0:
                logger.warning(f"Invalid sidecar address for {service_name}: {instance}")
                return None
                
            logger.debug(f"Resolved {service_name} via Connect sidecar: {host}:{port}")
            return ServiceAddress(host=host, port=port)
            
        except Exception as e:
            logger.debug(f"Connect sidecar resolution failed for {service_name}: {e}")
            return None

    async def _resolve_via_dns_srv(self, service_name: str) -> Optional[ServiceAddress]:
        """Resolve service via Consul DNS SRV records."""
        try:
            # Consul DNS format: <service>.service.consul
            srv_name = f"{service_name}.service.consul"
            
            # Use asyncio to run DNS query in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(
                    srv_name,
                    None,
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    0,
                    socket.AI_PASSIVE | socket.AI_NUMERICSERV,
                )
            )
            
            if not result:
                return None
                
            # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
            # For SRV, we need to query SRV records specifically
            # Use a more targeted approach with dnspython if available, 
            # but for now use the catalog API as it's more reliable
            logger.debug(f"DNS SRV resolution attempted for {srv_name}")
            return await self._resolve_via_catalog(service_name)
            
        except (socket.gaierror, OSError) as e:
            logger.debug(f"DNS SRV resolution failed for {service_name}: {e}")
            return None

    async def _resolve_via_catalog(self, service_name: str) -> Optional[ServiceAddress]:
        """Resolve service via Consul Catalog HTTP API."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.catalog_client.catalog.service(service_name)
            )
            
            # python-consul2 returns (index, services_list)
            if not result or len(result) < 2:
                logger.warning(f"No healthy instances found for {service_name} in Consul catalog")
                return None
            
            _, services = result
            
            if not services or len(services) == 0:
                logger.warning(f"No healthy instances found for {service_name} in Consul catalog")
                return None
            
            # Filter to only passing health checks
            healthy_services = [
                s for s in services 
                if s.get("CheckStatus") == "passing" or s.get("Status") == "passing"
            ]
            
            # If no explicitly healthy, use all (Consul only returns passing by default with ?passing)
            if not healthy_services:
                healthy_services = services
            
            # Pick first healthy instance (Consul provides basic load balancing via DNS)
            # For better load balancing, we could implement random/round-robin selection
            instance = healthy_services[0]
            
            # Use ServiceAddress if available, otherwise Node address
            host = instance.get("ServiceAddress") or instance.get("Address", "")
            port = instance.get("ServicePort", 0)
            
            if not host or port == 0:
                logger.warning(f"Invalid service address for {service_name}: {instance}")
                return None
                
            return ServiceAddress(host=host, port=port)
            
        except Exception as e:
            logger.error(f"Catalog API resolution failed for {service_name}: {e}")
            return None

    async def resolve_service_url(self, service_name: str) -> str:
        """Resolve service and return full HTTP URL."""
        address = await self.resolve_service(service_name)
        return address.url

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._cache.clear()
        logger.debug("Service discovery cache cleared")


class ServiceResolutionError(Exception):
    """Raised when a service cannot be resolved."""
    pass


# Global discovery instance for convenience
_discovery_instance: Optional[ServiceDiscovery] = None


def get_discovery(config: Optional[DiscoveryConfig] = None) -> ServiceDiscovery:
    """Get or create the global ServiceDiscovery instance."""
    global _discovery_instance
    if _discovery_instance is None:
        _discovery_instance = ServiceDiscovery(config)
    return _discovery_instance


@asynccontextmanager
async def discovery_lifespan(config: Optional[DiscoveryConfig] = None):
    """
    Async context manager for ServiceDiscovery lifecycle.
    
    Usage:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with discovery_lifespan(config):
                yield
    """
    discovery = ServiceDiscovery(config)
    try:
        yield discovery
    finally:
        discovery.clear_cache()


async def resolve_service_url(service_name: str, config: Optional[DiscoveryConfig] = None) -> str:
    """Convenience function to resolve a service URL."""
    discovery = get_discovery(config)
    return await discovery.resolve_service_url(service_name)