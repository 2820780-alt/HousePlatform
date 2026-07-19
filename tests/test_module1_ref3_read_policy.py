from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.config import settings
from app.services.module1_characteristic_schema_registry import list_schema_groups
from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref3_read_policy import (
    APPROVED_PURPOSES,
    DENIED_PURPOSES,
    EXPECTED_APPROVAL_SHA256,
    Module1Ref3ReadActivation,
)
from app.services.module1_ref3_read_projection import (
    CONVERSION_PURPOSE,
    PACKAGING_PURPOSE,
    RULE_PURPOSE,
    UNIT_PURPOSE,
    Ref3ProjectionError,
)
from app.services.module1_ref_runtime_artifacts import (
    APPROVAL_ROOT,
    DEFAULT_APPROVAL_DIR,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_REF2_APPROVAL_DIR,
    DEFAULT_REF3_APPROVAL_DIR,
    SUPPORTED_MODES,
    Module1RefRuntimeConfigurationError,
    snapshot_legacy_material_registry,
    validate_module1_ref_runtime,
)
from app.services.module1_unit_conversion_registry import list_units


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def activation() -> Module1Ref3ReadActivation:
    result = validate_module1_ref_runtime("ref3_read")
    assert isinstance(result, Module1Ref3ReadActivation)
    assert result.is_valid
    return result


def _copy_runtime(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    runtime_root = tmp_path / "runtime_reference"
    artifact_dir = runtime_root / DEFAULT_ARTIFACT_DIR.name
    approval_root = runtime_root / "approvals"
    ref1_dir = approval_root / DEFAULT_APPROVAL_DIR.name
    ref2_dir = approval_root / DEFAULT_REF2_APPROVAL_DIR.name
    ref3_dir = approval_root / DEFAULT_REF3_APPROVAL_DIR.name
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact_dir)
    shutil.copytree(DEFAULT_APPROVAL_DIR, ref1_dir)
    shutil.copytree(DEFAULT_REF2_APPROVAL_DIR, ref2_dir)
    shutil.copytree(DEFAULT_REF3_APPROVAL_DIR, ref3_dir)
    return artifact_dir, runtime_root, ref1_dir, ref2_dir, ref3_dir, approval_root


def _activate_copy(tmp_path: Path) -> Module1Ref3ReadActivation:
    artifact_dir, runtime_root, ref1_dir, ref2_dir, ref3_dir, approval_root = _copy_runtime(tmp_path)
    result = validate_module1_ref_runtime(
        "ref3_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=ref1_dir,
        ref2_approval_dir=ref2_dir,
        ref3_approval_dir=ref3_dir,
        approval_allowed_root=approval_root,
    )
    assert isinstance(result, Module1Ref3ReadActivation)
    return result


def test_supported_modes_default_and_unknown_mode_contract() -> None:
    assert SUPPORTED_MODES == {
        "legacy", "artifact_validation", "dual_read",
        "ref1_read", "ref2_read", "ref3_read",
    }
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    with pytest.raises(Module1RefRuntimeConfigurationError):
        validate_module1_ref_runtime("ref3_write")


def test_activation_validates_all_approvals_and_starts_without_ref3_projection(
    activation: Module1Ref3ReadActivation,
) -> None:
    assert activation.status == "PASS"
    assert activation.package_validated is True
    assert activation.ref1_approval_validated is True
    assert activation.ref2_approval_validated is True
    assert activation.ref3_approval_validated is True
    assert activation.ref3_approval_sha256 == EXPECTED_APPROVAL_SHA256
    assert activation.database_writes == activation.preference_writes == 0
    assert activation.registry_mutated is False
    assert activation.ref_only_writes_enabled is False
    assert activation.projection_cache is not None
    assert activation.startup_ref3_projection_count == 0
    assert activation.projection_cache.cache_entry_count == 0


def test_purpose_policy_is_exact_server_allowlist_and_unknown_denied(
    activation: Module1Ref3ReadActivation,
) -> None:
    assert APPROVED_PURPOSES == (
        "admin_conversion_metadata_read",
        "admin_extended_rule_read",
        "admin_packaging_read",
        "admin_unit_dictionary_read",
        "internal_diagnostics",
    )
    assert set(APPROVED_PURPOSES).isdisjoint(DENIED_PURPOSES)
    assert activation.ref3_policy is not None
    assert all(activation.ref3_policy.purpose_allowed(item) for item in APPROVED_PURPOSES)
    assert not activation.ref3_policy.purpose_allowed("material_write")
    assert not activation.ref3_policy.purpose_allowed("unknown")


