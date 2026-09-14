# Guía de Integración: Traefik como API Gateway / Reverse Proxy

Monolito FastAPI + MongoDB. Esta guía documenta la integración paso a paso,
incluyendo el código final aplicado en el repo y el orden exacto de arranque.

Workflow usado: spec-driven (los artifacts viven en `CAPABILITY-MAP.md`,
`SPEC-app-contract.md`, `SPEC-traefik-infra.md`, `SPEC-traefik-wiring.md`,
`tasks/plan.md`, `tasks/todo.md`). TDD para toda la capa Python.

---

## 1. Arquitectura y red

Tres docker-compose separados, pegados por **una red Docker externa y
compartida** (`${SHARED_NETWORK_NAME}`, default `default-shared-network`;
en `.env` actual: `test_network`). Ningún compose crea la red: se declara
`external: true` y se crea una única vez con `docker network create`.

```
                            (host) :80 / :8080
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │   traefik            │   docker-compose.traefik.yml
                       │  API Gateway         │
                       │  traefik:v3.7        │
                       └──────────┬───────────┘
                                  │  descubre contenedores por labels
                                  │  (docker.sock readonly) + red compartida
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────┐            ┌───────────────┐          ┌──────────────┐
│  app      │            │  app (FastAPI)│          │  mongo       │
│ myapp     │            │   myapp       │          │  mongo:8.0   │
│ :8000     │            │   :8000       │          │  :27017      │
└───────────┘            └───────────────┘          └──────────────┘
                                   ▲
                          red compartida externa
                     (mismo nombre en los 3 compose files)
```

- **Traefik** publica `80:80` (entrypoint `web`) y `8080:8080` (dashboard dev).
- **App** NO publica puertos al host: solo `expose: "8000"` (visible dentro de
  la red). Entrada única por Traefik.
- **DB** publica `27017:27017` para herramientas locales (dev); la app la
  alcanza como `mongo:27017` dentro de la red.
- La configuración **dinámica** (rutas) sale de los **labels Docker** en
  `docker-compose.app.yml` (`traefik.http.*`). La configuración **estática**
  (entrypoints/providers) sale del archivo `traefik.yml`.

---

## 2. Paso 1 — TDD y ajustes de la aplicación

### 2.1 Suite de tests hermética (prerrequisito)

La suite ahora corre **sin MongoDB viva**:

1. `pyproject.toml` → `pythonpath = ["."]` en `[tool.pytest.ini_options]` para
   que `uv run pytest` encuentre el paquete `app`.
2. `reportlab` agregado como dependencia dev (`tests/test_pdf_to_text.py` la
   importa):
   ```bash
   uv add --group dev reportlab
   ```
3. `tests/conftest.py` neutraliza `connect`/`disconnect` del singleton y deja
   `client = None`:

```python
import pytest


@pytest.fixture(autouse=True)
def _neutralize_mongodb(monkeypatch):
    from app.config.mongodb import mongodb

    async def _noop_connect() -> None:
        return None

    async def _noop_disconnect() -> None:
        return None

    monkeypatch.setattr(mongodb, "connect", _noop_connect)
    monkeypatch.setattr(mongodb, "disconnect", _noop_disconnect)
    monkeypatch.setattr(mongodb, "client", None)
```

### 2.2 Tests (TDD — rojo primero)

`tests/test_problem_detail.py` — modelo RFC 9457 y registro de estados:

