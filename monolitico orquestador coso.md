# Study - Monolitico (pdf-extractext)

## Estructura del proyecto

```
monolitico/
├── app/
│   ├── api/
│   │   ├── dependencies.py        # Composicion de dependencias (DIP)
│   │   ├── exception_handlers.py  # Handlers RFC 9457
│   │   ├── problems.py            # Constructor de respuestas RFC 9457
│   │   └── uploads.py             # Adaptador de entrada HTTP para uploads
│   ├── config/
│   │   ├── config.py              # Configuracion centralizada (Pydantic Settings)
│   │   └── logging_config.py      # Configuracion de logging
│   ├── controllers/
│   │   ├── document_controller.py # Rutas de documentos
│   │   ├── health_controller.py   # Rutas de salud
│   │   └── traefik_error_controller.py # Fallback de errores de Traefik
│   ├── domain/
│   │   ├── document.py            # Modelos de documento
│   │   ├── exceptions.py          # Jerarquia de errores de dominio
│   │   ├── pagination.py          # Objeto de valor de paginacion
│   │   └── problem_detail.py      # Modelo RFC 9457
│   ├── infrastructure/
│   │   └── remote_pdf_processor.py # Adaptador HTTP al microservicio de extraccion
│   ├── repositories/
│   │   ├── http_document_repo.py  # Cliente HTTP hacia microservicio de persistencia
│   │   └── http_health_repo.py    # Cliente HTTP de health hacia microservicio
│   ├── services/
│   │   ├── document_service.py    # Orquestacion de logica de documentos
│   │   ├── health_service.py      # Orquestacion de salud
│   │   └── ports.py               # Puertos (Protocols) de la app
│   └── main.py                    # Punto de entrada FastAPI
├── tests/                         # Tests unitarios e integracion (pytest)
├── docs/                          # Documentacion adicional
├── docker-compose.app.yml
├── docker-compose.traefik.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Modulos

### app/main.py
Punto de entrada de la aplicacion FastAPI; configura middlewares, handlers y routers.

Funciones:
- `lifespan(app)` - Gestiona el ciclo de vida de la app, creando y cerrando el cliente HTTP compartido.

### app/config/config.py
Configuracion centralizada tipada con Pydantic Settings.

Funciones:
- (Sin funciones; define la clase `Settings` y la instancia global `settings`.)

### app/config/logging_config.py
Configuracion centralizada del logging de la aplicacion y de uvicorn.

Funciones:
- `setup_logging()` - Configura el formatter, handlers y niveles de logging.

### app/api/dependencies.py
Composicion de dependencias (DIP) que expone abstracciones a los consumidores.

Funciones:
- `_get_http_client(request)` - Devuelve el cliente HTTP compartido gestionado por el lifespan.
- `get_document_repo(request)` - Retorna el adaptador HTTP del microservicio de persistencia.
- `get_pdf_processor()` - Instancia el adaptador de procesamiento de PDF.
- `get_document_service(repo, pdf_processor)` - Compone el servicio de documentos.
- `get_health_repo(request)` - Retorna el adaptador HTTP para el health check.
- `get_health_service(health_repo)` - Compone el servicio de salud.

### app/api/exception_handlers.py
Handlers consolidados de error RFC 9457 para la aplicacion.

Funciones:
- `_type_uri(slug)` - Construye la URI de tipo de error a partir de un slug.
- `http_exception_handler(request, exc)` - Maneja errores HTTP estandar de Starlette/FastAPI.
- `validation_exception_handler(request, exc)` - Maneja errores de validacion (422).
- `domain_error_handler(request, exc)` - Maneja errores de dominio segun su codigo.
- `unhandled_error_handler(request, exc)` - Maneja errores inesperados (500).
- `install_exception_handlers(app)` - Registra todos los handlers sobre FastAPI.

### app/api/problems.py
Constructor unico de respuestas de error RFC 9457.

Funciones:
- `build_problem_response(request, status_code, detail, ...)` - Construye una respuesta RFC 9457 a partir del request y el detalle.

### app/api/uploads.py
Adaptador de entrada HTTP que convierte UploadFile en bytes.

Funciones:
- `read_upload_bytes(upload)` - Lee el upload en chunks y aborta si supera el tamano maximo.

### app/controllers/document_controller.py
Controlador de rutas HTTP para documentos; delega la logica al servicio.

Funciones:
- `upload_document(file, service)` - Endpoint POST /upload para subir un PDF.
- `list_documents(skip, limit, service)` - Endpoint GET / para listar documentos paginados.
- `get_document(doc_id, service)` - Endpoint GET /{doc_id} para obtener un documento.
- `update_document(doc_id, update_data, service)` - Endpoint PATCH /{doc_id} para actualizar parcialmente.
- `delete_document(doc_id, service)` - Endpoint DELETE /{doc_id} para eliminar un documento.

### app/controllers/health_controller.py
Controlador de rutas HTTP de salud y liveness.

Funciones:
- `health_live()` - Endpoint de liveness para balanceadores.
- `health_check(request, service)` - Endpoint de health profundo verificando la BD.

### app/controllers/traefik_error_controller.py
Controlador de fallback para errores generados por Traefik.

Funciones:
- `traefik_rate_limited(request)` - Devuelve respuesta RFC 9457 para rate limit (429).
- `traefik_service_unavailable(request)` - Devuelve respuesta RFC 9457 para circuit breaker (503).

### app/domain/document.py
Modelos de datos de documento (Pydantic).

Funciones:
- `DocumentUpdate.get_changes()` - Devuelve solo los campos provistos por el cliente (PATCH semantico).

### app/domain/exceptions.py
Jerarquia de errores de dominio con codigo estable.

Funciones:
- `DomainError.__init__(code, detail)` - Inicializa el error base con codigo y detalle.
- `DomainError.__str__()` - Devuelve el detalle del error.
- `DocumentNotFoundError.__init__(doc_id)` - Error cuando no se encuentra un documento.
- `InvalidDocumentIdError.__init__(doc_id)` - Error cuando el id es invalido.
- `FileSizeExceededError.__init__(max_size_mb)` - Error cuando se supera el tamano maximo.
- `InvalidPDFFormatError.__init__(detail)` - Error cuando el archivo no es PDF valido.
- `PDFProcessingError.__init__(detail)` - Error cuando falla el procesamiento del PDF.
- `DocumentAlreadyExistsError.__init__(checksum)` - Error cuando el documento ya existe.

### app/domain/pagination.py
Objeto de valor de paginacion para consultas de listado.

Funciones:
- (Sin funciones; define el dataclass `PageQuery`.)

### app/domain/problem_detail.py
Modelo estandarizado de errores segun RFC 9457.

Funciones:
- (Sin funciones; define la clase `ProblemDetail`.)

### app/infrastructure/remote_pdf_processor.py
Adaptador que delega la extraccion de texto al microservicio Go.

Funciones:
- `compute_checksum(file_bytes)` - Calcula el hash SHA-256 de los bytes.
- `validate_pdf_format(file_bytes)` - Comprueba los magic bytes del PDF.
- `RemotePdfProcessor.__init__(base_url)` - Inicializa el adaptador con la URL base.
- `RemotePdfProcessor.validate_format(file_bytes)` - Valida el formato del PDF.
- `RemotePdfProcessor.compute_checksum(file_bytes)` - Calcula el checksum del archivo.
- `RemotePdfProcessor.extract_text(file_bytes)` - Extrae el texto del PDF via HTTP.

### app/repositories/http_document_repo.py
Cliente HTTP hacia el microservicio Go de persistencia de documentos.

Funciones:
- `HttpDocumentRepository.__init__(base_url, timeout, client)` - Inicializa el repositorio HTTP.
- `HttpDocumentRepository._get_client()` - Obtiene el cliente HTTP compartido o crea uno.
- `HttpDocumentRepository._close_if_owned()` - Cierra el cliente si es propio.
- `HttpDocumentRepository.exists_by_checksum(checksum)` - Verifica duplicados por checksum.
- `HttpDocumentRepository.create(data)` - Crea un documento via POST.
- `HttpDocumentRepository.get_all(query)` - Lista documentos con paginacion.
- `HttpDocumentRepository.get_by_id(doc_id)` - Obtiene un documento por ID.
- `HttpDocumentRepository.update(doc_id, changes)` - Actualiza un documento via PATCH.
- `HttpDocumentRepository.delete(doc_id)` - Elimina un documento via DELETE.
- `HttpDocumentRepository.ensure_indexes()` - No-op; los indices los gestiona el microservicio Go.
- `HttpDocumentRepository._handle_error(response, checksum, doc_id)` - Convierte error HTTP en excepcion de dominio.

### app/repositories/http_health_repo.py
Cliente HTTP de health hacia el microservicio Go.

Funciones:
- `HttpHealthRepository.__init__(base_url, timeout, client)` - Inicializa el repositorio HTTP.
- `HttpHealthRepository._get_client()` - Obtiene el cliente HTTP compartido o crea uno.
- `HttpHealthRepository._close_if_owned()` - Cierra el cliente si es propio.
- `HttpHealthRepository.ping()` - Verifica disponibilidad del microservicio Go.

### app/services/document_service.py
Orquesta la logica de negocio de documentos sobre los puertos.

Funciones:
- `DocumentService.__init__(repo, pdf_processor)` - Inicializa el servicio con sus dependencias.
- `DocumentService.process_and_store_document(file_bytes, filename)` - Valida, extrae y persiste un PDF.
- `DocumentService.list_documents(query)` - Lista documentos paginados.
- `DocumentService.get_by_id(doc_id)` - Obtiene un documento por ID.
- `DocumentService.update_document(doc_id, update_data)` - Actualiza parcialmente un documento.
- `DocumentService.delete(doc_id)` - Elimina un documento.

### app/services/health_service.py
Servicio de salud que orquesta el ping a la base de datos.

Funciones:
- `HealthService.__init__(health_repo)` - Inicializa el servicio con el repositorio de salud.
- `HealthService.database_is_healthy()` - Devuelve True si la base responde al ping.

### app/services/ports.py
Definicion de los puertos (Protocols) de la aplicacion.

Funciones:
- `IDocumentRepository.exists_by_checksum(checksum)` - Contrato para verificar duplicados.
- `IDocumentRepository.create(data)` - Contrato para crear un documento.
- `IDocumentRepository.get_all(query)` - Contrato para listar documentos.
- `IDocumentRepository.get_by_id(doc_id)` - Contrato para obtener por ID.
- `IDocumentRepository.update(doc_id, changes)` - Contrato para actualizar.
- `IDocumentRepository.delete(doc_id)` - Contrato para eliminar.
- `IPDFProcessor.validate_format(file_bytes)` - Contrato para validar formato PDF.
- `IPDFProcessor.compute_checksum(file_bytes)` - Contrato para calcular checksum.
- `IPDFProcessor.extract_text(file_bytes)` - Contrato para extraer texto.
- `IHealthRepository.ping()` - Contrato para verificar disponibilidad.
", path: C:\Users\Aster\Desktop\Proyecto\monolitico\study.md