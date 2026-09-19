"""
Tests unitarios de `DocumentService` con dobles de puertos (sin frameworks).

Aíslan la lógica de aplicación de infraestructura y Pydantic: verifican el
encapsulamiento de `get_changes()`, el paso del `PageQuery` como VO y la red de
seguridad TOCTOU propagada por el repositorio.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.domain.exceptions import DocumentAlreadyExistsError
from app.domain.pagination import PageQuery
from app.services.document_service import DocumentService


class _FakeRepo:
    """Doble determinista de `IDocumentRepository`."""

    def __init__(self) -> None:
        self.exists = False
        self.create_error: Exception | None = None
        self.created: DocumentCreate | None = None
        self.updated: tuple[str, dict[str, object]] | None = None
        self.found_by_id = _make_response()
        self.listed_with: PageQuery | None = None

    async def exists_by_checksum(self, checksum: str) -> bool:
        return self.exists

    async def create(self, data: DocumentCreate) -> DocumentResponse:
        if self.create_error is not None:
            raise self.create_error
        self.created = data
        return _make_response()

    async def get_all(self, query: PageQuery) -> list[DocumentResponse]:
        self.listed_with = query
        return []

    async def get_by_id(self, doc_id: str) -> DocumentResponse:
        return self.found_by_id

    async def update(self, doc_id: str, changes: dict[str, object]) -> DocumentResponse:
        self.updated = (doc_id, changes)
        return self.found_by_id

    async def delete(self, doc_id: str) -> None:
        return None


class _FakeProcessor:
    """Doble determinista de `IPDFProcessor`."""

    async def validate_format(self, file_bytes: bytes) -> None:
        return None

    async def compute_checksum(self, file_bytes: bytes) -> str:
        return "fake-checksum"

    async def extract_text(self, file_bytes: bytes) -> str:
        return "texto extraído"


def _make_response() -> DocumentResponse:
    return DocumentResponse(
        id="60d5ecb8b392d70008051234",
        filename="dummy.pdf",
        text_content="texto",
        checksum="fake-checksum",
        file_size_bytes=1024,
        created_at=datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc),
    )


def _make_service() -> tuple[DocumentService, _FakeRepo]:
    repo = _FakeRepo()
    return DocumentService(repo=repo, pdf_processor=_FakeProcessor()), repo


class TestUpdateDocument:
    async def test_sends_only_provided_fields(self):
        service, repo = _make_service()
        update = DocumentUpdate(filename="renombrado.pdf")

        await service.update_document("doc-id", update)

        assert repo.updated == ("doc-id", {"filename": "renombrado.pdf"})

    async def test_empty_update_reads_by_id_without_writing(self):
        service, repo = _make_service()

        result = await service.update_document("doc-id", DocumentUpdate())

        assert result is repo.found_by_id
        assert repo.updated is None

    async def test_falsy_explicit_value_is_still_forwarded(self):
        service, repo = _make_service()
        update = DocumentUpdate(text_content="")

        await service.update_document("doc-id", update)

        assert repo.updated == ("doc-id", {"text_content": ""})


class TestListDocuments:
    async def test_forwards_page_query_verbatim(self):
        service, repo = _make_service()
        query = PageQuery(skip=5, limit=25)

        await service.list_documents(query)

        assert repo.listed_with == query


class TestProcessAndStore:
    async def test_persists_document_with_checksum_and_size(self):
        service, repo = _make_service()

        result = await service.process_and_store_document(b"%PDF-data", "input.pdf")

        assert repo.created is not None
        assert repo.created.checksum == "fake-checksum"
        assert repo.created.file_size_bytes == len(b"%PDF-data")
        assert result.id == "60d5ecb8b392d70008051234"

    async def test_pre_check_short_circuits_before_create(self):
        service, repo = _make_service()
        repo.exists = True

        with pytest.raises(DocumentAlreadyExistsError):
            await service.process_and_store_document(b"%PDF-data", "input.pdf")

        assert repo.created is None

    async def test_race_winner_rejects_second_insert_with_domain_error(self):
        """TOCTOU: el repo rechaza atómicamente el duplicado y el servicio propaga."""
        service, repo = _make_service()
        repo.create_error = DocumentAlreadyExistsError("fake-checksum")

        with pytest.raises(DocumentAlreadyExistsError) as exc_info:
            await service.process_and_store_document(b"%PDF-data", "input.pdf")

        assert exc_info.value.code == "DOCUMENT_ALREADY_EXISTS"