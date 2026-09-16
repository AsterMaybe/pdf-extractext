# Plan: Integración Traefik

## Componentes y dependencias

1. **app-contract** (Python, TDD) — sin dependencias de infra.
   - `ProblemDetail` (RFC 9457) + builder `_problem_response`.
   - Consolidación de handlers en `app/api/exception_handlers.py` (OCP: extender el dict de estados para sumar errores).
   - `GET /health/live`; `ALLOWED_HOSTS` + `api.localhost`; eliminar `TRUSTED_HOSTS`.
   - Infra de tests: `conftest.py` neutraliza Mongo; `pythonpath=["."]`; `reportlab` dev.
2. **traefik-infra** (config) — independiente de app-contract, pero debe existir antes de wiring para que la red tenga gateway.
   - `traefik.yml` (entrypoint web, dashboard dev, docker provider) + `docker-compose.traefik.yml`.
3. **traefik-wiring** (compose/env) — depende de ambos.
   - `docker-compose.app.yml` con labels/healthcheck; borrar `docker-compose.yml`; `env.example`; README.
4. **traefik-errors** (compose labels + controlador FastAPI) — depende de `traefik-wiring` (router `pdf-app` ya existe) y de `app-contract` (`_problem_response`).
   - Middlewares Traefik via labels: Rate Limit (100 req/s, burst 50), Circuit Breaker (`NetworkErrorRatio() > 0.33`), Errors (429/503 → delegación interna).
   - Controlador `app/controllers/traefik_error_controller.py` con endpoints `/traefik/errors/429` y `/traefik/errors/503` en RFC 9457.
   - Tests `tests/test_traefik_error_endpoints.py` (TDD) validando `application/problem+json`.

## Orden de implementación
`app-contract` → `traefik-infra` → `traefik-wiring` → `traefik-errors`

- `app-contract` y `traefik-infra` son paralelizables; `traefik-wiring` y `traefik-errors` son secuenciales.
- Cada paso tiene checkpoint de verificación (`uv run pytest`, `docker compose config`).

## Riesgos y mitigación
- **Suite roja por entorno (import path + reportlab + MongoDB viva):** se resuelve de raíz con `pythonpath=["."]`, `reportlab` en dev y `conftest.py` hermético.
- **Interpolación de env en traefik.yml no garantizada:** se evita; la red se fija con label `traefik.docker.network` (interpolada por compose en render).
- **TrustedHost rechazando el Host del router:** `api.localhost` se suma a `ALLOWED_HOSTS` (default y env alternativa).
- **Lifespan conectando a Mongo durante tests:** neutralizada por `conftest.py`.
- **Docker Desktop no corriendo:** validación offline con `docker compose config`; smoke tests documentados para ejecutar con Docker.

## Checkpoints
1. `uv run pytest` verde (incluye tests nuevos) — fin de app-contract.
2. `docker compose -f docker-compose.traefik.yml config` OK — fin de traefik-infra.
3. `docker compose -f docker-compose.app.yml config` + `docker-compose.db.yml config` OK — fin de traefik-wiring.
4. Test TDD rojo: `uv run pytest tests/test_traefik_error_endpoints.py --no-header -q` falla (endpoints no existen). ✅ (rojo observado aunque el árbol ya traía la implementación)
5. `uv run pytest` verde — fin de traefik-errors. ✅ (84 passed, incluye endpoints nuevos)
6. Guía completa escrita con orden de ejecución exacto.