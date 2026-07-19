from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.admin_module1_ref2_characteristic_schemas import router as ref2_router
from app.api.v1.admin_module1_ref3 import router as ref3_router
from app.api.v1.admin_module1_ref_taxonomy import router as ref1_router
from app.api.v1.material_hub_view import router as material_hub_router
from app.database import get_db
from app.models.enums import UserRole
from app.services.module1_ref3_read_policy import Module1Ref3ReadActivation
from app.services.module1_ref_runtime_artifacts import validate_module1_ref_runtime


REF3_PATHS = (
    "/api/v1/admin/material-hub/ref3-units",
    "/api/v1/admin/material-hub/ref3-conversions",
    "/api/v1/admin/material-hub/ref3-packaging",
    "/api/v1/admin/material-hub/ref3-extended-rules",
)


@pytest.fixture(scope="module")
def activations():
    return {
        mode: validate_module1_ref_runtime(mode)
        for mode in (
            "legacy", "artifact_validation", "dual_read",
            "ref1_read", "ref2_read", "ref3_read",
        )
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
    app.include_router(ref3_router, prefix="/api/v1")
    app.state.module1_ref_runtime = state
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=role)
    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


def test_four_exact_routes_are_get_only() -> None:
    expected = {path.removeprefix("/api/v1") for path in REF3_PATHS}
    actual = {route.path for route in ref3_router.routes}
    assert actual == expected
    assert all(route.methods == {"GET"} for route in ref3_router.routes)


@pytest.mark.parametrize(
    ("mode", "ref1_status", "ref2_status", "ref3_status"),
    [
        ("legacy", 404, 404, 404),
        ("artifact_validation", 404, 404, 404),
        ("dual_read", 404, 404, 404),
        ("ref1_read", 200, 404, 404),
        ("ref2_read", 200, 200, 404),
        ("ref3_read", 200, 200, 200),
    ],
)
def test_six_mode_endpoint_dependencies(
    activations,
    mode: str,
    ref1_status: int,
    ref2_status: int,
    ref3_status: int,
) -> None:
    client = _client(activations[mode])
    assert client.get("/api/v1/admin/material-hub/view").status_code == 200
    assert client.get("/api/v1/admin/material-hub/ref1-taxonomy").status_code == ref1_status
    assert client.get("/api/v1/admin/material-hub/ref2-characteristic-schemas").status_code == ref2_status
    assert all(client.get(path).status_code == ref3_status for path in REF3_PATHS)


def test_units_list_detail_counts_and_alias_contract(activations) -> None:
    client = _client(activations["ref3_read"])
    response = client.get(REF3_PATHS[0])
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "ref3_read" and payload["read_only"] is True
    assert payload["runtime_package_id"] == "ref-runtime-v1-122079b1c558fefc"
    assert payload["ref1_approval_id"] == "ref1-read-v1-1a15fed6ebdd"
    assert payload["ref2_approval_id"] == "ref2-read-v1-1a15fed6ebdd"
    assert payload["ref3_approval_id"] == "ref3-read-v1-1a15fed6ebdd"
    assert payload["total"] == 90 and len(payload["items"]) == 50
    assert payload["counts"] == {
        "eligible": 73, "legacy_exact_eligible": 14,
        "legacy_exact_source": 16, "review_excluded": 17,
        "runtime_units": 16, "total": 90,
    }
    assert payload["alias_policy"]["canonical_lm_meaning"] == "lumen"
    assert payload["alias_policy"]["automatic_legacy_lm_mapping_allowed"] is False

    linear = client.get(REF3_PATHS[0], params={"unit_code": "linear_meter"})
    assert linear.status_code == 200
    item = linear.json()["item"]
    assert item["review_excluded"] is True
    assert item["legacy_exact"] is True
    assert item["eligible_for_material_write"] is False
    assert client.get(REF3_PATHS[0], params={"unit_code": "m2_mm"}).json()["item"]["review_excluded"] is True
    assert client.get(REF3_PATHS[0], params={"unit_code": "missing"}).status_code == 404


def test_conversion_filters_are_metadata_only(activations) -> None:
    client = _client(activations["ref3_read"])
    payload = client.get(REF3_PATHS[1]).json()
    assert payload["counts"] == {
        "executable": 0, "formula": 7, "simple": 12,
        "technical": 28, "total": 47,
    }
    assert payload["total"] == 47
    assert all(item["executable"] is False for item in payload["items"])
    technical = client.get(REF3_PATHS[1], params={"conversion_kind": "technical", "limit": 100}).json()
    assert technical["total"] == 28
    assert all(item["parameters_required"] is True for item in technical["items"])
    formula = client.get(REF3_PATHS[1], params={"conversion_kind": "formula"}).json()
    assert formula["total"] == 7
    assert all(item["formula_metadata"]["verified_execution"] is False for item in formula["items"])


