# Capability Map: API Gateway y microservicios

| Module id | Responsibility | Depends on |
|---|---|---|
| `app-contract` | RFC 9457 `ProblemDetail` + handlers consolidados, `/health/live`, trusted hosts, suite hermética | — |
| `db-service` | Microservicio Go de persistencia y MongoDB en un volumen persistente | red compartida |
| `extract-service` | Microservicio Go de extracción de PDF | red compartida, MongoDB |
| `traefik-infra` | `traefik.yml` estático + `docker-compose.traefik.yml` | — |
| `traefik-wiring` | `docker-compose.app.yml` (labels/network/healthcheck), env, orden de ejecución | `app-contract`, `db-service`, `extract-service`, `traefik-infra` |
| `traefik-errors` | Middlewares Traefik de rate-limit + circuit-breaker, delegación de errores 429/503 y endpoints de fallback RFC 9457 | `traefik-wiring`, `app-contract` |

Build order: `app-contract` → `traefik-infra` → `traefik-wiring` → `traefik-errors`

- Los ids son estables (kebab-case) y son la forma de referirse a cada spec (`SPEC-app-contract.md`, `SPEC-traefik-infra.md`, `SPEC-traefik-wiring.md`).
- La red externa `${SHARED_NETWORK_NAME}` conecta Traefik, FastAPI, ambos servicios Go y MongoDB. El stack `microservicio-db-go` es dueño de MongoDB; FastAPI solo consume su API HTTP.
- Aprobado en fase de clarificación (09/2026): entrega escribiendo archivos + tests verdes, HTTP-only local/staging, refactor RFC 9457, sin puerto 8000 publicado.