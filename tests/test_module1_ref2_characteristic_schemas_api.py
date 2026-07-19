from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.admin_module1_ref2_characteristic_schemas import router as ref2_router
from app.api.v1.admin_module1_ref_taxonomy import router as ref1_router
from app.api.v1.material_hub_view import router as material_hub_router
from app.database import get_db
from app.models.enums import UserRole
from app.services.module1_ref_runtime_artifacts import validate_module1_ref_runtime


@pytest.fixture(scope="module")
def activations():
    return {
        mode: validate_module1_ref_runtime(mode)
        for mode in ("legacy", "artifact_validation", "dual_read", "ref1_read", "ref2_read")
    }


class _EmptyScalarResult:
    def scalars(self):
        return self

    def all(self) -> list:
        return []


class _ReadOnlyFakeDb:
    async def execute(self, _statement):
        return _EmptyScalarResult()


async def _fake_db():
    yield _ReadOnlyFakeDb()


def _client(state, role: UserRole = UserRole.ADMIN) -> TestClient:
    app = FastAPI()
    app.include_router(material_hub_router, prefix="/api/v1")
    app.include_router(ref1_router, prefix="/api/v1")
    app.include_router(ref2_router, prefix="/api/v1")
    app.state.module1_ref_runtime = state
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=role)
    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


@pytest.mark.parametrize("mode", ["legacy", "artifact_validation", "dual_read", "ref1_read", "ref2_read"])
def test_material_hub_html_route_is_200_in_all_modes(activations, mode: str) -> None:
    response = _client(activations[mode]).get("/api/v1/admin/material-hub/view")
    assert response.status_code == 200


def test_endpoint_is_exact_get_only_route() -> None:
    route = next(
        item
        for item in ref2_router.routes
        if item.path == "/admin/material-hub/ref2-characteristic-schemas"
    )
    assert route.methods == {"GET"}


def test_admin_list_contract_and_default_pagination(activations) -> None:
    response = _client(activations["ref2_read"]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "ref2_read"
    assert payload["read_only"] is True
    assert payload["runtime_package_id"] == "ref-runtime-v1-122079b1c558fefc"
    assert payload["ref1_approval_id"] == "ref1-read-v1-1a15fed6ebdd"
    assert payload["ref2_approval_id"] == "ref2-read-v1-1a15fed6ebdd"
    assert payload["total"] == 978
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert len(payload["items"]) == 50
    assert payload["counts"] == {
        "fully_readable": 619,
        "readable_with_warnings": 311,
        "review_excluded": 48,
        "blocked": 0,
    }
    assert payload["compatibility_summary"] == {
        "overlap_total": 46,
        "read_compatible": 21,
        "review_required": 19,
        "required_semantics_mismatch": 6,
        "runtime_only_fields": 28,
        "packaging_mismatches": 345,
        "packaging_affected_material_types": 316,
    }
    assert "fields" not in payload["items"][0]


def test_list_pagination_is_deterministic(activations) -> None:
    client = _client(activations["ref2_read"])
    first = client.get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params={"limit": 2, "offset": 3},
    ).json()
    second = client.get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params={"limit": 2, "offset": 3},
    ).json()
    assert first == second
    assert first["limit"] == 2 and first["offset"] == 3
    assert len(first["items"]) == 2


def test_detail_contract_keeps_required_semantics_and_write_boundaries(activations) -> None:
    response = _client(activations["ref2_read"]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params={"material_type_code": "gypsum_board_regular"},
    )
    assert response.status_code == 200
    item = response.json()["item"]
    assert item["material_type_code"] == "gypsum_board_regular"
    assert item["canonical_group"]["code"] == "drywall_and_sheet_systems"
    assert item["canonical_path"] == ["drywall_and_sheet_systems", "gypsum_board_regular"]
    assert item["read_only"] is True
    assert item["source_profile"]["flattened"] is True
    assert "inheritance" not in item["source_profile"]
    fields = {field["field_code"]: field for field in item["fields"]}
    assert fields["length_mm"]["ref_source_required"] is True
    assert fields["length_mm"]["legacy_effective_required"] is True
    assert all(field["read_only"] is True for field in fields.values())
    assert all(field["eligible_for_material_write"] is False for field in fields.values())
    assert all(field["eligible_for_catalog_product_write"] is False for field in fields.values())
    assert all(field["eligible_for_normalizer_output"] is False for field in fields.values())


