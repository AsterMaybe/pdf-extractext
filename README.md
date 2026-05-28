
# PDF-ExtracText



Extraer texto de un pdf que es proporcionado por el usuario.

## Integrantes del Equipo

* Agustin Chaumont


* Genaro De Boni


* Yair Ezequiel Mautino


* Pablo Burgos



## Tecnologías



* Python

* UV (gestor de dependencias)

* Base de datos no relacional MongoDB

* Docker



## Metodologías



* TDD (Test-Driven Development)

* Los seis primeros principios de 12factorapp



## Principios de Programación



* KISS (Keep It Simple, Stupid)

* DRY (Don't Repeat Yourself)

* YAGNI (You Aren't Gonna Need It)

* SOLID



## Requisitos
* Python 3.14 o superior

* pip o uv (recomendado uv)

* Docker (recomendado para la ejecución mediante contenedores)


### Dependencias del Proyecto



Las dependencias se encuentran especificadas en el archivo `pyproject.toml` e incluyen:

* FastAPI

* Uvicorn

* PyMuPDF4LLM (fitz)

* Requests

* MongoDB driver asíncrono (Motor / pymongo)

* Pydantic y Pydantic Settings



## Instalación y Setup



### 1. Clonar el Repositorio



```bash
git clone https://github.com/AsterMaybe/pdf-extractext.git
cd pdf-extractext

```

### 2. Configurar Variables de Entorno



Crea un archivo `.env` en la raíz del proyecto (al mismo nivel que `docker-compose.yml`) con las siguientes variables necesarias para la base de datos y la configuración de la aplicación:

```env
MONGO_USER=admin
MONGO_PASSWORD=password
MONGO_NAME=pdf_db
MONGO_COLLECTION=extracted_texts
PDF_MAX_SIZE_MB=5
SHARED_NETWORK_NAME=network_name

```

## Cómo Ejecutar la Aplicación



### Opción 1: Con Docker Compose (Recomendado)



```bash
# 1. Crear la red externa (usando el nombre que definiste en tu .env)
docker network create network_name

# 2. Levantar la base de datos en segundo plano
docker compose -f docker-compose.db.yml up -d

# 3. Construir la imagen y levantar la aplicación en segundo plano
docker compose up --build -d

```

Una vez que los contenedores estén corriendo, la API interactiva estará disponible en:
**[http://localhost:8000/docs](https://www.google.com/search?q=http://localhost:8000/docs)**

*Nota: Si modificas el archivo `.env` después de la primera ejecución, es necesario destruir el volumen de la base de datos para que tome las nuevas credenciales de inicialización ejecutando `docker compose -f docker-compose.db.yml down -v` antes de volver a levantarla con `docker compose -f docker-compose.db.yml up -d`.*

### Opción 2: Ejecución Local (Sin Docker)



Si prefieres correr el código localmente sin contenedores (requiere tener una instancia de MongoDB corriendo localmente en el puerto 27017):

```bash
# 1. Instalar UV (si no lo tienes)
pip install uv

# 2. Crear entorno virtual y sincronizar dependencias
uv venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
uv sync

# 3. Ejecutar la aplicación
uvicorn app.main:app --reload

```

La aplicación estará disponible en `http://localhost:8000/docs`

## Cómo Ejecutar los Tests



### Ejecutar Todos los Tests



```bash
# Con pytest
pytest

# O con uv
uv run pytest

```

### Ejecutar Tests Específicos



```bash
# Tests de una carpeta específica
pytest tests/unit/

# Tests de un archivo específico
pytest tests/test_extract.py

# Tests con un patrón específico
pytest -k "test_pdf"

```

## Estructura del Proyecto



```text
pdf-extractext/
├── app/
│     ├── config/           # Configuraciones generales (ej. Pydantic Settings y .env).
│     ├── controllers/      # Recibe las peticiones del usuario (ej. rutas web) y devuelve la respuesta. No lleva lógica.
│     ├── domain/           # Todo lo que sea para transformar el documento de pdf a texto, extraer, resumirlo.
│     ├── presentation/     # Relacionado con CRUD y el formato de los datos de salida.
│     ├── services/         # Utiliza lo que está en domain (clases, objetos) para orquestar la lógica de negocio.
│     └── util/             # Herramientas genéricas (cálculos de checksum, validaciones) reutilizables.
├── tests/                  # Tests unitarios e integración
├── docker-compose.db.yml   # Orquestación de la base de datos MongoDB
├── docker-compose.yml      # Orquestación de la aplicación FastAPI
├── pyproject.toml          # Configuración del proyecto y dependencias
├── .env                    # Variables de entorno locales (NO subir a Git)
├── README.md               # Este archivo
└── .gitignore              # Archivos y carpetas ignorados por Git

```

## Recursos Útiles



* [Documentación de FastAPI](https://fastapi.tiangolo.com/)

* [Documentación de UV](https://docs.astral.sh/uv/)

* [Documentación de MongoDB](https://www.mongodb.com/docs/)

* [12 Factor App](https://12factor.net/)