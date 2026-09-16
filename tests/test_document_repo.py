"""
Tests unitarios para el repositorio de documentos.
Se mockea AsyncIOMotorCollection para no depender de una BD real,
alineándose con la metodología TDD y test de unidad rápidos.
"""

import pytest
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from unittest.mock import AsyncMock, MagicMock

from app.domain.document import DocumentCreate
from app.domain.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    InvalidDocumentIdError,
)
from app.repositories.document_repo import DocumentRepository


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_collection():
    """Retorna un mock asíncrono de la colección de MongoDB."""
    return AsyncMock()


@pytest.fixture
def repo(mock_collection):
    """Instancia el repositorio inyectando la colección mockeada."""
    return DocumentRepository(collection=mock_collection)


@pytest.fixture
def valid_object_id():
    return str(ObjectId())


@pytest.fixture
def sample_doc_create():
    return DocumentCreate(
        filename="test.pdf",
        text_content="Contenido de prueba",
        checksum="abcd1234efgh5678",
        file_size_bytes=1024
    )


@pytest.fixture
def sample_mongo_doc(valid_object_id):
    return {
        "_id": ObjectId(valid_object_id),
        "filename": "test.pdf",
        "text_content": "Contenido de prueba",
        "checksum": "abcd1234efgh5678",
        "file_size_bytes": 1024,
        "created_at": "2026-05-20T10:00:00Z"  # Simulación de fecha
    }


# ── Tests ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDocumentRepository:

    async def test_exists_by_checksum_true(self, repo, mock_collection):
        mock_collection.find_one.return_value = {"_id": ObjectId()}
        result = await repo.exists_by_checksum("abcd1234efgh5678")
        assert result is True
        mock_collection.find_one.assert_awaited_once_with({"checksum": "abcd1234efgh5678"}, {"_id": 1})

    async def test_exists_by_checksum_false(self, repo, mock_collection):
        mock_collection.find_one.return_value = None
        result = await repo.exists_by_checksum("nuevo_checksum")
        assert result is False

    async def test_create_document(self, repo, mock_collection, sample_doc_create, sample_mongo_doc):
        # Simular el resultado de insert_one (que ya trae el _id generado)
        mock_insert_result = MagicMock()
        mock_insert_result.inserted_id = sample_mongo_doc["_id"]
        mock_collection.insert_one.return_value = mock_insert_result

        result = await repo.create(sample_doc_create)

        assert result.id == str(sample_mongo_doc["_id"])
        assert result.filename == "test.pdf"
        assert result.text_content == "Contenido de prueba"
        # KISS: no se re-consulta la BD después de insertar.
        mock_collection.insert_one.assert_awaited_once()
        mock_collection.find_one.assert_not_awaited()

    async def test_ensure_indexes_creates_unique_checksum(self, repo, mock_collection):
        """La garantía anti-duplicados se materializa en un índice único."""
        await repo.ensure_indexes()
        mock_collection.create_index.assert_awaited_once_with("checksum", unique=True)

    async def test_create_raises_domain_error_on_duplicate_key(self, repo, mock_collection, sample_doc_create):
        """Carrera TOCTOU: la BD rechaza el duplicado y el repo lo traduce al dominio."""
        mock_collection.insert_one.side_effect = DuplicateKeyError("E11000 duplicate key error")

        with pytest.raises(DocumentAlreadyExistsError) as exc_info:
            await repo.create(sample_doc_create)

        assert exc_info.value.code == "DOCUMENT_ALREADY_EXISTS"
        assert "abcd1234efgh5678" in str(exc_info.value)

    async def test_get_by_id_success(self, repo, mock_collection, sample_mongo_doc, valid_object_id):
        mock_collection.find_one.return_value = sample_mongo_doc
        result = await repo.get_by_id(valid_object_id)

        assert result.id == valid_object_id
        mock_collection.find_one.assert_awaited_once_with({"_id": ObjectId(valid_object_id)})

    async def test_get_by_id_not_found_raises_domain_error(self, repo, mock_collection, valid_object_id):
        mock_collection.find_one.return_value = None
        with pytest.raises(DocumentNotFoundError) as exc_info:
            await repo.get_by_id(valid_object_id)
        assert f"Documento con id '{valid_object_id}' no encontrado." == str(exc_info.value)

    async def test_get_by_id_invalid_format_raises_domain_error(self, repo):
        with pytest.raises(InvalidDocumentIdError) as exc_info:
            await repo.get_by_id("id_invalido_no_hex")
        assert exc_info.value.code == "INVALID_DOCUMENT_ID"

    async def test_update_success(self, repo, mock_collection, sample_mongo_doc, valid_object_id):
        changes = {"filename": "renombrado.pdf"}
        updated_doc = {**sample_mongo_doc, **changes}
        mock_collection.find_one_and_update.return_value = updated_doc

        result = await repo.update(valid_object_id, changes)

        assert result.filename == "renombrado.pdf"
        mock_collection.find_one_and_update.assert_awaited_once_with(
            {"_id": ObjectId(valid_object_id)},
            {"$set": changes},
            return_document=ReturnDocument.AFTER,
        )

    async def test_update_not_found_raises_domain_error(self, repo, mock_collection, valid_object_id):
        mock_collection.find_one_and_update.return_value = None

        with pytest.raises(DocumentNotFoundError) as exc_info:
            await repo.update(valid_object_id, {"filename": "x.pdf"})
        assert f"Documento con id '{valid_object_id}' no encontrado." == str(exc_info.value)

    async def test_delete_success(self, repo, mock_collection, valid_object_id):
        mock_delete_result = MagicMock()
        mock_delete_result.deleted_count = 1
        mock_collection.delete_one.return_value = mock_delete_result

        await repo.delete(valid_object_id)
        mock_collection.delete_one.assert_awaited_once_with({"_id": ObjectId(valid_object_id)})

    async def test_delete_not_found_raises_domain_error(self, repo, mock_collection, valid_object_id):
        mock_delete_result = MagicMock()
        mock_delete_result.deleted_count = 0
        mock_collection.delete_one.return_value = mock_delete_result

        with pytest.raises(DocumentNotFoundError) as exc_info:
            await repo.delete(valid_object_id)
        assert f"Documento con id '{valid_object_id}' no encontrado." == str(exc_info.value)