```python
"""
Tests unitarios del modelo RFC 9457 (ProblemDetail) y del registro de
estados HTTP que alimenta los handlers consolidados.
"""

from fastapi import status

from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    FileSizeExceededError,
    InvalidPDFFormatError,
)
from app.domain.problem_detail import ProblemDetail


class TestProblemDetailModel:
    def test_type_defaults_to_about_blank(self):
        problem = ProblemDetail(title="Bad Request", status=400, detail="detalle")
        assert problem.type == "about:blank"

    def test_optional_fields_are_none_by_default(self):
        problem = ProblemDetail(title="Bad Request", status=400, detail="detalle")
        assert problem.instance is None
        assert problem.errors is None

    def test_all_fields_are_set(self):
        problem = ProblemDetail(
            type="https://example.com/errors/custom",
            title="Conflict",
            status=409,
            detail="duplicado",
            instance="/api/v1/documents/upload",
            errors=[{"loc": ["body"], "msg": "x"}],
        )
        assert problem.type == "https://example.com/errors/custom"
        assert problem.title == "Conflict"
        assert problem.status == 409
        assert problem.detail == "duplicado"
        assert problem.instance == "/api/v1/documents/upload"
        assert problem.errors == [{"loc": ["body"], "msg": "x"}]

    def test_dump_excludes_none_fields(self):
        problem = ProblemDetail(title="Bad Request", status=400, detail="detalle")
        data = problem.model_dump(exclude_none=True)
        assert data["type"] == "about:blank"
        assert data["title"] == "Bad Request"
        assert data["status"] == 400
        assert data["detail"] == "detalle"
        assert "instance" not in data
        assert "errors" not in data


class TestHttpStatusByExceptionMap:
    def test_document_not_found_is_404(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_EXCEPTION

        assert HTTP_STATUS_BY_EXCEPTION[DocumentNotFoundError] == status.HTTP_404_NOT_FOUND

    def test_already_exists_is_409(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_EXCEPTION

        assert HTTP_STATUS_BY_EXCEPTION[DocumentAlreadyExistsError] == status.HTTP_409_CONFLICT

    def test_file_size_exceeded_is_400(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_EXCEPTION

        assert HTTP_STATUS_BY_EXCEPTION[FileSizeExceededError] == status.HTTP_400_BAD_REQUEST

    def test_invalid_pdf_format_is_400(self):
        from app.api.exception_handlers import HTTP_STATUS_BY_EXCEPTION

        assert HTTP_STATUS_BY_EXCEPTION[InvalidPDFFormatError] == status.HTTP_400_BAD_REQUEST
```

`tests/test_error_handlers_rfc9457.py` — integración vía `TestClient`:

```python
"""
Tests de integración de los handlers de error RFC 9457.

Verifica que todos los errores responden en `application/problem+json` con el
cuerpo estandarizado, y que el comportamiento observable se conserva tras la
consolidación de los handlers duplicados.
"""

from fastapi import status
from fastapi.testclient import TestClient

from app.controllers.document_controller import get_document_repo
from app.domain.exceptions import DocumentNotFoundError
from app.main import app


def _make_dummy_pdf() -> bytes:
    import io

    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Texto de prueba")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


class _StubRepo:
    async def exists_by_checksum(self, checksum: str) -> bool:
        return False

    async def get_by_id(self, doc_id: str):
        raise DocumentNotFoundError(doc_id)

    async def create(self, doc):
        raise NotImplementedError


def _assert_problem(response, status_code: int) -> None:
    assert response.status_code == status_code
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    for key in ("type", "title", "status", "detail"):
        assert key in body
    assert body["status"] == status_code
    assert body["title"]


class TestRfc9457Handlers:
    def test_unknown_route_returns_404_problem(self):
        with TestClient(app) as client:
            response = client.get("/ruta/inexistente")
        _assert_problem(response, status.HTTP_404_NOT_FOUND)

    def test_validation_error_returns_422_problem_with_errors(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with TestClient(app) as client:
                response = client.post("/api/v1/documents/upload")
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_422_UNPROCESSABLE_CONTENT)
        assert "errors" in response.json()

    def test_document_not_found_returns_404_problem(self):
        class NotFoundRepo(_StubRepo):
            async def get_by_id(self, doc_id: str):
                raise DocumentNotFoundError(doc_id)

        app.dependency_overrides[get_document_repo] = lambda: NotFoundRepo()
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/documents/60d5ecb8b392d70008051234")
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_404_NOT_FOUND)

    def test_duplicate_document_returns_409_problem(self):
        class DuplicateRepo(_StubRepo):
            async def exists_by_checksum(self, checksum: str) -> bool:
                return True

        app.dependency_overrides[get_document_repo] = lambda: DuplicateRepo()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("dup.pdf", _make_dummy_pdf(), "application/pdf")},
                )
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_409_CONFLICT)

    def test_oversized_file_returns_400_problem(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("big.pdf", b"0" * (5 * 1024 * 1024 + 1), "application/pdf")},
                )
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_400_BAD_REQUEST)

    def test_invalid_pdf_format_returns_400_problem(self):
        app.dependency_overrides[get_document_repo] = lambda: _StubRepo()
        try:
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": ("doc.txt", b"This is not a pdf", "application/octet-stream")},
                )
        finally:
            app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_400_BAD_REQUEST)

    def test_unhandled_error_returns_500_problem(self):
        class ExplodingRepo(_StubRepo):
            async def get_by_id(self, doc_id: str):
                raise RuntimeError("boom")

        app.dependency_overrides[get_document_repo] = lambda: ExplodingRepo()
        # ServerErrorMiddleware re-raisea tras enviar la 500; lo desactivamos
        # para poder inspeccionar la respuesta problem+json.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/documents/60d5ecb8b392d70008051234")
        app.dependency_overrides.clear()
        _assert_problem(response, status.HTTP_500_INTERNAL_SERVER_ERROR)
        assert "inesperado" in response.json()["detail"].lower()
```

