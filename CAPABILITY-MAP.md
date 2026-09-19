# Capability Map: Integración Traefik (API Gateway del monolito)

| Module id | Responsibility | Depends on |
|---|---|---|
| `app-contract` | RFC 9457 `ProblemDetail` + handlers consolidados, `/health/live`, trusted hosts, suite hermética | — |
| `traefik-infra` | `traefik.yml` estático + `docker-compose.traefik.yml` | — |
| `traefik-wiring` | `docker-compose.app.yml` (labels/network/healthcheck), env, orden de ejecución | `app-contract`, `traefik-infra` |
| `traefik-errors` | Middlewares Traefik de rate-limit + circuit-breaker, delegación de errores 429/503 y endpoints de fallback RFC 9457 | `traefik-wiring`, `app-contract` |

Build order: `app-contract` → `traefik-infra` → `traefik-wiring` → `traefik-errors`

- Los ids son estables (kebab-case) y son la forma de referirse a cada spec (`SPEC-app-contract.md`, `SPEC-traefik-infra.md`, `SPEC-traefik-wiring.md`).
- La red compartida `shared-network` (externa, nombrada via `${SHARED_NETWORK_NAME}`) es el pegamento entre los tres compose files y no pertenece a ningún módulo.
- Aprobado en fase de clarificación (09/2026): entrega escribiendo archivos + tests verdes, HTTP-only local/staging, refactor RFC 9457, sin puerto 8000 publicado.