from __future__ import annotations

import hashlib
import json
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.admin_module1_ref2_characteristic_schemas import router as ref2_router
from app.api.v1.admin_module1_ref3 import router as ref3_router
from app.api.v1.admin_module1_ref_taxonomy import router as ref1_router
from app.api.v1.material_hub_view import router as material_hub_router
from app.config import settings
from app.database import get_db
from app.models.enums import UserRole
from app.services.module1_characteristic_schema_registry import list_schema_groups
from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref1_read_policy import Module1Ref1ReadActivation
from app.services.module1_ref2_read_policy import Module1Ref2ReadActivation
from app.services.module1_ref3_read_policy import Module1Ref3ReadActivation
from app.services.module1_ref3_read_projection import (
    CONVERSION_PURPOSE,
    PACKAGING_PURPOSE,
    RULE_PURPOSE,
    UNIT_PURPOSE,
)
from app.services.module1_ref_dual_read import (
    build_legacy_taxonomy_snapshot,
    fingerprint_legacy_registry_snapshot,
)
from app.services.module1_ref_runtime_artifacts import (
    DEFAULT_ARTIFACT_DIR,
    Module1RefRuntimeConfigurationError,
    snapshot_legacy_material_registry,
    validate_module1_ref_runtime,
)
from app.services.module1_unit_conversion_registry import convert_quantity, list_units


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REF1_PATH = "/api/v1/admin/material-hub/ref1-taxonomy"
REF2_PATH = "/api/v1/admin/material-hub/ref2-characteristic-schemas"
REF3_PATHS = (
    "/api/v1/admin/material-hub/ref3-units",
    "/api/v1/admin/material-hub/ref3-conversions",
    "/api/v1/admin/material-hub/ref3-packaging",
    "/api/v1/admin/material-hub/ref3-extended-rules",
)
MODE_MATRIX = {
    "legacy": (404, 404, 404),
    "artifact_validation": (404, 404, 404),
    "dual_read": (404, 404, 404),
    "ref1_read": (200, 404, 404),
    "ref2_read": (200, 200, 404),
    "ref3_read": (200, 200, 200),
}
ROLLBACK_CHAIN = (
    "legacy",
    "ref1_read",
    "ref2_read",
    "ref3_read",
    "ref2_read",
    "ref1_read",
    "legacy",
)
APPROVAL_HASHES = {
    "ref1-read-v1-1a15fed6ebdd": "55c9f09aa1db034f22108f02a2f2afe692bdf58650ff4d2a8d0d8b70b1799973",
    "ref2-read-v1-1a15fed6ebdd": "e5e13fba61a3aef4e94b27e22394f41d2ebbeb0b948e5f899742342e19d50e06",
    "ref3-read-v1-1a15fed6ebdd": "429468eda2569c7366504e10f95ad84ea96d17878b5bb1b3a09fcf8e12e97bab",
}
DB_BASELINE = {
    "materials": 394,
    "catalog_products": 441,
    "price_history": 188,
    "material_types": 0,
    "material_category_schemas": 0,
    "material_attributes": 0,
    "units": 0,
    "unit_aliases": 0,
    "unit_conversions": 0,
    "user_preferences": 19,
    "widget_preferences": 0,
}


class _EmptyScalarResult:
    def scalars(self) -> _EmptyScalarResult:
        return self

    def all(self) -> list[Any]:
        return []


class _IsolatedReadOnlyDb:
    def __init__(self) -> None:
        self.counts = dict(DB_BASELINE)
        self.statements: list[str] = []

    async def execute(self, statement: Any) -> _EmptyScalarResult:
        sql = str(statement).strip().lower()
        assert not sql.startswith(("insert", "update", "delete", "merge", "alter", "create", "drop"))
        self.statements.append(sql)
        return _EmptyScalarResult()