`tests/test_health_controller.py` — liveness (para Traefik) y readiness:

```python
from unittest.mock import AsyncMock

from fastapi import status
from fastapi.testclient import TestClient

from app.config.mongodb import mongodb
from app.main import app


class TestHealthLiveness:
    def test_live_returns_200_without_database(self):
        mongodb.client = None
        with TestClient(app) as client:
            response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}


class TestHealthReadiness:
    def test_health_returns_503_when_database_offline(self):
        mongodb.client = None
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["database"] == "error"

    def test_health_returns_200_when_database_online(self):
        mongodb.client = AsyncMock()
        mongodb.client.admin.command = AsyncMock(return_value={"ok": 1})
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "ok"
        assert response.json()["app"] == "ok"
        assert response.json()["database"] == "ok"
```

`tests/test_config.py` — hosts confiables:

```python
from app.config.config import settings


class TestAllowedHosts:
    def test_incluye_el_host_del_router_de_traefik(self):
        assert "api.localhost" in settings.ALLOWED_HOSTS

    def test_incluye_hosts_locales_y_de_pruebas(self):
        assert "localhost" in settings.ALLOWED_HOSTS
        assert "127.0.0.1" in settings.ALLOWED_HOSTS
        assert "testserver" in settings.ALLOWED_HOSTS
```

### 2.3 Implementación (verde)

`app/domain/problem_detail.py` — **modelo estándar de error RFC 9457**:

```python
from typing import Any

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """Cuerpo estándar de una respuesta de error HTTP (RFC 9457)."""

    type: str = Field(default="about:blank", description="URI que identifica el tipo de problema.")
    title: str = Field(description="Título breve y legible del problema.")
    status: int = Field(description="Código de estado HTTP de la respuesta.")
    detail: str = Field(description="Explicación específica de este error en particular.")
    instance: str | None = Field(
        default=None,
        description="URI que identifica la ocurrencia concreta del problema.",
    )
    errors: list[Any] | None = Field(
        default=None,
        description="Detalle adicional, por ejemplo errores de validación (422).",
    )
```

`app/api/exception_handlers.py` — handlers consolidados (SOLID/OCP):
extender el mapa `HTTP_STATUS_BY_EXCEPTION` es suficiente para un error nuevo.

```python
import http
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    FileSizeExceededError,
    InvalidPDFFormatError,
)
from app.domain.problem_detail import ProblemDetail

logger = logging.getLogger(__name__)

HTTP_STATUS_BY_EXCEPTION: dict[type[Exception], int] = {
    DocumentNotFoundError: status.HTTP_404_NOT_FOUND,
    FileSizeExceededError: status.HTTP_400_BAD_REQUEST,
    InvalidPDFFormatError: status.HTTP_400_BAD_REQUEST,
    DocumentAlreadyExistsError: status.HTTP_409_CONFLICT,
}


def _problem_response(
    request: Request,
    status_code: int,
    detail: str,
    title: str | None = None,
    errors: list | None = None,
) -> JSONResponse:
    problem = ProblemDetail(
        title=title or http.HTTPStatus(status_code).phrase,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _problem_response(request, status_code=exc.status_code, detail=str(exc.detail))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="La petición contiene datos inválidos o incompletos.",
        errors=exc.errors(),
    )


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = HTTP_STATUS_BY_EXCEPTION.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return _problem_response(request, status_code=status_code, detail=str(exc))


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Error interno del servidor no controlado")
    return _problem_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Ha ocurrido un error inesperado en el servidor. Por favor, intente más tarde.",
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    for exception_type in HTTP_STATUS_BY_EXCEPTION:
        app.add_exception_handler(exception_type, domain_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
```

`app/controllers/health_controller.py` — nuevo liveness:

