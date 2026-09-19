# Spec: traefik-wiring (Capability id: `traefik-wiring`)

## Objective
Conectar la app FastAPI al gateway: `docker-compose.app.yml` (renombrado de `docker-compose.yml`) con labels de Traefik, sin puerto 8000 público, healthcheck del contenedor y orden de ejecución reproducible.

Acceptance criteria:

- **AC1:** `docker-compose.app.yml` reemplaza a `docker-compose.yml` (el viejo se elimina). El servicio está en la red compartida externa.
- **AC2:** Sin `ports` publicados (entrada única por Traefik); `expose: "8000"` solo para la red interna.
- **AC3:** Labels Traefik: `traefik.enable=true`, router `pdf-app` `Host(`api.localhost`)` con entrypoint `web`, service `loadbalancer.server.port=8000`, `traefik.docker.network` explícito. **Sin healthcheck de LB de Traefik:** probea con la IP del contenedor y `TrustedHostMiddleware` la rechaza (400); la liveness la cubre el healthcheck de Docker (AC4).
- **AC4:** `healthcheck` del contenedor con python/stdlib (urllib) sobre `/health/live`, `start_period: 10s`.
- **AC4b:** Cada ficha compose declara su propio proyecto (`name:`) para que `up`/`down` no borre contenedores de las otras fichas como "huérfanos"; el volumen de Mongo es externo con nombre fijo.
- **AC5:** `env.example` documenta `DOMAIN_HOST`, `ALLOWED_HOSTS` (opcional, JSON array) y corrige typo `TZ=${TZ}$` de los compose precedentes.
- **AC6:** README actualizado en la lista de archivos (estructura del proyecto).
- **AC7:** `docker compose -f docker-compose.app.yml config` resuelve sin errores.

## Tech Stack
- Docker Compose v2; labels `traefik.http.*`; host de ruteo `api.localhost` (aprobado en clarificación).

## Commands
- Validar: `docker compose -f docker-compose.app.yml config`
- Levantar: `docker compose -f docker-compose.app.yml up -d --build`
- Verificar: `curl -H "Host: api.localhost" http://localhost/health`

## Project Structure
```
docker-compose.app.yml  → servicio app con labels (nuevo, reemplaza docker-compose.yml)
env.example             → actualizado (DOMAIN_HOST / ALLOWED_HOSTS / TZ)
README.md               → sección estructura actualizada
```

## Code Style
- YAML; labels `traefik.http.*`; nombres kebab-case; sin comentarios innecesarios.

## Testing Strategy
- Validación estática con `docker compose config`. La capa de aplicación ya está cubierta por pytest (`app-contract`).

## Boundaries
- **Always:** rutear por entrypoint `web`; host de ruteo dentro de `ALLOWED_HOSTS`; healthcheck (contenedor) apuntando a liveness.
- **Ask first:** volver a publicar el puerto de la app, cambiar el host de ruteo, agregar middlewares Traefik.
- **Never:** exponer la app sin Traefik en staging; hardcodear secretos en labels/env; usar `:latest` en imágenes.

## Success Criteria
- `docker compose config` correcto para los tres archivos.
- Guía final incluye orden exacto de arranque + comandos curl de verificación (`/health`, `/api/v1/documents/`, dashboard).

## Open Questions
- Ninguno.