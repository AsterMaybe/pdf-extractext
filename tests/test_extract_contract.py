"""
Tests de contrato para la API compartida del microservicio de extracción.

Verifican que el contrato OpenAPI (`docs/contract/extract-api.openapi.yaml`)
sigue coincidiendo con lo que el orquestador realmente implementa. Sin este
vínculo, el contrato puede desincronizarse en silencio al evolucionar el
adaptador: justamente el riesgo que motivó documentarlo.
"""

from pathlib import Path

import pytest
import yaml

from app.infrastructure.remote_pdf_processor import (
    CONTENT_FIELD,
    EXTRACT_PATH,
    UPLOAD_FIELD,
)

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "contract" / "extract-api.openapi.yaml"
)

# Códigos de estado que el microservicio puede devolver según su contrato.
EXPECTED_STATUS_CODES = {"200", "400", "413", "422", "500", "504"}


@pytest.fixture(scope="module")
def contract() -> dict:
    """Carga el contrato OpenAPI desde disco."""
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def extract_operation(contract: dict) -> dict:
    """Devuelve la definición de `POST /extract` del contrato."""
    return contract["paths"][EXTRACT_PATH]["post"]


def resolve(contract: dict, node: dict) -> dict:
    """Resuelve una referencia local `$ref` (`#/components/...`) del contrato."""
    ref = node.get("$ref")
    if ref is None:
        return node
    assert ref.startswith("#/"), f"Referencia externa no soportada: {ref}"
    target: object = contract
    for segment in ref.removeprefix("#/").split("/"):
        target = target[segment]  # type: ignore[index]
    return resolve(contract, target)  # type: ignore[arg-type]


def problem_body(contract: dict, extract_operation: dict, status_code: str) -> dict:
    """Devuelve el cuerpo `application/problem+json` de una respuesta de error."""
    response = resolve(contract, extract_operation["responses"][status_code])
    return response["content"]["application/problem+json"]


class TestContractIsWellFormed:
    def test_declares_openapi_3(self, contract: dict):
        assert contract["openapi"].startswith("3.")

    def test_declares_a_title_and_version(self, contract: dict):
        assert contract["info"]["title"]
        assert contract["info"]["version"]

    def test_declares_the_problem_schema(self, contract: dict):
        problem = contract["components"]["schemas"]["Problem"]
        assert set(problem["required"]) == {"type", "title", "status", "detail", "instance"}


class TestExtractOperationMatchesImplementation:
    def test_path_matches_the_path_used_by_the_adapter(self, extract_operation: dict):
        assert extract_operation["operationId"] == "extractText"

    def test_request_body_is_multipart_with_the_file_field(
        self, extract_operation: dict
    ):
        schema = extract_operation["requestBody"]["content"]["multipart/form-data"][
            "schema"
        ]
        assert schema["required"] == [UPLOAD_FIELD]
        assert schema["properties"][UPLOAD_FIELD]["format"] == "binary"

    def test_success_response_declares_the_fields_the_adapter_reads(
        self, extract_operation: dict
    ):
        schema = extract_operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ]
        assert CONTENT_FIELD in schema["properties"]
        assert "page_count" in schema["properties"]

    def test_declares_exactly_the_known_status_codes(self, extract_operation: dict):
        assert set(extract_operation["responses"]) == EXPECTED_STATUS_CODES

    def test_client_errors_use_rfc9457_problem_documents(
        self, contract: dict, extract_operation: dict
    ):
        for status_code in ("400", "413", "422"):
            body = problem_body(contract, extract_operation, status_code)
            assert body["schema"] == {"$ref": "#/components/schemas/Problem"}

    def test_invalid_file_codes_are_distinguished(
        self, contract: dict, extract_operation: dict
    ):
        """400 y 422 se distinguen en el contrato: el adaptador los mapea distinto."""
        invalid_file = problem_body(contract, extract_operation, "400")["example"]["type"]
        malformed = problem_body(contract, extract_operation, "422")["example"]["type"]
        assert invalid_file != malformed