```python
@router.get("/health/live", summary="Verifica que la aplicación esté viva", response_class=JSONResponse)
async def health_live():
    """
    Liveness para balanceadores/reverse proxies (Traefik).
    Solo comprueba que el proceso responde; no toca la base de datos.
    """
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})
```

`app/config/config.py` — hosts confiables (eliminado `TRUSTED_HOSTS` duplicado):

```python
ALLOWED_HOSTS: list[str] = ["api.localhost", "localhost", "127.0.0.1", "testserver"]
```

`app/main.py` — se reemplazan los 6 handlers inline por el registro central:

```python
install_exception_handlers(app)
```

TrustedHostMiddleware se mantiene (`allowed_hosts=settings.ALLOWED_HOSTS`).

### 2.4 Verificación

```bash
uv run pytest tests/test_problem_detail.py tests/test_error_handlers_rfc9457.py tests/test_health_controller.py tests/test_config.py
```

---

## 3. Paso 2 — Infraestructura (DB y Traefik)

### `docker-compose.db.yml` (existente, ajustado)

> Cambios: `TZ=${TZ}$` → `TZ=${TZ:-UTC}`, **proyecto aislado** (`name:`)
> y volumen externo con nombre fijo (conserva los datos si el proyecto cambia).

```yaml
# Proyecto aislado: `docker compose up` de otra ficha NO trata este contenedor
# como "huérfano" (todas las fichas comparten solo la red externa).
name: pdf-extractext-db

services:
  mongo:
    image: mongo:8.0
    container_name: mongo
    ports:
      - '27017:27017'
    environment:
      - MONGO_INITDB_ROOT_USERNAME=${MONGO_USER}
      - MONGO_INITDB_ROOT_PASSWORD=${MONGO_PASSWORD}
      - TZ=${TZ:-UTC}
    volumes:
      - mongo_data:/data/db
    networks:
      - shared-network

volumes:
  mongo_data:
    name: pdf-extractext_mongo_data
    external: true

networks:
  shared-network:
    name: ${SHARED_NETWORK_NAME:-default-shared-network}
    external: true
```

### `traefik.yml` (estática — entrypoints + providers)

```yaml
api:
  dashboard: true
  # SOLO para local/staging. En producción: dashboard protegido con middleware
  # BasicAuth o desactivado (insecure: false).
  insecure: true

entryPoints:
  web:
    address: ":80"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false   # solo contenedores con labels traefik
    watch: true

log:
  level: INFO
```

> HTTPS/Let's Encrypt queda documentado como bloque comentado dentro del
> archivo (entrypoint `websecure` + `certificatesResolvers.acme`).

### `docker-compose.traefik.yml`

```yaml
# Proyecto aislado: evita que `up`/`down` de otra ficha toque Traefik.
name: pdf-extractext-gateway

services:
  traefik:
    image: traefik:v3.7
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"        # entrypoint web (tráfico de la API)
      - "8080:8080"    # dashboard/api (solo desarrollo)
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml:ro
    networks:
      - shared-network

networks:
  shared-network:
    name: ${SHARED_NETWORK_NAME:-default-shared-network}
    external: true
```

---

## 4. Paso 3 — Compose de la aplicación con labels de Traefik

### `docker-compose.app.yml`

```yaml
# Proyecto aislado: evita que `up`/`down` de esta ficha borre las otras.
name: pdf-extractext-app

services:
  myapp:
    build:
      context: .
      dockerfile: Dockerfile
    image: myapp:v1.0.0
    restart: unless-stopped
    expose:
      - "8000"
    environment:
      - MONGODB_URL=mongodb://${MONGO_USER}:${MONGO_PASSWORD}@mongo:27017
      - MONGODB_DB_NAME=${MONGODB_DB_NAME}
      - MONGODB_COLLECTION=${MONGODB_COLLECTION}
      - TZ=${TZ:-UTC}
      # Opcional: el default de la app ya incluye api.localhost.
      # - ALLOWED_HOSTS=["api.localhost","localhost","127.0.0.1"]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=${SHARED_NETWORK_NAME:-default-shared-network}"
      - "traefik.http.routers.pdf-app.rule=Host(`${DOMAIN_HOST:-api.localhost}`)"
      - "traefik.http.routers.pdf-app.entrypoints=web"
      - "traefik.http.routers.pdf-app.service=pdf-app"
      - "traefik.http.services.pdf-app.loadbalancer.server.port=8000"
      # Sin healthcheck activo en Traefik: probea con la IP del contenedor y
      # TrustedHostMiddleware la rechaza (400). Liveness real: healthcheck Docker.
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)\""]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 10s
    networks:
      - shared-network

networks:
  shared-network:
    name: ${SHARED_NETWORK_NAME:-default-shared-network}
    external: true
```