def test_units_and_alias_policy_counts_are_exact(activation: Module1Ref3ReadActivation) -> None:
    assert activation.projection_cache is not None
    projection = activation.projection_cache.get_units(UNIT_PURPOSE)
    assert len(projection.units) == 90
    assert dict(projection.counts) == {
        "eligible": 73, "legacy_exact_eligible": 14,
        "legacy_exact_source": 16, "review_excluded": 17,
        "runtime_units": 16, "total": 90,
    }
    lm = projection.get("lm")
    linear_meter = projection.get("linear_meter")
    m2_mm = projection.get("m2_mm")
    assert lm and linear_meter and m2_mm
    assert projection.alias_policy["canonical_lm_meaning"] == "lumen"
    assert projection.alias_policy["automatic_legacy_lm_mapping_allowed"] is False
    assert linear_meter.review_excluded and m2_mm.review_excluded
    assert linear_meter.legacy_exact is True
    assert all(item.as_dict()["eligible_for_material_write"] is False for item in projection.units)


def test_conversions_are_metadata_only_and_never_executable(
    activation: Module1Ref3ReadActivation,
) -> None:
    assert activation.projection_cache is not None
    projection = activation.projection_cache.get_conversions(CONVERSION_PURPOSE)
    assert len(projection.conversions) == 47
    assert dict(projection.counts) == {
        "executable": 0, "formula": 7, "simple": 12,
        "technical": 28, "total": 47,
    }
    kinds = {item.conversion_kind for item in projection.conversions}
    assert kinds == {"simple", "technical", "formula"}
    assert all(item.as_dict()["executable"] is False for item in projection.conversions)
    assert all(item.parameters_required for item in projection.conversions if item.conversion_kind != "simple")
    assert all(item.as_dict()["legacy_executor_source_of_truth"] is True for item in projection.conversions)


def test_packaging_keeps_review_and_mismatch_flags_independent(
    activation: Module1Ref3ReadActivation,
) -> None:
    assert activation.projection_cache is not None
    projection = activation.projection_cache.get_packaging(PACKAGING_PURPOSE)
    assert len(projection.assignments) == 978
    assert dict(projection.counts) == {
        "affected_material_types": 316, "assignments": 978,
        "eligible": 633, "mismatches": 345, "profiles": 21,
        "review_excluded": 51, "review_mismatch_overlap": 22,
    }
    review = {item.material_type_code for item in projection.assignments if item.review_excluded}
    mismatch = {item.material_type_code for item in projection.assignments if item.mismatch_warning}
    assert len(review & mismatch) == 22
    assert all(item.as_dict()["eligible_for_write"] is False for item in projection.assignments)
    assert all(item.as_dict()["eligible_for_price_basis"] is False for item in projection.assignments)


def test_rules_are_classified_metadata_without_formula_execution(
    activation: Module1Ref3ReadActivation,
) -> None:
    assert activation.projection_cache is not None
    projection = activation.projection_cache.get_rules(RULE_PURPOSE)
    assert len(projection.rules) == 15
    assert dict(projection.counts) == {
        "consumption": 5, "coverage": 2, "executable": 0,
        "geometry": 7, "pure_candidates": 6,
        "requires_module2_parameters": 7, "review_only": 2,
        "total": 15, "yield": 1,
    }
    assert all(item.as_dict()["executable"] is False for item in projection.rules)
    assert all(item.as_dict()["module2_execution_allowed"] is False for item in projection.rules)
    assert all(item.as_dict()["formula_metadata"]["evaluated"] is False for item in projection.rules)


def test_cache_is_private_bounded_lazy_and_reuses_completed_entries() -> None:
    activation = validate_module1_ref_runtime("ref3_read")
    assert isinstance(activation, Module1Ref3ReadActivation)
    assert activation.projection_cache is not None
    cache = activation.projection_cache
    assert cache.max_entries == 5 and cache.cache_entry_count == 0
    first = cache.get_units(UNIT_PURPOSE)
    assert cache.cache_entry_count == 1
    second = cache.get_units(UNIT_PURPOSE)
    assert first is second and cache.cache_entry_count == 1
    metric = cache.metrics()[UNIT_PURPOSE]
    assert metric["build_count"] == 1 and metric["cache_hits"] == 1
    assert metric["first_load_duration_ms"] >= 0
    assert metric["cached_request_duration_ms"] >= 0
    assert metric["serialized_size_bytes"] > 0
    with pytest.raises(Ref3ProjectionError):
        cache.get_units("material_write")


