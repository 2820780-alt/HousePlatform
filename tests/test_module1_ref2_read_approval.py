from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.config import settings
from app.services.module1_ref_runtime_artifacts import SUPPORTED_MODES
from tools.module1_ref_projection.ref2_read_approval import (
    APPROVAL_ID,
    APPROVAL_PATH,
    APPROVAL_SCHEMA_VERSION,
    APPROVAL_VERSION,
    PURPOSE_ALLOWLIST,
    PURPOSE_DENYLIST,
    REF1_APPROVAL_ID,
    REF1_APPROVAL_PATH,
    REF1_APPROVAL_SHA256,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PACKAGE_DIR,
    RUNTIME_PACKAGE_ID,
    TOP_LEVEL_KEYS,
    build_expected_ref2_read_approval,
    serialize_ref2_read_approval,
    validate_ref2_read_approval,
    write_expected_ref2_read_approval,
)

EXPECTED_ARTIFACT_HASHES = {
    "compatibility": "43cf3b1bce4f0424ec9204de51cb09138b452ab2a365f3a7747292937848c726",
    "fields": "1162e96b6df21d6497da545f6bf36ba0212660505a3022ec247c043031ebc959",
    "flattened_assignments": "5686cc00caac54eddf56949de4259a2ba0518d727ee5ab5fe0d79fd5b6b05e38",
}


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_path(tmp_path: Path) -> Path:
    return tmp_path / "approvals" / APPROVAL_ID / "approval_manifest.json"


def _write_candidate(tmp_path: Path, payload: dict) -> Path:
    path = _candidate_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(serialize_ref2_read_approval(payload))
    return path


def test_exact_identity_path_schema_scope_and_mode() -> None:
    payload = _read(APPROVAL_PATH)
    project_root = Path(__file__).resolve().parents[1]

    assert APPROVAL_PATH.relative_to(project_root).as_posix() == (
        "src/modules/module1/runtime_reference/approvals/"
        "ref2-read-v1-1a15fed6ebdd/approval_manifest.json"
    )
    assert payload["approval_id"] == APPROVAL_ID == "ref2-read-v1-1a15fed6ebdd"
    assert APPROVAL_ID == f"ref2-read-v1-{RUNTIME_MANIFEST_SHA256[:12]}"
    assert payload["approval_schema_version"] == APPROVAL_SCHEMA_VERSION == "1.0"
    assert payload["approval_version"] == APPROVAL_VERSION == "1.0"
    assert set(payload) == TOP_LEVEL_KEYS
    assert payload["decision_number"] == 37
    assert payload["approved_scope"] == "module1_ref2_read_only_admin_projection"
    assert payload["approved_modes"] == ["ref2_read"]


def test_runtime_package_artifacts_sources_and_ref1_prerequisite_are_pinned() -> None:
    payload = _read(APPROVAL_PATH)
    manifest = _read(RUNTIME_PACKAGE_DIR / "manifest.json")
    runtime = payload["runtime_package"]

    assert runtime["package_id"] == RUNTIME_PACKAGE_ID == manifest["artifact_set_id"]
    assert runtime["manifest_sha256"] == RUNTIME_MANIFEST_SHA256
    assert runtime["manifest_sha256"] == _sha256(RUNTIME_PACKAGE_DIR / "manifest.json")
    assert runtime["artifact_hashes"] == EXPECTED_ARTIFACT_HASHES
    assert runtime["artifact_hashes"]["fields"] == _sha256(RUNTIME_PACKAGE_DIR / "fields.json")
    assert runtime["artifact_hashes"]["flattened_assignments"] == _sha256(RUNTIME_PACKAGE_DIR / "characteristic_assignments.json")
    assert runtime["artifact_hashes"]["compatibility"] == _sha256(RUNTIME_PACKAGE_DIR / "compatibility.json")
    assert runtime["artifact_schema_version"] == "1.0"
    assert runtime["compatibility_map_version"] == "1.0"
    assert runtime["source_hashes"] == {
        item["filename"]: item["sha256"] for item in manifest["source_packages"]
    }
    assert payload["prerequisite_approvals"] == [{
        "approval_id": REF1_APPROVAL_ID,
        "approval_sha256": REF1_APPROVAL_SHA256,
        "required_mode": "ref1_read",
    }]
    assert _sha256(REF1_APPROVAL_PATH) == REF1_APPROVAL_SHA256