### Labels explicados

| Label | Efecto |
|---|---|
| `traefik.enable=true` | Expone el contenedor (requerido porque `exposedByDefault=false`). |
| `traefik.docker.network=…` | Nombre de la red que Traefik usa para alcanzar el contenedor (lo interpola compose, no Traefik). |
| `traefik.http.routers.pdf-app.rule=Host(\`api.localhost\`)` | Ruta: matchea el host. |
| `traefik.http.routers.pdf-app.entrypoints=web` | Entrypoint `web` (:80). |
| `traefik.http.services.pdf-app.loadbalancer.server.port=8000` | Puerto interno real del servicio. |
| `healthcheck:` (docker) | Healthcheck del contenedor (`/health/live`, `start_period: 10s`). Liveness real; Traefik no hace healthcheck de LB (ver nota abajo). |

### ¿Por qué no hay healthcheck de LBs en Traefik?

El provider Docker descubrió el contenedor pero el healthcheck **del load
balancer** de Traefik devuelve `400` (WARN en logs): Traefik probea con el
`Host` = IP del contenedor y la app lo rechaza vía `TrustedHostMiddleware`
(`ALLOWED_HOSTS`). Configurar `healthcheck.headers.Host` no surte efecto:
Go/`http` trata `Host` como campo especial del request y lo toma de la URL del
server. Como alternativa segura, la **liveness real la cubre el healthcheck de
Docker** (`/health/live` sobre `127.0.0.1`, permitido) y Traefik sirve
directamente (si la app cae, devuelve 502/503 al cliente).

> Separación liveness vs readiness: `/health/live` es **liveness** (no depende
> de MongoDB) y lo usa el healthcheck de Docker; `/health` sigue siendo el
> **readiness** (503 si la DB cae).

`env.example` (los valores clave):

```env
SHARED_NETWORK_NAME=test_network
DOMAIN_HOST=api.localhost
# ALLOWED_HOSTS=["api.localhost","localhost","127.0.0.1"]  # opcional (JSON array)
```

---

## 5. Paso 4 — Orden de ejecución

```bash
# 0) Crear la red compartida UNA sola vez (external en los 3 compose files)
docker network create test_network        # ajustar a tu SHARED_NETWORK_NAME

# 1) Base de datos
docker compose -f docker-compose.db.yml up -d

# 2) Gateway Traefik
docker compose -f docker-compose.traefik.yml up -d

# 3) Aplicación
docker compose -f docker-compose.app.yml up -d --build
```

> Cada ficha tiene su **propio proyecto compose** (`name:`). Esto evita que
> `up`/`down` de una ficha borre los contenedores de las otras (son
> "huérfanos" si comparten el nombre de proyecto inferido del directorio).
> Todas comparten la red externa `test_network`.

Verificación:

```bash
# a) Dashboard de Traefik (dev)
open http://localhost:8080

# b) Readiness de la app a través del gateway (Host api.localhost)
curl -H "Host: api.localhost" http://localhost/health

# c) Liveness (usado por el healthcheck de Docker del contenedor)
curl -H "Host: api.localhost" http://localhost/health/live

# d) API de documentos (lista)
curl -H "Host: api.localhost" http://localhost/api/v1/documents/

# e) Error RFC 9457 a través del gateway (404)
curl -i -H "Host: api.localhost" http://localhost/nada
```

Cómo verificar errores consistentes como respuesta:

```json
HTTP/1.1 404 Not Found
content-type: application/problem+json

{"type":"about:blank","title":"Not Found","status":404,"detail":"Not Found","instance":"/nada"}
```

Inspección de rutas descubiertas:

```bash
docker compose -f docker-compose.traefik.yml logs -f
# o via API: curl http://localhost:8080/api/http/routers
```

---

## Estado de la suite (validado)

Suite completa en verde y **hermética** (sin MongoDB viva). Los dos archivos de
tests que quedaron rotos por el refactor previo (`test_entrada_salida_pdf.py` y
`test_pdf_to_text.py`) se actualizaron a la API actual.

```bash
uv run pytest
```

Resultado actual: **82 passed** (incluye RFC 9457, health, pdf_processor y
pdf_to_text).