def test_review_excluded_detail_is_explicitly_withheld(activations) -> None:
    response = _client(activations["ref2_read"]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params={"material_type_code": "board"},
    )
    assert response.status_code == 200
    item = response.json()["item"]
    assert item["schema_status"] == "review_excluded"
    assert item["field_availability"] == "withheld_pending_review"
    assert item["approved_field_count"] == 0
    assert item["fields"] == []
    assert item["warning_codes"] == ["REF2_ASSIGNMENT_REVIEW_EXCLUDED"]


def test_unknown_material_type_is_404(activations) -> None:
    response = _client(activations["ref2_read"]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params={"material_type_code": "stale_ref2_field_code"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"purpose": "material_write"},
        {"arbitrary": "field"},
    ],
)
def test_query_contract_rejects_invalid_or_unknown_parameters(activations, params) -> None:
    response = _client(activations["ref2_read"]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params=params,
    )
    assert response.status_code == 422


def test_header_cannot_override_server_owned_purpose(activations) -> None:
    client = _client(activations["ref2_read"])
    path = "/api/v1/admin/material-hub/ref2-characteristic-schemas"
    baseline = client.get(path, params={"limit": 1})
    attempted = client.get(
        path,
        params={"limit": 1},
        headers={"X-Module1-Ref-Purpose": "material_write"},
    )
    assert attempted.status_code == 200
    assert attempted.json() == baseline.json()


def test_endpoint_requires_admin_role(activations) -> None:
    response = _client(activations["ref2_read"], UserRole.SUPPLIER).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas"
    )
    assert response.status_code == 403


@pytest.mark.parametrize("mode", ["legacy", "artifact_validation", "dual_read", "ref1_read"])
def test_ref2_endpoint_is_unavailable_in_other_modes(activations, mode: str) -> None:
    response = _client(activations[mode]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas"
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [
        ("legacy", 404),
        ("artifact_validation", 404),
        ("dual_read", 404),
        ("ref1_read", 200),
        ("ref2_read", 200),
    ],
)
def test_ref1_endpoint_mode_dependency(activations, mode: str, expected_status: int) -> None:
    response = _client(activations[mode]).get("/api/v1/admin/material-hub/ref1-taxonomy")
    assert response.status_code == expected_status
    if mode == "ref2_read":
        assert response.json()["counts"] == {"groups": 37, "material_types": 978}
        assert response.json()["mode"] == "ref2_read"


def test_response_has_no_db_ids_paths_raw_payload_or_mutation_routes(activations) -> None:
    payload = _client(activations["ref2_read"]).get(
        "/api/v1/admin/material-hub/ref2-characteristic-schemas",
        params={"material_type_code": "gypsum_board_regular"},
    ).json()
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    for forbidden in (
        "uuid",
        "database_id",
        "orm_id",
        "filesystem",
        "source_pointer",
        "raw_payload",
        "mutation_route",
        "python class",
    ):
        assert forbidden not in serialized


def test_mutation_methods_are_not_registered(activations) -> None:
    client = _client(activations["ref2_read"])
    path = "/api/v1/admin/material-hub/ref2-characteristic-schemas"
    assert client.post(path).status_code == 405
    assert client.put(path).status_code == 405
    assert client.patch(path).status_code == 405
    assert client.delete(path).status_code == 405


def test_list_and_detail_response_times_are_recordable(activations) -> None:
    client = _client(activations["ref2_read"])
    path = "/api/v1/admin/material-hub/ref2-characteristic-schemas"
    started = time.perf_counter()
    assert client.get(path).status_code == 200
    list_duration_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    assert client.get(path, params={"material_type_code": "gypsum_board_regular"}).status_code == 200
    detail_duration_ms = (time.perf_counter() - started) * 1000
    assert list_duration_ms >= 0
    assert detail_duration_ms >= 0
