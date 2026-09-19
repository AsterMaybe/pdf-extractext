# Spec: traefik-infra (Capability id: `traefik-infra`)

## Objective
Entregar la infraestructura de Traefik como API gateway del monolito: configuración estática (`traefik.yml`), `docker-compose.traefik.yml` separado y estrategia de red compartida.

Acceptance criteria:

- **AC1:** `traefik.yml` con entrypoint `web` (`:80`), dashboard de desarrollo, provider `docker` (endpoint unix socket, `exposedByDefault: false`, watch activo). **Sin interpolación de entorno dentro del archivo estático** (no soportada de forma determinista por Traefik).
- **AC2:** `docker-compose.traefik.yml` con imagen `traefik:v3.7` (tag explícito), monta `/var/run/docker.sock` (read-only) y `./traefik.yml` (read-only), publica `80:80` (web) y `8080:8080` (dashboard/api), conectado a la red externa compartida.
- **AC3:** Resolver Let's Encrypt documentado como bloque comentado (fuera de alcance en esta fase HTTP-only).
- **AC4:** `docker compose -f docker-compose.traefik.yml config` resuelve sin errores (validación offline).
- **AC5:** La red compartida es la MISMA en los tres compose files (mismo `${SHARED_NETWORK_NAME}`), es `external: true` en todos (no la crea ningún compose) y se crea explícitamente con `docker network create`.

## Tech Stack / Dependencies
- Imagen `traefik:v3.7` (Traefik 3.7.x es la rama estable actual, tag conforme a la convención del repo: sin `:latest`).

## Commands
- Validar: `docker compose -f docker-compose.traefik.yml config`
- Levantar: `docker compose -f docker-compose.traefik.yml up -d`
- Logs: `docker compose -f docker-compose.traefik.yml logs -f`

## Project Structure
```
traefik.yml               → configuración estática (raíz del proyecto)
docker-compose.traefik.yml → servicio traefik (raíz del proyecto)
```

## Code Style
- YAML; keys de Traefik en la forma documentada; router/service en kebab-case (`pdf-app`); servicio compose llamado `traefik`.

## Testing Strategy
- Validación estática con `docker compose config` (no requiere engine). Smoke runtime documentado como comandos (requiere Docker Desktop corriendo).
- No hay tests pytest para infra en este repo; la capa de app está cubierta en `app-contract`.

## Boundaries
- **Always:** tag explícito `traefik:v3.7`; docker.sock montado con `:ro`; `exposedByDefault: false` para que mongo/app no queden expuestos por default.
- **Ask first:** cambiar entrypoints, habilitar TLS/https, publicar puertos adicionales.
- **Never:** usar `:latest`; dashboard `insecure: true` en producción; montar docker.sock en modo escritura.

## Success Criteria
- `docker compose config` renderiza el servicio traefik + red externa sin errores.
- Guía documenta smoke test: dashboard en `http://localhost:8080` (verificación manual, requiere Docker).

## Open Questions
- Ninguno (HTTP-only aprobado).