def test_legacy_registries_and_schemas_remain_unchanged() -> None:
    registry = get_material_knowledge_seed_registry()
    material_before = snapshot_legacy_material_registry(registry)
    unit_before = tuple(list_units())
    result = validate_module1_ref_runtime("ref3_read", registry=registry)
    unique_fields = {
        field
        for schema in registry.characteristic_schemas.values()
        for bucket in (schema.required, schema.module2_required, schema.recommended)
        for field in bucket
    }
    usages = sum(
        len(schema.required) + len(schema.module2_required) + len(schema.recommended)
        for schema in registry.characteristic_schemas.values()
    )
    assert result.is_valid and not result.registry_mutated
    assert snapshot_legacy_material_registry(registry) == material_before
    assert tuple(list_units()) == unit_before and len(unit_before) == 16
    assert len(list_schema_groups()) == 13
    assert len(unique_fields) == 74 and usages == 125


def test_rollback_chain_to_ref2_and_legacy_preserves_registries() -> None:
    registry = get_material_knowledge_seed_registry()
    before = snapshot_legacy_material_registry(registry)
    ref3 = validate_module1_ref_runtime("ref3_read", registry=registry)
    ref2 = validate_module1_ref_runtime("ref2_read", registry=registry)
    legacy = validate_module1_ref_runtime("legacy", registry=registry)
    assert ref3.is_valid and ref2.is_valid and legacy.status == "LEGACY"
    assert snapshot_legacy_material_registry(registry) == before


def test_missing_each_approval_fails_closed_without_partial_cache(tmp_path: Path) -> None:
    for index, approval_name in enumerate(("ref1", "ref2", "ref3")):
        paths = _copy_runtime(tmp_path / str(index))
        artifact_dir, runtime_root, ref1_dir, ref2_dir, ref3_dir, approval_root = paths
        target = {"ref1": ref1_dir, "ref2": ref2_dir, "ref3": ref3_dir}[approval_name]
        (target / "approval_manifest.json").unlink()
        result = validate_module1_ref_runtime(
            "ref3_read", artifact_dir=artifact_dir, allowed_root=runtime_root,
            approval_dir=ref1_dir, ref2_approval_dir=ref2_dir,
            ref3_approval_dir=ref3_dir, approval_allowed_root=approval_root,
        )
        assert isinstance(result, Module1Ref3ReadActivation)
        assert result.status == "BLOCKED" and result.projection_cache is None
        assert result.database_writes == result.preference_writes == 0


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(approval_schema_version="2.0"),
        lambda p: p.update(decision_number=39),
        lambda p: p["counts"].update(ref3_units_total=91),
        lambda p: p["purpose_policy"].update(unknown_purpose="allow"),
        lambda p: p["unit_alias_policy"].update(automatic_legacy_lm_mapping_allowed=True),
        lambda p: p["conversion_policy"].update(ref_conversion_execution_allowed=True),
        lambda p: p["packaging_policy"].update(packaging_write_allowed=True),
        lambda p: p["rule_policy"].update(rule_execution_allowed=True),
        lambda p: p["activation_flags"].update(module2_execution_allowed=True),
    ],
)
def test_approval_policy_mutations_fail_closed(tmp_path: Path, mutation) -> None:
    artifact_dir, runtime_root, ref1_dir, ref2_dir, ref3_dir, approval_root = _copy_runtime(tmp_path)
    path = ref3_dir / "approval_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutation(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = validate_module1_ref_runtime(
        "ref3_read", artifact_dir=artifact_dir, allowed_root=runtime_root,
        approval_dir=ref1_dir, ref2_approval_dir=ref2_dir,
        ref3_approval_dir=ref3_dir, approval_allowed_root=approval_root,
    )
    assert result.status == "BLOCKED" and result.projection_cache is None
    assert "APPROVAL_HASH_INVALID" in {issue.code for issue in result.issues}


def test_changed_lazy_artifact_fails_without_partial_cache(tmp_path: Path) -> None:
    activation = _activate_copy(tmp_path)
    assert activation.projection_cache is not None
    cache = activation.projection_cache
    (tmp_path / "runtime_reference" / DEFAULT_ARTIFACT_DIR.name / "units.json").write_bytes(
        (tmp_path / "runtime_reference" / DEFAULT_ARTIFACT_DIR.name / "units.json").read_bytes() + b" "
    )
    with pytest.raises(Ref3ProjectionError):
        cache.get_units(UNIT_PURPOSE)
    assert cache.cache_entry_count == 0


def test_production_ref3_services_do_not_import_tools_docs_db_or_business_layers() -> None:
    sources = "\n".join(
        (PROJECT_ROOT / path).read_text(encoding="utf-8")
        for path in (
            "app/services/module1_ref3_read_policy.py",
            "app/services/module1_ref3_read_projection.py",
        )
    )
    for forbidden in (
        "tools.module1_ref_projection", "docs/Modules", "reference_data",
        "sqlalchemy", "app.database", "app.models", "module1_material_normalizer",
        "module1_matching_dedup", "module1_moderation_core",
        "module1_export_packages", "module1_provider_work_cost_offers",
    ):
        assert forbidden not in sources