def _client(state: Any, database: _IsolatedReadOnlyDb) -> TestClient:
    app = FastAPI()
    app.include_router(material_hub_router, prefix="/api/v1")
    app.include_router(ref1_router, prefix="/api/v1")
    app.include_router(ref2_router, prefix="/api/v1")
    app.include_router(ref3_router, prefix="/api/v1")
    app.state.module1_ref_runtime = state

    async def fake_db():
        yield database

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
    app.dependency_overrides[get_db] = fake_db
    return TestClient(app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_state() -> dict[str, Any]:
    registry = get_material_knowledge_seed_registry()
    taxonomy = build_legacy_taxonomy_snapshot(registry)
    schemas = tuple(registry.characteristic_schemas.values())
    field_uses = tuple(
        field
        for schema in schemas
        for bucket in (schema.required, schema.module2_required, schema.recommended)
        for field in bucket
    )
    conversion = convert_quantity(1000, "mm", "m")
    return {
        "full_snapshot": snapshot_legacy_material_registry(registry),
        "taxonomy_fingerprint": fingerprint_legacy_registry_snapshot(taxonomy),
        "groups": len(taxonomy["groups"]),
        "material_types": len(taxonomy["material_types"]),
        "schemas": len(list_schema_groups()),
        "unique_fields": len(set(field_uses)),
        "field_usages": len(field_uses),
        "units": tuple(list_units()),
        "conversion_probe": (
            conversion.success,
            conversion.value,
            conversion.unit,
            conversion.error_code,
        ),
    }


def _assert_zero_mutations(activation: Any) -> None:
    assert getattr(activation, "registry_mutated", False) is False
    assert getattr(activation, "database_writes", 0) == 0
    assert getattr(activation, "preference_writes", 0) == 0
    assert getattr(activation, "ref_only_writes_enabled", False) is False


def test_decision_039_records_consolidated_read_only_and_rollback_contract() -> None:
    decisions = (PROJECT_ROOT / "docs/Decisions.md").read_text(encoding="utf-8")
    heading = "## \u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u2116039"
    assert decisions.count(heading) == 1
    section = decisions.split(heading, 1)[1]
    assert "governed administrative read-only projections" in section
    assert "ref3_read \u2192 ref2_read \u2192 ref1_read \u2192 legacy" in section
    assert "REF-only codes \u043d\u0435 \u0440\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u044b \u0434\u043b\u044f business writes" in section
    assert "no destructive migration required; compatibility and rollback proven" in section
    assert "\u0421\u0442\u0430\u0442\u0443\u0441:\n\u041f\u0440\u0438\u043d\u044f\u0442\u043e." in section
    for number in range(32, 39):
        assert decisions.count(f"## \u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u2116{number:03d}") == 1


def test_default_and_unknown_mode_contract_remain_strict() -> None:
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    assert set(MODE_MATRIX) == {
        "legacy", "artifact_validation", "dual_read",
        "ref1_read", "ref2_read", "ref3_read",
    }
    with pytest.raises(Module1RefRuntimeConfigurationError):
        validate_module1_ref_runtime("ref_write")


def test_immutable_runtime_and_approval_hash_chain_is_version_pinned() -> None:
    manifest_path = DEFAULT_ARTIFACT_DIR / "manifest.json"
    assert _sha256(manifest_path) == "1a15fed6ebddb77c293b8a77539f790b5733215ef3a748a52f3c83a33fe75e9f"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifact_set_id"] == "ref-runtime-v1-122079b1c558fefc"
    assert manifest["artifact_schema_version"] == "1.0"
    assert manifest["compatibility_map_version"] == "1.0"
    assert len(manifest["artifacts"]) == 8
    for filename, contract in manifest["artifacts"].items():
        assert _sha256(DEFAULT_ARTIFACT_DIR / filename) == contract["sha256"]

    approval_root = DEFAULT_ARTIFACT_DIR.parent / "approvals"
    approvals = {}
    for approval_id, expected_hash in APPROVAL_HASHES.items():
        path = approval_root / approval_id / "approval_manifest.json"
        assert _sha256(path) == expected_hash
        approvals[approval_id] = json.loads(path.read_text(encoding="utf-8"))
        assert approvals[approval_id]["approval_id"] == approval_id
        assert approvals[approval_id]["approval_schema_version"] == "1.0"
        assert approvals[approval_id]["approval_version"] == "1.0"

    ref1, ref2, ref3 = approvals.values()
    assert int(ref1["decision_number"]) == 36
    assert int(ref2["decision_number"]) == 37
    assert int(ref3["decision_number"]) == 38
    assert ref1["runtime_manifest_hash"] == _sha256(manifest_path)
    assert ref2["runtime_package"]["manifest_sha256"] == _sha256(manifest_path)
    assert ref3["runtime_package"]["manifest_sha256"] == _sha256(manifest_path)
    assert ref2["prerequisite_approvals"] == [{
        "approval_id": "ref1-read-v1-1a15fed6ebdd",
        "approval_sha256": APPROVAL_HASHES["ref1-read-v1-1a15fed6ebdd"],
        "required_mode": "ref1_read",
    }]
    assert {item["approval_id"] for item in ref3["prerequisite_approvals"]} == {
        "ref1-read-v1-1a15fed6ebdd", "ref2-read-v1-1a15fed6ebdd",
    }


def test_six_mode_matrix_and_full_rollback_preserve_registry_db_and_preferences() -> None:
    registry = get_material_knowledge_seed_registry()
    initial_registry = _legacy_state()
    database = _IsolatedReadOnlyDb()
    initial_database = dict(database.counts)

    for mode in ROLLBACK_CHAIN:
        before = _legacy_state()
        activation = validate_module1_ref_runtime(mode, registry=registry)
        _assert_zero_mutations(activation)
        if mode == "dual_read":
            assert activation.status == "PASS_WITH_WARNINGS"
        elif mode == "legacy":
            assert activation.status == "LEGACY"
        else:
            assert activation.status == "PASS"

        if mode == "ref3_read":
            assert isinstance(activation, Module1Ref3ReadActivation)
            assert activation.projection_cache is not None
            assert activation.projection_cache.cache_entry_count == 0
        else:
            assert not hasattr(activation, "projection_cache")

        ref1_status, ref2_status, ref3_status = MODE_MATRIX[mode]
        client = _client(activation, database)
        try:
            assert client.get("/api/v1/admin/material-hub/view").status_code == 200
            assert client.get(REF1_PATH).status_code == ref1_status
            assert client.get(REF2_PATH).status_code == ref2_status
            assert all(client.get(path).status_code == ref3_status for path in REF3_PATHS)
        finally:
            client.close()

        if mode == "ref3_read":
            assert activation.projection_cache.cache_entry_count == 4
        assert _legacy_state() == before == initial_registry
        assert database.counts == initial_database

    assert database.counts == initial_database
    assert all(not sql.startswith(("insert", "update", "delete")) for sql in database.statements)
    final_legacy = validate_module1_ref_runtime("legacy", registry=registry)
    client = _client(final_legacy, database)
    try:
        assert client.get(REF1_PATH).status_code == 404
        assert client.get(REF2_PATH).status_code == 404
        assert all(client.get(path).status_code == 404 for path in REF3_PATHS)
    finally:
        client.close()


def test_legacy_registry_counts_fingerprint_and_executor_remain_source_of_truth() -> None:
    before = _legacy_state()
    assert before["groups"] == 19
    assert before["material_types"] == 192
    assert before["schemas"] == 13
    assert before["unique_fields"] == 74
    assert before["field_usages"] == 125
    assert len(before["units"]) == 16
    assert before["conversion_probe"] == (True, Decimal("1.000"), "m", None)

    for mode in MODE_MATRIX:
        validate_module1_ref_runtime(mode)
        assert _legacy_state() == before
    assert "acoustic_ceiling_panel" not in {
        child
        for group in get_material_knowledge_seed_registry().taxonomy
        for child in group.children
    }


def test_ref_only_data_is_admin_metadata_and_business_services_remain_legacy_only() -> None:
    ref1 = validate_module1_ref_runtime("ref1_read")
    assert isinstance(ref1, Module1Ref1ReadActivation)
    assert ref1.policy is not None
    eligibility = ref1.policy.eligibility(
        "acoustic_ceiling_panel",
        purpose="admin_taxonomy_read",
    )
    assert eligibility.recognised_for_ref_read is True
    assert eligibility.eligible_for_material_write is False
    assert eligibility.eligible_for_catalog_product_write is False
    assert eligibility.eligible_for_normalizer_output is False
    assert eligibility.eligible_for_matching is False
    assert eligibility.eligible_for_moderation_approval is False

    ref2 = validate_module1_ref_runtime("ref2_read")
    assert isinstance(ref2, Module1Ref2ReadActivation)
    assert ref2.projection is not None
    ref2_schema = ref2.projection.get("gypsum_board_regular")
    assert ref2_schema is not None
    assert all(field.as_dict()["eligible_for_material_write"] is False for field in ref2_schema.fields)
    assert all(field.as_dict()["eligible_for_catalog_product_write"] is False for field in ref2_schema.fields)
    assert all(field.as_dict()["eligible_for_normalizer_output"] is False for field in ref2_schema.fields)

    ref3 = validate_module1_ref_runtime("ref3_read")
    assert isinstance(ref3, Module1Ref3ReadActivation)
    assert ref3.projection_cache is not None
    units = ref3.projection_cache.get_units(UNIT_PURPOSE)
    conversions = ref3.projection_cache.get_conversions(CONVERSION_PURPOSE)
    packaging = ref3.projection_cache.get_packaging(PACKAGING_PURPOSE)
    rules = ref3.projection_cache.get_rules(RULE_PURPOSE)
    assert all(item.as_dict()["eligible_for_material_write"] is False for item in units.units)
    assert all(item.as_dict()["executable"] is False for item in conversions.conversions)
    assert all(item.as_dict()["eligible_for_write"] is False for item in packaging.assignments)
    assert all(item.as_dict()["executable"] is False for item in rules.rules)

    business_paths = (
        "app/models/material.py",
        "app/models/catalog_product.py",
        "app/services/module1_material_normalizer.py",
        "app/services/module1_matching_dedup.py",
        "app/services/module1_moderation_core.py",
        "app/services/module1_canonical_material_store.py",
        "app/services/module1_export_packages.py",
        "app/services/module1_provider_work_cost_offers.py",
    )
    for relative_path in business_paths:
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "module1_ref" not in source
        assert "runtime_reference" not in source


def test_review_diagnostics_and_non_execution_counts_are_preserved() -> None:
    ref2 = validate_module1_ref_runtime("ref2_read")
    assert isinstance(ref2, Module1Ref2ReadActivation)
    assert dict(ref2.counts) == {
        "assignments_blocked": 0,
        "assignments_eligible": 930,
        "assignments_fully_readable": 619,
        "assignments_readable_with_warnings": 311,
        "assignments_review_excluded": 48,
        "assignments_total": 978,
        "fields": 558,
        "profiles": 177,
    }
    assert ref2.projection is not None
    assert ref2.projection.compatibility_summary["runtime_only_fields"] == 28

    ref3 = validate_module1_ref_runtime("ref3_read")
    assert isinstance(ref3, Module1Ref3ReadActivation)
    assert ref3.projection_cache is not None
    units = ref3.projection_cache.get_units(UNIT_PURPOSE)
    packaging = ref3.projection_cache.get_packaging(PACKAGING_PURPOSE)
    conversions = ref3.projection_cache.get_conversions(CONVERSION_PURPOSE)
    rules = ref3.projection_cache.get_rules(RULE_PURPOSE)
    assert units.counts["review_excluded"] == 17
    assert units.alias_policy["canonical_lm_meaning"] == "lumen"
    assert units.alias_policy["automatic_legacy_lm_mapping_allowed"] is False
    assert packaging.counts["review_excluded"] == 51
    assert packaging.counts["mismatches"] == 345
    assert packaging.counts["affected_material_types"] == 316
    assert packaging.counts["review_mismatch_overlap"] == 22
    assert conversions.counts["executable"] == 0
    assert rules.counts["executable"] == 0
    approval_path = (
        DEFAULT_ARTIFACT_DIR.parent
        / "approvals/ref3-read-v1-1a15fed6ebdd/approval_manifest.json"
    )
    approval_counts = json.loads(approval_path.read_text(encoding="utf-8"))["counts"]
    assert approval_counts["work_material_mappings"] == 0
    assert approval_counts["object_scope_calculations"] == 0
    assert approval_counts["work_scope_calculations"] == 0


def test_lazy_cache_and_performance_snapshot_have_no_cross_mode_leakage(record_property) -> None:
    timings: dict[str, float] = {}
    for mode in MODE_MATRIX:
        started = time.perf_counter()
        activation = validate_module1_ref_runtime(mode)
        timings[f"{mode}_startup_ms"] = (time.perf_counter() - started) * 1000
        if mode == "ref1_read":
            assert isinstance(activation, Module1Ref1ReadActivation)
            assert activation.projection is not None
        elif mode == "ref2_read":
            assert isinstance(activation, Module1Ref2ReadActivation)
            assert activation.projection is not None
            assert not hasattr(activation, "projection_cache")
        elif mode == "ref3_read":
            assert isinstance(activation, Module1Ref3ReadActivation)
            assert activation.startup_ref3_projection_count == 0
            assert activation.projection_cache is not None
            assert activation.projection_cache.cache_entry_count == 0
            cache = activation.projection_cache
            for purpose, getter in (
                (UNIT_PURPOSE, cache.get_units),
                (CONVERSION_PURPOSE, cache.get_conversions),
                (PACKAGING_PURPOSE, cache.get_packaging),
                (RULE_PURPOSE, cache.get_rules),
            ):
                getter(purpose)
                getter(purpose)
            assert cache.cache_entry_count == 4
            assert cache.max_entries == 5
            assert all(metric["build_count"] == 1 for metric in cache.metrics().values())
            assert all(metric["cache_hits"] == 1 for metric in cache.metrics().values())
            assert all(metric["serialized_size_bytes"] > 0 for metric in cache.metrics().values())
        else:
            assert not hasattr(activation, "projection_cache")

    fresh_ref2 = validate_module1_ref_runtime("ref2_read")
    fresh_ref1 = validate_module1_ref_runtime("ref1_read")
    fresh_legacy = validate_module1_ref_runtime("legacy")
    assert not any(hasattr(item, "projection_cache") for item in (fresh_ref2, fresh_ref1, fresh_legacy))
    assert not hasattr(get_material_knowledge_seed_registry(), "ref3_projection")
    record_property("module1_ref_runtime_startup_metrics", json.dumps(timings, sort_keys=True))
    assert all(value >= 0 for value in timings.values())