"""
Tests de configuración de red/seguridad de la aplicación.
"""

from app.config.config import settings


class TestAllowedHosts:
    def test_incluye_el_host_del_router_de_traefik(self):
        assert "api.localhost" in settings.ALLOWED_HOSTS

    def test_incluye_hosts_locales_y_de_pruebas(self):
        assert "localhost" in settings.ALLOWED_HOSTS
        assert "127.0.0.1" in settings.ALLOWED_HOSTS
        assert "testserver" in settings.ALLOWED_HOSTS