def test_packaging_contract_preserves_independent_flags(activations) -> None:
    client = _client(activations["ref3_read"])
    payload = client.get(REF3_PATHS[2], params={"limit": 100}).json()
    assert payload["counts"] == {
        "affected_material_types": 316, "assignments": 978,
        "eligible": 633, "mismatches": 345, "profiles": 21,
        "review_excluded": 51, "review_mismatch_overlap": 22,
    }
    overlap_item = next(
        item
        for item in activations["ref3_read"].projection_cache.get_packaging(
            "admin_packaging_read"
        ).assignments
        if item.review_excluded and item.mismatch_warning
    )
    filtered = client.get(
        REF3_PATHS[2],
        params={"material_type_code": overlap_item.material_type_code},
    ).json()
    assert filtered["total"] == 1
    item = filtered["items"][0]
    assert item["review_excluded"] is True and item["mismatch_warning"] is True
    assert item["eligible_for_write"] is False
    assert item["eligible_for_price_basis"] is False
    assert client.get(REF3_PATHS[2], params={"material_type_code": "missing"}).json()["items"] == []
    assert client.get(REF3_PATHS[2], params={"profile_code": "missing"}).json()["items"] == []


def test_rules_list_detail_filters_and_no_execution(activations) -> None:
    client = _client(activations["ref3_read"])
    payload = client.get(REF3_PATHS[3]).json()
    assert payload["counts"] == {
        "consumption": 5, "coverage": 2, "executable": 0,
        "geometry": 7, "pure_candidates": 6,
        "requires_module2_parameters": 7, "review_only": 2,
        "total": 15, "yield": 1,
    }
    assert payload["total"] == 15
    assert all(item["executable"] is False for item in payload["items"])
    assert all(item["object_scope_allowed"] is False for item in payload["items"])
    geometry = client.get(REF3_PATHS[3], params={"rule_class": "geometry"}).json()
    assert geometry["total"] == 7
    detail = client.get(
        REF3_PATHS[3],
        params={"rule_code": geometry["items"][0]["rule_code"]},
    )
    assert detail.status_code == 200
    assert detail.json()["item"]["formula_metadata"]["evaluated"] is False
    assert client.get(REF3_PATHS[3], params={"rule_code": "missing"}).status_code == 404


@pytest.mark.parametrize("path", REF3_PATHS)
def test_endpoints_require_admin_and_ignore_purpose_header(activations, path: str) -> None:
    assert _client(activations["ref3_read"], UserRole.SUPPLIER).get(path).status_code == 403
    client = _client(activations["ref3_read"])
    baseline = client.get(path, params={"limit": 1})
    attempted = client.get(
        path,
        params={"limit": 1},
        headers={"X-Module1-Ref-Purpose": "material_write"},
    )
    assert baseline.status_code == attempted.status_code == 200
    assert baseline.json() == attempted.json()


@pytest.mark.parametrize("path", REF3_PATHS)
def test_common_pagination_unknown_query_and_mutation_methods(activations, path: str) -> None:
    client = _client(activations["ref3_read"])
    assert client.get(path, params={"limit": 0}).status_code == 422
    assert client.get(path, params={"limit": 101}).status_code == 422
    assert client.get(path, params={"offset": -1}).status_code == 422
    assert client.get(path, params={"purpose": "material_write"}).status_code == 422
    assert client.get(path, params={"execute": "true"}).status_code == 422
    assert client.post(path).status_code == 405
    assert client.put(path).status_code == 405
    assert client.patch(path).status_code == 405
    assert client.delete(path).status_code == 405


def test_invalid_enum_queries_are_422(activations) -> None:
    client = _client(activations["ref3_read"])
    assert client.get(REF3_PATHS[1], params={"conversion_kind": "execute"}).status_code == 422
    assert client.get(REF3_PATHS[3], params={"rule_class": "work_scope"}).status_code == 422


def test_responses_do_not_expose_db_ids_paths_raw_or_mutation_routes(activations) -> None:
    client = _client(activations["ref3_read"])
    serialized = json.dumps(
        [client.get(path, params={"limit": 2}).json() for path in REF3_PATHS],
        ensure_ascii=False,
    ).lower()
    for forbidden in (
        "uuid", "database_id", "orm_id", "filesystem", "source_pointer",
        "raw_payload", "mutation_route", "python class", "stack trace",
    ):
        assert forbidden not in serialized
    assert '"executable": true' not in serialized
    assert '"eligible_for_write": true' not in serialized


def test_first_and_cached_requests_update_bounded_metrics() -> None:
    activation = validate_module1_ref_runtime("ref3_read")
    assert isinstance(activation, Module1Ref3ReadActivation)
    assert activation.projection_cache is not None
    client = _client(activation)
    assert activation.projection_cache.cache_entry_count == 0
    assert client.get(REF3_PATHS[0]).status_code == 200
    assert activation.projection_cache.cache_entry_count == 1
    assert client.get(REF3_PATHS[0]).status_code == 200
    metric = activation.projection_cache.metrics()["admin_unit_dictionary_read"]
    assert metric["build_count"] == 1 and metric["cache_hits"] == 1
