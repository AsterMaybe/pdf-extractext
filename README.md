# pdf-extractext

Extraer texto de un pdf que es proporcionado por el usuario.

## Integrantes del Equipo

### Nombres y Apellidos:
- Agustin Chaumont
- Genaro De Boni
- Yair Ezequiel Mautino
- Pablo Burgos

## Tecnologías

- Python
- UV (gestor de dependencias)
- Base de datos no relacional MongoDB
- Docker

## Metodologías

- TDD (Test-Driven Development)
- Los seis primeros principios de 12factorapp

## Principios de Programación

- KISS (Keep It Simple, Stupid)
- DRY (Don't Repeat Yourself)
- YAGNI (You Aren't Gonna Need It)
- SOLID


## Requisitos

### Requisitos del Sistema

- Python 3.8 o superior
- pip o uv (recomendado uv)
- Docker (opcional, para containerización)
- MongoDB (acceso a la base de datos)

### Dependencias del Proyecto

Las dependencias se encuentran especificadas en el archivo `pyproject.toml` e incluyen:

- FastAPI
- Uvicorn
- Pymupdf4llm
- Requests
- MongoDB driver (pymongo)


## Instalación y Setup

### 1. Clonar el Repositorio

```bash
git clone https://github.com/AsterMaybe/pdf-extractext.git
cd pdf-extractext
```

### 2. Instalar UV (si no lo tienes)

```bash
pip install uv
```

### 3. Crear un Entorno Virtual e Instalar Dependencias

Con `uv`:

```bash
uv venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

O alternativamente:

```bash
uv sync
```

### 4. Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=pdf_extractext
AI_MODEL_API_KEY=tu_clave_api
ENVIRONMENT=development
```

### 5. Inicializar la Base de Datos

Si es necesario, ejecuta los scripts de inicialización:

```bash
python scripts/init_db.py
```


## Cómo Ejecutar la Aplicación

### Opción 1: Ejecución Local

```bash
# Activar el entorno virtual
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Ejecutar la aplicación
python main.py
```

O si es una aplicación FastAPI:

```bash
uvicorn main:app --reload
```

La aplicación estará disponible en `http://localhost:8000`

### Opción 2: Con Docker

```bash
# Construir la imagen Docker
docker build -t pdf-extractext .

# Ejecutar el contenedor
docker run -p 8000:8000 --env-file .env pdf-extractext
```

## Cómo Ejecutar los Tests

### Ejecutar Todos los Tests

```bash
# Con pytest
pytest

# O con uv
uv run pytest
```

### Ejecutar Tests con Cobertura

```bash
pytest --cov=. --cov-report=html
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

### Ejecutar Tests en Modo Watch

```bash
pytest-watch
```

## Estructura del Proyecto

```
pdf-extractext/
├── app/
      ├── controllers/      # Recibe las peticiones del usuario (ej. rutas web) y devuelve la respuesta. No lleva lógica.
      ├── domain/           # Todo lo que sea para transformar el documento de pdf a texto, extraer, resumirlo, va aca
      ├── presentation      # Lo queesta relacionado con CRUD, va en este repositorio
      ├── services/         # Service va a utilizar lo que esta en domain (clases, objetos) y los va a utilizar para algo
      ├── util/             # Herramientas genéricas (formatear fechas, cálculos, generar IDs) que podrías usar en cualquier otro proyecto.
├── tests/                  # Tests unitarios e integración
├── docker/                 # Configuración Docker
├── pyproject.toml          # Configuración del proyecto y dependencias
├── .env.example            # Ejemplo de variables de entorno
├── Dockerfile              # Configuración de Docker
├── README.md               # Este archivo
└── .gitignore              # Archivo para ignorar en Git
```

## Recursos Útiles

- [Documentación de FastAPI](https://fastapi.tiangolo.com/)
- [Documentación de UV](https://github.com/astral-sh/uv)
- [Documentación de MongoDB](https://docs.mongodb.com/)
- [12 Factor App](https://12factor.net/)

---
