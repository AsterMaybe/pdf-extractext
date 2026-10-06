# Ejecución integrada con Traefik

## Arquitectura

Los Compose de los repositorios hermanos se conectan por la red externa indicada en `SHARED_NETWORK_NAME` (actualmente `test_network`). Traefik publica solo las APIs de FastAPI y extracción; la API DB y MongoDB permanecen privadas en la red Docker.

- `api.localhost` → orquestador FastAPI (`pdf-extractext/docker-compose.app.yml`, puerto interno 8000).
- `extract.localhost` → extractor Go (`microservicio-extract-go/docker-compose.yml`, puerto interno 8080).
- FastAPI consume `http://api:8080` para extraer y `http://microservicio-db-go:8080` para persistir.
- El stack `microservicio-db-go` inicia MongoDB y su API. Los datos persisten en el volumen Docker `microservicio-db-go_mongo-data`.
- El frontend se publica en `http://localhost:5173`.

## Preparación

Desde la carpeta `Proyecto`, crea `pdf-extractext/.env` a partir de `pdf-extractext/env.example` si todavía no existe. La misma configuración debe usar `test_network` en los Compose del extractor y DB. Crea la red externa una sola vez:

```powershell
docker network create test_network
```

No publiques ni enrutes `mongo` o `microservicio-db-go` en Traefik: el orquestador los consume directamente por la red privada compartida. El Compose conserva el volumen anterior `pdf-extractext_mongo_data`; en una instalación nueva, créalo antes de levantar DB:

```powershell
docker volume create pdf-extractext_mongo_data
```

Si el contenedor `mongo` del Compose anterior sigue activo, detenlo con `docker stop mongo` antes de iniciar el nuevo stack. Ambos usan el mismo volumen; no los ejecutes en paralelo y no borres el volumen.

## Arranque

Ejecuta desde `Proyecto` y respeta este orden para que las dependencias estén listas antes de iniciar FastAPI:

```powershell
docker compose --env-file pdf-extractext/.env -f microservicio-db-go/docker-compose.yml up -d --build
docker compose --env-file pdf-extractext/.env -f microservicio-extract-go/docker-compose.yml up -d --build
docker compose --env-file pdf-extractext/.env -f pdf-extractext/docker-compose.traefik.yml up -d
docker compose --env-file pdf-extractext/.env -f pdf-extractext/docker-compose.app.yml up -d --build
docker compose --env-file pdf-extractext-frontend/.env -f pdf-extractext-frontend/docker-compose.yml up -d --build
```

`depends_on` espera a que MongoDB esté saludable antes de iniciar la API DB. Los demás proyectos Compose son independientes, por eso se levantan explícitamente.

## Verificación

```powershell
docker compose --env-file pdf-extractext/.env -f microservicio-db-go/docker-compose.yml ps
docker compose --env-file pdf-extractext/.env -f microservicio-extract-go/docker-compose.yml ps
docker compose --env-file pdf-extractext/.env -f pdf-extractext/docker-compose.app.yml ps
curl.exe -H "Host: api.localhost" http://localhost/health
curl.exe -H "Host: api.localhost" http://localhost/docs
curl.exe -H "Host: extract.localhost" http://localhost/api/v1/health
```

FastAPI debe responder `200` en `/health` cuando DB Go y Mongo estén disponibles. La documentación de FastAPI queda en `http://api.localhost/docs`; el dashboard de desarrollo de Traefik en `http://localhost:8080/dashboard/`.

Para revisar el descubrimiento de rutas:

```powershell
docker compose --env-file pdf-extractext/.env -f pdf-extractext/docker-compose.traefik.yml logs
```

## Apagado y datos

Baja los servicios con `docker compose ... down` usando los mismos archivos y `--env-file`. No agregues `-v` si quieres conservar los documentos: MongoDB vive en un volumen nombrado administrado por el Compose de DB. Cambiar `MONGO_USER` o `MONGO_PASSWORD` no cambia las credenciales de un volumen ya inicializado.

El dashboard está configurado para desarrollo (`api.insecure: true`); no lo expongas así en producción.