def test_counts_overlap_assignments_and_runtime_only_policies_are_exact() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["counts"] == {
        "assignments_blocked": 0, "assignments_eligible": 930,
        "assignments_fully_readable": 619, "assignments_readable_with_warnings": 311,
        "assignments_review_excluded": 48, "assignments_total": 978, "fields": 558,
        "overlap_read_compatible": 21, "overlap_required_semantics_mismatch": 6,
        "overlap_review_required": 19, "overlap_total": 46,
        "packaging_affected_material_types": 316, "packaging_mismatches": 345,
        "profiles": 177, "runtime_only_fields": 28,
    }
    assert payload["overlap_compatibility_policy"] == {
        "read_compatible": 21, "required_semantics_mismatch": 6,
        "review_required": 19, "total": 46, "write_compatibility_inferred": False,
    }
    assert payload["assignment_policy"] == {
        "blocked": 0, "eligible": 930, "fully_readable": 619,
        "readable_with_warnings": 311, "review_excluded": 48,
        "review_excluded_interpretation": "schema_review_excluded",
        "review_excluded_is_empty_schema": False, "total": 978,
    }
    assert payload["runtime_only_fields_policy"] == {
        "automatic_deprecation_allowed": False, "count": 28,
        "delete_allowed": False, "preserve": True, "rename_allowed": False,
    }


def test_purpose_required_packaging_read_write_and_activation_policies_are_exact() -> None:
    payload = _read(APPROVAL_PATH)

    assert payload["purpose_policy"] == {
        "allow": list(PURPOSE_ALLOWLIST), "deny": list(PURPOSE_DENYLIST),
        "purpose_source": "server_owned", "unknown_purpose": "deny",
    }
    assert payload["required_semantics_policy"] == {
        "automatic_required_activation": False,
        "legacy_effective_required": "write_source_of_truth",
        "ref_source_required": "metadata_only",
        "required_mismatch_blocks_admin_read": False,
        "required_mismatch_blocks_future_automatic_write_activation": True,
    }
    assert payload["packaging_boundary_policy"] == {
        "affected_material_types": 316, "automatic_correction_allowed": False,
        "diagnostics_only": True, "mismatches": 345,
        "package_quantity_is_characteristic": False, "packaging_owner": "REF-3",
        "price_basis_is_characteristic": False, "ref3_activation_allowed": False,
    }
    assert payload["read_policy"] == {
        "admin_projection_artifact_backed": True, "database_reads_required": False,
        "existing_schema_registry_extended": False,
        "existing_schema_registry_replaced": False,
        "second_public_registry_allowed": False,
        "visible_for_allowlisted_admin_read": True,
    }
    assert payload["write_policy"] == {
        "catalog_product_write_for_ref_only_fields": False,
        "legacy_behavior_unchanged": True, "matching_for_ref_only_fields": False,
        "material_write_for_ref_only_fields": False,
        "moderation_for_ref_only_fields": False, "module2_for_ref_only_fields": False,
        "module5_for_ref_only_fields": False,
        "normalizer_output_for_ref_only_fields": False,
        "readiness_export_for_ref_only_fields": False,
    }
    assert payload["activation_flags"] == {
        "ref3_activation_allowed": False,
        "runtime_activation_allowed": True,
        "write_activation_allowed": False,
    }


def test_rollback_has_both_targets_and_no_persistence_side_effects() -> None:
    policy = _read(APPROVAL_PATH)["rollback_policy"]

    assert policy["allowed_target_modes"] == ["legacy", "ref1_read"]
    assert policy["artifact_deletion_required"] is False
    assert policy["database_migration_required"] is False
    assert policy["database_update_required"] is False
    assert policy["existing_records_reclassification_required"] is False
    assert policy["requires_restart"] is True
    assert policy["stale_ref2_field_code_behavior"] == "ignore_as_unknown"


def test_canonical_serialization_is_exact_and_deterministic(tmp_path: Path) -> None:
    payload = build_expected_ref2_read_approval()
    first = write_expected_ref2_read_approval(_candidate_path(tmp_path / "first"))
    second = write_expected_ref2_read_approval(_candidate_path(tmp_path / "second"))
    raw = APPROVAL_PATH.read_bytes()

    assert payload["canonical_serialization"] == {
        "bom": False, "encoding": "UTF-8", "ensure_ascii": False,
        "hash_algorithm": "SHA-256", "indent": 2, "line_ending": "LF",
        "sort_keys": True, "trailing_newline": True,
    }
    assert first.read_bytes() == second.read_bytes() == raw
    assert raw == serialize_ref2_read_approval(payload)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    assert _sha256(first) == _sha256(second) == _sha256(APPROVAL_PATH)


