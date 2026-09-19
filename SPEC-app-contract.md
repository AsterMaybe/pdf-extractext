# Spec: app-contract (Capability id: `app-contract`)

## Objective
Adecuar la aplicación FastAPI para operar detrás de Traefik y estandarizar el contrato de errores HTTP según RFC 9457 (Problem Details for HTTP APIs), consolidando el código duplicado actual.

Acceptance criteria:

- **AC1:** Existe un modelo `ProblemDetail` (RFC 9457) como única fuente de verdad para las respuestas de error.
- **AC2:** Los 6 handlers duplicados de `app/main.py` quedan consolidados detrás del modelo **sin cambiar comportamiento observable** (títulos, detalles en español, `media_type: application/problem+json`, códigos 400/404/409/422/500).
- **AC3:** Nuevo endpoint `GET /health/live` (liveness) que responde `200 {"status":"ok"}` sin depender de MongoDB; `/health` se mantiene como readiness (ping a MongoDB, 503 si cae).
- **AC4:** Config de hosts confiables: `ALLOWED_HOSTS` incluye el host del router de Traefik (`api.localhost`); se elimina `TRUSTED_HOSTS` (código muerto).
- **AC5:** Suite de tests hermética (no requiere MongoDB viva): `conftest.py` neutraliza `connect`/`disconnect`; `pythonpath = ["."]` en config de pytest; `reportlab` agregado a dependencias dev (lo requiere `tests/test_pdf_to_text.py`).
- **AC6:** Nuevos tests (TDD) en verde y toda la suite pasando.

## Tech Stack
- fastapi==0.135.3, pydantic==2.12.5, pytest==8.3.5, pytest-asyncio, httpx, uv.

## Commands
- Test: `uv run pytest`
- Agregado de dependencia dev: `uv add --group dev reportlab`
- App local: `uv run uvicorn app.main:app --reload`

## Project Structure
```
app/domain/problem_detail.py          → modelo ProblemDetail RFC 9457 (nuevo)
app/api/exception_handlers.py         → registro central de handlers (nuevo)
app/main.py                           → usa install_exception_handlers(app)
app/controllers/health_controller.py  → + GET /health/live
app/config/config.py                  → ALLOWED_HOSTS ampliados; TRUSTED_HOSTS eliminado
tests/conftest.py                     → neutraliza MongoDB (nuevo)
tests/test_problem_detail.py          → unit del modelo + mapa de estados (nuevo)
tests/test_error_handlers_rfc9457.py  → integración TestClient RFC 9457 (nuevo)
tests/test_health_controller.py       → /health/live y /health (nuevo)
pyproject.toml                        → [tool.pytest.ini_options] pythonpath=["."]
```

## Code Style
- PEP 8, type hints, docstrings en español (idioma del repo), imports stdlib → third-party → local.

```python
async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = HTTP_STATUS_BY_EXCEPTION.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
    return _problem_response(request, status_code=status_code, detail=str(exc))
```

## Testing Strategy
- pytest (`testpaths=["tests"]`, `asyncio_mode=auto`).
- Unit: modelo y mapa de estados. Integración: `TestClient` (lifespan neutralizado vía `conftest.py`).
- TDD: primero tests (rojo), luego implementación (verde).

## Boundaries
- **Always:** preservar `detail` en español, `media_type: application/problem+json` y códigos 400/404/409/422/500; correr la suite completa antes de cerrar la tarea.
- **Ask first:** agregar/eliminar dependencias, modificar tests existentes, cambios de schema/datos.
- **Never:** commitear `.env`; cambiar rutas/verbos existentes; responder errores fuera de RFC 9457; borrar tests fallidos sin aprobación.

## Success Criteria
- `uv run pytest` → 100% verde **sin MongoDB corriendo**.
- `TestClient`: 404, 422, 400, 409 y 500 responden en `application/problem+json` con `type`/`title`/`status`/`detail`/`instance`.
- `GET /health/live` → `200 {"status":"ok"}` con `mongodb.client is None`.
- `settings.ALLOWED_HOSTS` contiene `api.localhost`.

## Open Questions
- Ninguno (resueltos en clarificación).