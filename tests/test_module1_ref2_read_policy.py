from __future__ import annotations

import json
import shutil
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.config import settings
from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref2_read_policy import (
    APPROVED_PURPOSES,
    DENIED_PURPOSES,
    EXPECTED_APPROVAL_SHA256,
    Module1Ref2ReadActivation,
)
from app.services.module1_ref_runtime_artifacts import (
    APPROVAL_ROOT,
    DEFAULT_APPROVAL_DIR,
    DEFAULT_ARTIFACT_DIR,
    DEFAULT_REF2_APPROVAL_DIR,
    SUPPORTED_MODES,
    Module1RefRuntimeConfigurationError,
    snapshot_legacy_material_registry,
    validate_module1_ref_runtime,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def activation() -> Module1Ref2ReadActivation:
    result = validate_module1_ref_runtime("ref2_read")
    assert isinstance(result, Module1Ref2ReadActivation)
    assert result.is_valid
    return result


def _copy_runtime(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    runtime_root = tmp_path / "runtime_reference"
    artifact_dir = runtime_root / DEFAULT_ARTIFACT_DIR.name
    approval_root = runtime_root / "approvals"
    ref1_dir = approval_root / DEFAULT_APPROVAL_DIR.name
    ref2_dir = approval_root / DEFAULT_REF2_APPROVAL_DIR.name
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact_dir)
    shutil.copytree(DEFAULT_APPROVAL_DIR, ref1_dir)
    shutil.copytree(DEFAULT_REF2_APPROVAL_DIR, ref2_dir)
    return artifact_dir, runtime_root, ref1_dir, ref2_dir, approval_root


def _activate_copy(tmp_path: Path) -> Module1Ref2ReadActivation:
    artifact_dir, runtime_root, ref1_dir, ref2_dir, approval_root = _copy_runtime(tmp_path)
    result = validate_module1_ref_runtime(
        "ref2_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=ref1_dir,
        ref2_approval_dir=ref2_dir,
        approval_allowed_root=approval_root,
    )
    assert isinstance(result, Module1Ref2ReadActivation)
    return result


def test_supported_modes_default_and_unknown_mode_contract() -> None:
    assert SUPPORTED_MODES == {
        "legacy",
        "artifact_validation",
        "dual_read",
        "ref1_read",
        "ref2_read",
    }
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    with pytest.raises(Module1RefRuntimeConfigurationError):
        validate_module1_ref_runtime("ref2_write")


def test_activation_validates_both_approvals_and_is_read_only(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert activation.status == "PASS"
    assert activation.package_validated is True
    assert activation.ref1_approval_validated is True
    assert activation.ref2_approval_validated is True
    assert activation.ref2_approval_sha256 == EXPECTED_APPROVAL_SHA256
    assert activation.registry_mutated is False
    assert activation.database_writes == activation.preference_writes == 0
    assert activation.business_reads_enabled is True
    assert activation.ref_only_writes_enabled is False
    with pytest.raises(FrozenInstanceError):
        activation.mode = "legacy"  # type: ignore[misc]


def test_projection_counts_statuses_and_compatibility_are_exact(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert dict(activation.counts) == {
        "assignments_blocked": 0,
        "assignments_eligible": 930,
        "assignments_fully_readable": 619,
        "assignments_readable_with_warnings": 311,
        "assignments_review_excluded": 48,
        "assignments_total": 978,
        "fields": 558,
        "profiles": 177,
    }
    assert activation.projection is not None
    assert dict(activation.projection.counts) == {
        "fully_readable": 619,
        "readable_with_warnings": 311,
        "review_excluded": 48,
        "blocked": 0,
    }
    assert dict(activation.projection.compatibility_summary) == {
        "overlap_total": 46,
        "read_compatible": 21,
        "review_required": 19,
        "required_semantics_mismatch": 6,
        "runtime_only_fields": 28,
        "packaging_mismatches": 345,
        "packaging_affected_material_types": 316,
    }


def test_purpose_is_exact_server_allowlist_and_unknown_is_denied(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert activation.policy is not None
    assert APPROVED_PURPOSES == ("admin_characteristic_schema_read", "internal_diagnostics")
    assert set(APPROVED_PURPOSES).isdisjoint(DENIED_PURPOSES)
    assert activation.policy.purpose_allowed("admin_characteristic_schema_read")
    assert activation.policy.purpose_allowed("internal_diagnostics")
    assert not activation.policy.purpose_allowed("material_write")
    assert not activation.policy.purpose_allowed("unknown")


def test_review_assignment_is_withheld_and_not_treated_as_empty_schema(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert activation.projection is not None
    schema = activation.projection.get("board")
    assert schema is not None
    assert schema.schema_status == "review_excluded"
    assert schema.field_availability == "withheld_pending_review"
    assert schema.warning_codes == ("REF2_ASSIGNMENT_REVIEW_EXCLUDED",)
    assert schema.fields == ()
    assert schema.as_summary()["eligible_for_material_write"] is False


def test_flattened_fields_keep_ref_and_legacy_required_semantics_separate(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert activation.projection is not None
    schema = activation.projection.get("gypsum_board_regular")
    assert schema is not None
    assert schema.legacy_schema_present is True
    assert schema.schema_status == "readable_with_warnings"
    fields = {field.field_code: field for field in schema.fields}
    assert fields["length_mm"].ref_source_required is True
    assert fields["length_mm"].legacy_effective_required is True
    ref_only = next(field for field in schema.fields if field.compatibility_status == "ref_only")
    assert ref_only.legacy_effective_required is False
    assert ref_only.as_dict()["eligible_for_material_write"] is False
    assert tuple(field.field_code for field in schema.fields) == tuple(sorted(fields))


def test_packaging_is_diagnostic_only_and_never_injected(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert activation.projection is not None
    schema = activation.projection.get("abutment_strip")
    assert schema is not None
    assert schema.packaging_boundary_warnings == ("PACKAGING_REF2_MISMATCH_DIAGNOSTIC_ONLY",)
    assert "PACKAGING_REF2_MISMATCH" in schema.warning_codes
    detail = schema.as_detail()
    serialized = json.dumps(detail, ensure_ascii=False)
    assert "candidate_price_basis_units" not in serialized
    assert "required_packaging_fields" not in serialized
    assert "raw" not in serialized.lower()


def test_legacy_registry_contract_is_unchanged_and_not_extended(
    activation: Module1Ref2ReadActivation,
) -> None:
    registry = get_material_knowledge_seed_registry()
    before = snapshot_legacy_material_registry(registry)
    second = validate_module1_ref_runtime("ref2_read", registry=registry)
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
    assert len(registry.characteristic_schemas) == 13
    assert len(unique_fields) == 74
    assert usages == 125
    assert second.is_valid and second.registry_mutated is False
    assert snapshot_legacy_material_registry(registry) == before


def test_rollback_to_ref1_and_legacy_keeps_registry_unchanged() -> None:
    registry = get_material_knowledge_seed_registry()
    before = snapshot_legacy_material_registry(registry)
    ref2 = validate_module1_ref_runtime("ref2_read", registry=registry)
    ref1 = validate_module1_ref_runtime("ref1_read", registry=registry)
    legacy = validate_module1_ref_runtime("legacy", registry=registry)
    assert ref2.is_valid and ref1.is_valid
    assert legacy.status == "LEGACY"
    assert snapshot_legacy_material_registry(registry) == before


def test_missing_ref1_or_ref2_approval_fails_closed(tmp_path: Path) -> None:
    artifact_dir, runtime_root, ref1_dir, ref2_dir, approval_root = _copy_runtime(tmp_path)
    (ref1_dir / "approval_manifest.json").unlink()
    missing_ref1 = validate_module1_ref_runtime(
        "ref2_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=ref1_dir,
        ref2_approval_dir=ref2_dir,
        approval_allowed_root=approval_root,
    )
    assert missing_ref1.status == "BLOCKED"
    assert missing_ref1.projection is None
    assert "REF1_APPROVAL_MISSING" in {issue.code for issue in missing_ref1.issues}

    artifact_dir, runtime_root, ref1_dir, ref2_dir, approval_root = _copy_runtime(tmp_path / "second")
    (ref2_dir / "approval_manifest.json").unlink()
    missing_ref2 = validate_module1_ref_runtime(
        "ref2_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=ref1_dir,
        ref2_approval_dir=ref2_dir,
        approval_allowed_root=approval_root,
    )
    assert missing_ref2.status == "BLOCKED"
    assert missing_ref2.projection is None
    assert "APPROVAL_MISSING" in {issue.code for issue in missing_ref2.issues}
    assert missing_ref2.database_writes == missing_ref2.preference_writes == 0


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        (lambda p: p.update(approval_schema_version="2.0"), "APPROVAL_SCHEMA_INVALID"),
        (lambda p: p.update(decision_number=38), "APPROVAL_DECISION_INVALID"),
        (lambda p: p.update(approved_modes=["ref1_read"]), "APPROVED_MODES_INVALID"),
        (lambda p: p["prerequisite_approvals"][0].update(approval_sha256="0" * 64), "PREREQUISITE_CONTRACT_INVALID"),
        (lambda p: p["runtime_package"].update(manifest_sha256="0" * 64), "RUNTIME_PACKAGE_INVALID"),
        (lambda p: p["purpose_policy"].update(unknown_purpose="allow"), "PURPOSE_POLICY_INVALID"),
        (lambda p: p["required_semantics_policy"].update(ref_source_required="write_source_of_truth"), "REQUIRED_POLICY_INVALID"),
        (lambda p: p["runtime_only_fields_policy"].update(preserve=False), "RUNTIME_ONLY_POLICY_INVALID"),
        (lambda p: p["assignment_policy"].update(review_excluded=0), "ASSIGNMENT_POLICY_INVALID"),
        (lambda p: p["packaging_boundary_policy"].update(diagnostics_only=False), "PACKAGING_POLICY_INVALID"),
        (lambda p: p["write_policy"].update(material_write_for_ref_only_fields=True), "WRITE_POLICY_INVALID"),
        (lambda p: p["activation_flags"].update(ref3_activation_allowed=True), "ACTIVATION_FLAGS_INVALID"),
    ],
)
def test_approval_contract_mutations_fail_closed(
    tmp_path: Path,
    mutation,
    expected_issue: str,
) -> None:
    artifact_dir, runtime_root, ref1_dir, ref2_dir, approval_root = _copy_runtime(tmp_path)
    path = ref2_dir / "approval_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutation(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = validate_module1_ref_runtime(
        "ref2_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=ref1_dir,
        ref2_approval_dir=ref2_dir,
        approval_allowed_root=approval_root,
    )
    codes = {issue.code for issue in result.issues}
    assert result.status == "BLOCKED"
    assert result.projection is None
    assert "APPROVAL_HASH_INVALID" in codes
    assert expected_issue in codes


def test_changed_artifacts_fail_before_partial_projection(tmp_path: Path) -> None:
    artifact_dir, runtime_root, ref1_dir, ref2_dir, approval_root = _copy_runtime(tmp_path)
    (artifact_dir / "fields.json").write_bytes((artifact_dir / "fields.json").read_bytes() + b" ")
    result = validate_module1_ref_runtime(
        "ref2_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=ref1_dir,
        ref2_approval_dir=ref2_dir,
        approval_allowed_root=approval_root,
    )
    assert result.status == "BLOCKED"
    assert result.projection is None
    assert result.database_writes == result.preference_writes == 0


def test_production_policy_has_no_tooling_docs_database_or_business_imports() -> None:
    source = (PROJECT_ROOT / "app/services/module1_ref2_read_policy.py").read_text(encoding="utf-8")
    for forbidden in (
        "tools.module1_ref_projection",
        "docs/Modules",
        "reference_data",
        "sqlalchemy",
        "app.database",
        "app.models",
        "module1_material_normalizer",
        "module1_matching_dedup",
        "module1_moderation_core",
        "module1_export_packages",
    ):
        assert forbidden not in source


def test_activation_records_performance_without_hard_limits(
    activation: Module1Ref2ReadActivation,
) -> None:
    assert activation.validation_duration_ms >= 0
    assert activation.ref1_validation_duration_ms >= 0
    assert activation.ref2_approval_validation_duration_ms >= 0
    assert activation.fields_load_duration_ms >= 0
    assert activation.assignments_load_duration_ms >= 0
    assert activation.projection_load_duration_ms >= 0
    assert activation.total_duration_ms >= 0
    assert activation.projection_size_bytes > 0