def test_pure_validator_accepts_committed_approval() -> None:
    result = validate_ref2_read_approval()

    assert result.is_valid is True
    assert result.issues == ()
    assert result.approval_sha256 == _sha256(APPROVAL_PATH)


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        (lambda p: p.update(extra=True), "TOP_LEVEL_KEYS_EXTRA"),
        (lambda p: p.pop("counts"), "TOP_LEVEL_KEYS_MISSING"),
        (lambda p: p.update(approval_schema_version="2.0"), "SCHEMA_VERSION_INVALID"),
        (lambda p: p.update(approved_modes=["ref1_read"]), "APPROVED_MODES_INVALID"),
        (lambda p: p["prerequisite_approvals"][0].update(approval_sha256="0" * 64), "PREREQUISITE_CONTRACT_INVALID"),
        (lambda p: p["runtime_package"].update(manifest_sha256="0" * 64), "RUNTIME_PACKAGE_INVALID"),
        (lambda p: p["purpose_policy"].update(unknown_purpose="allow"), "PURPOSE_POLICY_INVALID"),
        (lambda p: p["required_semantics_policy"].update(ref_source_required="write_source_of_truth"), "REQUIRED_POLICY_INVALID"),
        (lambda p: p["runtime_only_fields_policy"].update(delete_allowed=True), "RUNTIME_ONLY_POLICY_INVALID"),
        (lambda p: p["assignment_policy"].update(review_excluded_is_empty_schema=True), "ASSIGNMENT_POLICY_INVALID"),
        (lambda p: p["packaging_boundary_policy"].update(diagnostics_only=False), "PACKAGING_POLICY_INVALID"),
        (lambda p: p["write_policy"].update(material_write_for_ref_only_fields=True), "WRITE_POLICY_INVALID"),
        (lambda p: p["activation_flags"].update(ref3_activation_allowed=True), "ACTIVATION_FLAGS_INVALID"),
    ],
)
def test_validator_fails_closed_for_contract_mutations(tmp_path: Path, mutation, expected_issue: str) -> None:
    payload = build_expected_ref2_read_approval()
    mutation(payload)
    result = validate_ref2_read_approval(_write_candidate(tmp_path, payload))

    assert result.is_valid is False
    assert expected_issue in {issue.code for issue in result.issues}


def test_validator_fails_closed_for_missing_or_changed_ref1_prerequisite(tmp_path: Path) -> None:
    missing = validate_ref2_read_approval(prerequisite_path=tmp_path / "missing.json")
    changed = tmp_path / "approval_manifest.json"
    changed.write_bytes(REF1_APPROVAL_PATH.read_bytes() + b"\n")
    changed_result = validate_ref2_read_approval(prerequisite_path=changed)

    assert "REF1_APPROVAL_MISSING" in {issue.code for issue in missing.issues}
    assert "REF1_APPROVAL_HASH_INVALID" in {issue.code for issue in changed_result.issues}


def test_runtime_package_and_ref1_approval_files_are_unchanged() -> None:
    manifest = _read(RUNTIME_PACKAGE_DIR / "manifest.json")

    assert _sha256(RUNTIME_PACKAGE_DIR / "manifest.json") == RUNTIME_MANIFEST_SHA256
    assert _sha256(REF1_APPROVAL_PATH) == REF1_APPROVAL_SHA256
    assert set(path.name for path in RUNTIME_PACKAGE_DIR.iterdir()) == {"manifest.json", *manifest["artifacts"].keys()}
    for name, contract in manifest["artifacts"].items():
        path = RUNTIME_PACKAGE_DIR / name
        assert _sha256(path) == contract["sha256"]
        assert path.stat().st_size == contract["size_bytes"]


def test_decision_and_approved_runtime_mode_are_present_without_tooling_import() -> None:
    project_root = Path(__file__).resolve().parents[1]
    decisions = (project_root / "docs" / "Decisions.md").read_text(encoding="utf-8")
    config = (project_root / "app" / "config.py").read_text(encoding="utf-8")
    app_sources = "\n".join(path.read_text(encoding="utf-8") for path in (project_root / "app").rglob("*.py"))

    decision_heading = "## \u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u2116037"
    accepted_status = "\u0421\u0442\u0430\u0442\u0443\u0441:\n\u041f\u0440\u0438\u043d\u044f\u0442\u043e."
    assert decisions.count(decision_heading) == 1
    assert accepted_status in decisions.split(decision_heading, 1)[1]
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"
    assert "ref2_read" in SUPPORTED_MODES
    assert "MODULE1_REF2_APPROVAL_ID" in config
    assert "module1_ref_projection.ref2_read_approval" not in app_sources
    assert "/ref2-characteristic-schemas" in app_sources


def test_tooling_has_no_database_orm_ui_or_runtime_imports() -> None:
    path = Path(__file__).resolve().parents[1] / "tools/module1_ref_projection/ref2_read_approval.py"
    text = path.read_text(encoding="utf-8")

    for forbidden in ("sqlalchemy", "app.database", "app.models", "app.services", "templates", "Dashboard", "Quick Actions"):
        assert forbidden not in text