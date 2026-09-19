# Task List — Integración Traefik

- [ ] **AGENT-2 · Task: Infra de tests hermética (pythonpath + reportlab + conftest)**
  - Acceptance: `uv run pytest` recolecta y corre sin MongoDB viva.
  - Verify: `uv run pytest`
  - Files: `pyproject.toml`, `tests/conftest.py`, `uv.lock`

- [ ] **AGENT-2 · Task: TDD app-contract (tests rojo)**
  - Acceptance: nuevos tests para `ProblemDetail`, handlers RFC 9457, `/health/live`, `ALLOWED_HOSTS` fallan al no existir la implementación nueva.
  - Verify: `uv run pytest tests/test_problem_detail.py tests/test_error_handlers_rfc9457.py tests/test_health_controller.py`
  - Files: `tests/test_problem_detail.py`, `tests/test_error_handlers_rfc9457.py`, `tests/test_health_controller.py`

- [ ] **AGENT-2 · Task: Implementación app-contract (verde)**
  - Acceptance: handlers consolidados, `/health/live` agregado, config limpia; suite completa verde.
  - Verify: `uv run pytest`
  - Files: `app/domain/problem_detail.py`, `app/api/exception_handlers.py`, `app/main.py`, `app/controllers/health_controller.py`, `app/config/config.py`

- [ ] **AGENT-2 · Task: traefik-infra (traefik.yml + docker-compose.traefik.yml)**
  - Acceptance: `docker compose -f docker-compose.traefik.yml config` renderiza sin errores.
  - Verify: `docker compose -f docker-compose.traefik.yml config`
  - Files: `traefik.yml`, `docker-compose.traefik.yml`

- [ ] **AGENT-2 · Task: traefik-wiring (docker-compose.app.yml + env + README)**
  - Acceptance: `docker compose config` correcto para app y db; labels/healthcheck presentes.
  - Verify: `docker compose -f docker-compose.app.yml config`, `docker compose -f docker-compose.db.yml config`
  - Files: `docker-compose.app.yml`, `env.example`, `README.md`, eliminar `docker-compose.yml`

- [ ] **AGENT-2 · Task: Guía final (docs)**
  - Acceptance: documento con arquitectura, TDD+app, infra, wiring y orden de ejecución.
  - Verify: lectura del documento.
  - Files: `docs/TRAEFIK-INTEGRATION.md`

# Task List — traefik-errors

- [x] **Task: TDD traefik-errors (tests rojo)**
  - Acceptance: `tests/test_traefik_error_endpoints.py` valida rutas `/traefik/errors/429` y `/traefik/errors/503` (RFC 9457); falla al no existir el controlador.
  - Verify: `uv run pytest tests/test_traefik_error_endpoints.py --no-header -q`
  - Files: `tests/test_traefik_error_endpoints.py`

- [x] **Task: Controlador de fallback Traefik (verde)**
  - Acceptance: endpoint 429 y 503 devuelven `application/problem+json` con `type/title/status/detail/instance` en español.
  - Verify: `uv run pytest tests/test_traefik_error_endpoints.py`
  - Files: `app/controllers/traefik_error_controller.py`, `app/main.py`

- [x] **Task: Middlewares Traefik en docker-compose.app.yml**
  - Acceptance: labels `ratelimit`, `cb`, `errors` declarados y encadenados en el router `pdf-app`.
  - Verify: `docker compose -f docker-compose.app.yml config`
  - Files: `docker-compose.app.yml`