"""
Puertos (Ports) de la capa de aplicación.

Define las abstracciones que `DocumentService` necesita para cumplir su rol de
orquestador (Hexagonal / Ports & Adapters):

- `IDocumentRepository`: contrato de persistencia. Aislado de la implementación
  concreta de MongoDB → DIP.
- `IPDFProcessor`: contrato de procesamiento de PDF (validación, checksum,
  extracción). Permite un test doble sin monkeypatching → TDD-ready.

La implementación concreta de cada puerto vive en `app/services` y
`app/repositories`, y se inyecta por constructor desde la "composition root"
(`app/api/dependencies.py`).
"""

from typing import Protocol

from app.domain.document import DocumentCreate, DocumentResponse
from app.domain.pagination import PageQuery


class IDocumentRepository(Protocol):
    """Contrato mínimo que `DocumentService` exige a su repositorio."""

    async def exists_by_checksum(self, checksum: str) -> bool: ...

    async def create(self, data: DocumentCreate) -> DocumentResponse: ...

    async def get_all(self, query: PageQuery) -> list[DocumentResponse]: ...

    async def get_by_id(self, doc_id: str) -> DocumentResponse: ...

    async def update(self, doc_id: str, changes: dict[str, object]) -> DocumentResponse: ...

    async def delete(self, doc_id: str) -> None: ...


class IPDFProcessor(Protocol):
    """Contrato de procesamiento de PDF que `DocumentService` exige.

    Todos los métodos son `async`: las operaciones de validación, checksum y
    extracción pueden ser CPU/I/O intensivas, y el adaptador concreto debe
    descargarlas a un thread pool (`asyncio.to_thread`) para no bloquear el
    event loop. La capa de presentación (`read_upload_bytes`) ya aplica el
    límite de tamaño, por eso no forma parte del contrato (DRY).
    """

    async def validate_format(self, file_bytes: bytes) -> None: ...

    async def compute_checksum(self, file_bytes: bytes) -> str: ...

    async def extract_text(self, file_bytes: bytes) -> str: ...


class IHealthRepository(Protocol):
    """Contrato de verificación de disponibilidad que `HealthService` exige."""

    async def ping(self) -> bool: ...