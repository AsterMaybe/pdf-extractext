# Spec: traefik-errors (Capability id: `traefik-errors`)

## Objective

Implementar los middlewares de **Rate Limiting** y **Circuit Breaker** en Traefik para proteger la aplicación FastAPI, y garantizar que los errores generados por estos mecanismos (HTTP 429 y HTTP 503) se presenten al cliente en formato RFC 9457 (`application/problem+json`).

Traefik por defecto devuelve texto plano para 429 y 503; el spec crea un flujo de delegación: Traefik intercepta el error de infra → redirige internamente a un controlador FastAPI → FastAPI devuelve el `ProblemDetail` estandarizado.

### Acceptance Criteria

- **AC1:** `docker-compose.app.yml` declara middlewares de Traefik via labels:
  - Rate Limit: `RateLimit`
  - a 100 req/s, burst de 50.
  - Circuit Breaker: `NetworkErrorRatio() > 0.33`.
  - Errors middleware: intercepta estados 429 y 503, redirige a la app (`/traefik/errors/{code}`).
- **AC2:** Middlewares asignados al router `pdf-app` existente.
- **AC3:** Nuevo controlador `app/controllers/traefik_error_controller.py` con endpoints `GET /traefik/errors/429` y `GET /traefik/errors/503` que devuelven `ProblemDetail` RFC 9457 con los status 429 y 503 respectivamente, en español.
- **AC4:** Tests en `tests/test_traefik_error_endpoints.py` validan que las rutas 429 y 503 responden `application/problem+json` con `type`, `title`, `status`, `detail`, `instance`.
- **AC5:** No se rompe la DI existente; no se agregan dependencias nuevas.

## Tech Stack
- Traefik v3.7 (labels `traefik.http.middlewares.*`)
- FastAPI 0.135.3, Pydantic 2.12.5

## Commands
- Test: `uv run pytest`
- Validar compose: `docker compose -f docker-compose.app.yml config`

## Project Structure
```
app/controllers/traefik_error_controller.py → endpoints de fallback 429/503 (nuevo)
tests/test_traefik_error_endpoints.py      → tests TDD de los endpoints (nuevo)
docker-compose.app.yml                     → labels de middlewares Traefik (modificado)
app/main.py                                → incluir router del nuevo controlador
```

## Code Style
- PEP 8, type hints, docstrings en español; usa `_problem_response` existente.
- Endpoints dedicados, sin lógica de dominio.

```python
@router.get("/traefik/errors/429", response_class=JSONResponse)
async def traefik_rate_limited(request: Request) -> JSONResponse:
    return _problem_response(
        request,
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Se ha excedido el límite de peticiones. Intente más tarde.",
    )
```

## Testing Strategy
- pytest; tests de integración con `TestClient`.
- Cada endpoint: status correcto, content-type `application/problem+json`, keys `type/title/status/detail/instance`.

## Boundaries
- **Always:** responder en `application/problem+json`; idioma español; usar `_problem_response`.
- **Ask first:** cambiar valores de rate-limit/circuit-breaker; agregar endpoints adicionales; modificar middlewares existentes.
- **Never:** exponer la app sin Traefik; hardcodear valores de infra en código Python; romper tests existentes.

## Success Criteria
- `uv run pytest` → 100% verde.
- `docker compose config` resuelve sin errores.
- `/traefik/errors/429` y `/traefik/errors/503` responden RFC 9457.

## Open Questions
- Ninguno.
