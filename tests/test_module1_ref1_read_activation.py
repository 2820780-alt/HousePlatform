from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref1_read_policy import Module1Ref1ReadActivation
from app.services.module1_ref_runtime_artifacts import (
    DEFAULT_APPROVAL_DIR,
    DEFAULT_ARTIFACT_DIR,
    Module1RefArtifactValidationError,
    require_module1_ref_runtime_validation,
    snapshot_legacy_material_registry,
    validate_module1_ref_runtime,
)


def _copy_runtime(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    runtime_root = tmp_path / "runtime_reference"
    artifact_dir = runtime_root / DEFAULT_ARTIFACT_DIR.name
    approval_root = runtime_root / "approvals"
    approval_dir = approval_root / DEFAULT_APPROVAL_DIR.name
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact_dir)
    shutil.copytree(DEFAULT_APPROVAL_DIR, approval_dir)
    return artifact_dir, runtime_root, approval_dir, approval_root


def _activate_copy(tmp_path: Path) -> Module1Ref1ReadActivation:
    artifact_dir, runtime_root, approval_dir, approval_root = _copy_runtime(tmp_path)
    result = validate_module1_ref_runtime(
        "ref1_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=approval_dir,
        approval_allowed_root=approval_root,
    )
    assert isinstance(result, Module1Ref1ReadActivation)
    return result


def test_valid_approval_and_package_activate_ref1_read(tmp_path: Path) -> None:
    result = _activate_copy(tmp_path)

    assert result.status == "PASS"
    assert result.is_valid is True
    assert result.package_validated is True
    assert result.approval_validated is True
    assert result.database_writes == 0
    assert result.registry_mutated is False


def test_missing_approval_fails_closed_without_legacy_fallback(tmp_path: Path) -> None:
    artifact_dir, runtime_root, approval_dir, approval_root = _copy_runtime(tmp_path)
    (approval_dir / "approval_manifest.json").unlink()

    result = validate_module1_ref_runtime(
        "ref1_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=approval_dir,
        approval_allowed_root=approval_root,
    )

    assert result.status == "BLOCKED"
    assert result.mode == "ref1_read"
    assert result.business_reads_enabled is False
    assert result.projection is None
    assert result.database_writes == 0
    assert "APPROVAL_MISSING" in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    ("mutator", "expected_issue"),
    [
        (lambda data: data.update(approval_schema_version="2.0"), "APPROVAL_SCHEMA_INVALID"),
        (lambda data: data.update(decision_number="035"), "APPROVAL_DECISION_INVALID"),
        (lambda data: data.update(runtime_package_id="other"), "APPROVAL_PACKAGE_ID_INVALID"),
        (lambda data: data.update(runtime_manifest_hash="0" * 64), "APPROVAL_MANIFEST_HASH_INVALID"),
        (lambda data: data.update(compatibility_map_version="2.0"), "APPROVAL_COMPATIBILITY_VERSION_INVALID"),
        (lambda data: data.update(consumer_allowlist=["admin_taxonomy_read"]), "APPROVAL_ALLOWLIST_INVALID"),
        (lambda data: data.update(consumer_denylist=[]), "APPROVAL_DENYLIST_INVALID"),
        (lambda data: data.update(write_activation_allowed=True), "WRITE_ACTIVATION_APPROVED"),
        (lambda data: data.update(ref2_activation_allowed=True), "REF2_ACTIVATION_APPROVED"),
        (lambda data: data.update(ref3_activation_allowed=True), "REF3_ACTIVATION_APPROVED"),
    ],
)
def test_approval_contract_mutations_fail_closed(
    tmp_path: Path,
    mutator,
    expected_issue: str,
) -> None:
    artifact_dir, runtime_root, approval_dir, approval_root = _copy_runtime(tmp_path)
    path = approval_dir / "approval_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = validate_module1_ref_runtime(
        "ref1_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=approval_dir,
        approval_allowed_root=approval_root,
    )

    issue_codes = {issue.code for issue in result.issues}
    assert "APPROVAL_HASH_INVALID" in issue_codes
    assert expected_issue in issue_codes
    assert result.projection is None
    assert result.database_writes == 0


def test_package_mismatch_fails_before_projection(tmp_path: Path) -> None:
    artifact_dir, runtime_root, approval_dir, approval_root = _copy_runtime(tmp_path)
    (artifact_dir / "taxonomy.json").write_bytes((artifact_dir / "taxonomy.json").read_bytes() + b" ")

    result = validate_module1_ref_runtime(
        "ref1_read",
        artifact_dir=artifact_dir,
        allowed_root=runtime_root,
        approval_dir=approval_dir,
        approval_allowed_root=approval_root,
    )

    assert result.status == "BLOCKED"
    assert result.package_validated is False
    assert result.approval_validated is False
    assert result.projection is None
    assert "ARTIFACT_HASH_MISMATCH" in {issue.code for issue in result.issues}


def test_require_ref1_read_raises_without_partial_fallback(tmp_path: Path) -> None:
    artifact_dir, runtime_root, approval_dir, approval_root = _copy_runtime(tmp_path)
    (approval_dir / "approval_manifest.json").unlink()

    with pytest.raises(Module1RefArtifactValidationError, match="APPROVAL_MISSING"):
        require_module1_ref_runtime_validation(
            "ref1_read",
            artifact_dir=artifact_dir,
            allowed_root=runtime_root,
            approval_dir=approval_dir,
            approval_allowed_root=approval_root,
        )


def test_rollback_to_legacy_keeps_registry_snapshot_equal() -> None:
    registry = get_material_knowledge_seed_registry()
    before = snapshot_legacy_material_registry(registry)

    active = validate_module1_ref_runtime("ref1_read", registry=registry)
    rolled_back = validate_module1_ref_runtime("legacy", registry=registry)

    assert active.is_valid and active.business_reads_enabled
    assert rolled_back.status == "LEGACY"
    assert rolled_back.business_reads_enabled is False
    assert snapshot_legacy_material_registry(registry) == before


def test_activation_records_performance_without_hard_limit() -> None:
    result = validate_module1_ref_runtime("ref1_read")

    assert result.validation_duration_ms >= 0
    assert result.approval_validation_duration_ms >= 0
    assert result.projection_load_duration_ms >= 0
    assert result.total_duration_ms >= 0
    assert result.projection_size_bytes > 0
