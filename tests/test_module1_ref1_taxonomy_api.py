from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.admin_module1_ref_taxonomy import router
from app.models.enums import UserRole
from app.services.module1_ref_runtime_artifacts import validate_module1_ref_runtime


@pytest.fixture(scope="module")
def activation():
    result = validate_module1_ref_runtime("ref1_read")
    assert result.is_valid
    return result


def _client(state, role: UserRole = UserRole.ADMIN) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    test_app.state.module1_ref_runtime = state
    test_app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=role)
    return TestClient(test_app)


def test_endpoint_is_get_only_and_uses_exact_approved_route() -> None:
    route = next(item for item in router.routes if item.path == "/admin/material-hub/ref1-taxonomy")

    assert route.methods == {"GET"}


def test_admin_get_returns_read_only_projection(activation) -> None:
    response = _client(activation).get("/api/v1/admin/material-hub/ref1-taxonomy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "ref1_read"
    assert payload["read_only"] is True
    assert payload["filters_persisted"] is False
    assert payload["ref_only_write_eligibility"] is False
    assert payload["counts"] == {"groups": 37, "material_types": 978}
    assert payload["artifact_set_id"] == "ref-runtime-v1-122079b1c558fefc"
    assert payload["approval_id"] == "ref1-read-v1-1a15fed6ebdd"


def test_records_use_approved_read_only_fields_without_db_ids_or_routes(activation) -> None:
    payload = _client(activation).get("/api/v1/admin/material-hub/ref1-taxonomy").json()
    expected_fields = {"code", "name_ru", "canonical_parent", "read_status", "artifact_set_id"}

    assert set(payload["groups"][0]) == expected_fields
    assert set(payload["material_types"][0]) == expected_fields
    serialized = str(payload).lower()
    assert "uuid" not in serialized
    assert "database_id" not in serialized
    assert "filesystem" not in serialized
    assert "mutation_route" not in serialized


def test_ref_only_record_is_marked_read_only_and_not_a_write_payload(activation) -> None:
    response = _client(activation).get(
        "/api/v1/admin/material-hub/ref1-taxonomy",
        params={"code": "acoustic_ceiling_panel"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"] == {"groups": 0, "material_types": 1}
    record = payload["material_types"][0]
    assert record["read_status"] == "REF_ONLY_READ_ONLY"
    assert record["canonical_parent"] == "ceiling_systems"


def test_liquid_waterproofing_has_single_canonical_ref_parent(activation) -> None:
    payload = _client(activation).get(
        "/api/v1/admin/material-hub/ref1-taxonomy",
        params={"code": "liquid_waterproofing"},
    ).json()

    assert len(payload["material_types"]) == 1
    assert payload["material_types"][0]["canonical_parent"] == "waterproofing"


def test_filters_are_stateless_and_unknown_stale_code_is_empty_safe(activation) -> None:
    client = _client(activation)

    filtered = client.get(
        "/api/v1/admin/material-hub/ref1-taxonomy",
        params={"name": "акуст", "parent": "ceiling_systems"},
    )
    stale = client.get(
        "/api/v1/admin/material-hub/ref1-taxonomy",
        params={"code": "stale_ref_only_code"},
    )

    assert filtered.status_code == 200
    assert filtered.json()["filters_persisted"] is False
    assert stale.status_code == 200
    assert stale.json()["counts"] == {"groups": 0, "material_types": 0}


def test_client_cannot_override_fixed_purpose(activation) -> None:
    client = _client(activation)
    baseline = client.get(
        "/api/v1/admin/material-hub/ref1-taxonomy",
        params={"code": "acoustic_ceiling_panel"},
    )
    attempted_override = client.get(
        "/api/v1/admin/material-hub/ref1-taxonomy",
        params={"code": "acoustic_ceiling_panel", "purpose": "material_write"},
        headers={"X-Module1-Ref-Purpose": "material_write"},
    )

    assert attempted_override.status_code == 200
    assert attempted_override.json() == baseline.json()


def test_endpoint_requires_admin_role(activation) -> None:
    response = _client(activation, UserRole.SUPPLIER).get(
        "/api/v1/admin/material-hub/ref1-taxonomy"
    )

    assert response.status_code == 403


@pytest.mark.parametrize("mode", ["legacy", "artifact_validation", "dual_read"])
def test_endpoint_is_unavailable_outside_ref1_read(mode: str) -> None:
    response = _client(validate_module1_ref_runtime(mode)).get(
        "/api/v1/admin/material-hub/ref1-taxonomy"
    )

    assert response.status_code == 404


def test_mutation_methods_are_not_registered(activation) -> None:
    client = _client(activation)
    path = "/api/v1/admin/material-hub/ref1-taxonomy"

    assert client.post(path).status_code == 405
    assert client.put(path).status_code == 405
    assert client.patch(path).status_code == 405
    assert client.delete(path).status_code == 405
