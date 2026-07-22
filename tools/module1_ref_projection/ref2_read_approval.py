from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .portability import portable_identity_or_raw


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
RUNTIME_PACKAGE_ID = "ref-runtime-v1-122079b1c558fefc"
RUNTIME_PACKAGE_DIR = RUNTIME_REFERENCE_ROOT / RUNTIME_PACKAGE_ID
RUNTIME_MANIFEST_SHA256 = "1a15fed6ebddb77c293b8a77539f790b5733215ef3a748a52f3c83a33fe75e9f"
APPROVAL_ID = "ref2-read-v1-1a15fed6ebdd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
REF1_APPROVAL_ID = "ref1-read-v1-1a15fed6ebdd"
REF1_APPROVAL_SHA256 = "55c9f09aa1db034f22108f02a2f2afe692bdf58650ff4d2a8d0d8b70b1799973"
REF1_APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / REF1_APPROVAL_ID / "approval_manifest.json"
DECISIONS_PATH = PROJECT_ROOT / "docs" / "Decisions.md"

TOP_LEVEL_KEYS = frozenset({
    "activation_flags", "approval_id", "approval_schema_version", "approval_version",
    "approved_modes", "approved_scope", "assignment_policy", "canonical_serialization",
    "counts", "decision_number", "overlap_compatibility_policy", "packaging_boundary_policy",
    "prerequisite_approvals", "purpose_policy", "read_policy", "required_semantics_policy",
    "rollback_policy", "runtime_only_fields_policy", "runtime_package", "write_policy",
})
PURPOSE_ALLOWLIST = ("admin_characteristic_schema_read", "internal_diagnostics")
PURPOSE_DENYLIST = (
    "analyzer_business_processing", "catalog_product_write", "dashboard",
    "documents_business_processing", "existing_material_details", "existing_materials_table",
    "matching_candidate", "material_write", "moderation_approval", "module2_export",
    "module5_export", "normalizer_output", "readiness_export", "widgets",
)


@dataclass(frozen=True)
class Ref2ApprovalValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class Ref2ApprovalValidationResult:
    is_valid: bool
    approval_sha256: str | None
    issues: tuple[Ref2ApprovalValidationIssue, ...]


def build_expected_ref2_read_approval(
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
) -> dict[str, Any]:
    package = Path(runtime_package_dir)
    manifest_path = package / "manifest.json"
    manifest = _read_json(manifest_path)
    artifacts = manifest["artifacts"]
    source_hashes = {
        str(item["filename"]): str(item["sha256"])
        for item in manifest["source_packages"]
    }
    return {
        "activation_flags": {
            "ref3_activation_allowed": False,
            "runtime_activation_allowed": True,
            "write_activation_allowed": False,
        },
        "approval_id": APPROVAL_ID,
        "approval_schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_version": APPROVAL_VERSION,
        "approved_modes": ["ref2_read"],
        "approved_scope": "module1_ref2_read_only_admin_projection",
        "assignment_policy": {
            "blocked": 0,
            "eligible": 930,
            "fully_readable": 619,
            "readable_with_warnings": 311,
            "review_excluded": 48,
            "review_excluded_interpretation": "schema_review_excluded",
            "review_excluded_is_empty_schema": False,
            "total": 978,
        },
        "canonical_serialization": {
            "bom": False,
            "encoding": "UTF-8",
            "ensure_ascii": False,
            "hash_algorithm": "SHA-256",
            "indent": 2,
            "line_ending": "LF",
            "sort_keys": True,
            "trailing_newline": True,
        },
        "counts": {
            "assignments_blocked": 0,
            "assignments_eligible": 930,
            "assignments_fully_readable": 619,
            "assignments_readable_with_warnings": 311,
            "assignments_review_excluded": 48,
            "assignments_total": 978,
            "fields": 558,
            "overlap_read_compatible": 21,
            "overlap_required_semantics_mismatch": 6,
            "overlap_review_required": 19,
            "overlap_total": 46,
            "packaging_affected_material_types": 316,
            "packaging_mismatches": 345,
            "profiles": 177,
            "runtime_only_fields": 28,
        },
        "decision_number": 37,
        "overlap_compatibility_policy": {
            "read_compatible": 21,
            "required_semantics_mismatch": 6,
            "review_required": 19,
            "total": 46,
            "write_compatibility_inferred": False,
        },
        "packaging_boundary_policy": {
            "affected_material_types": 316,
            "automatic_correction_allowed": False,
            "diagnostics_only": True,
            "mismatches": 345,
            "package_quantity_is_characteristic": False,
            "packaging_owner": "REF-3",
            "price_basis_is_characteristic": False,
            "ref3_activation_allowed": False,
        },
        "prerequisite_approvals": [{
            "approval_id": REF1_APPROVAL_ID,
            "approval_sha256": REF1_APPROVAL_SHA256,
            "required_mode": "ref1_read",
        }],
        "purpose_policy": {
            "allow": list(PURPOSE_ALLOWLIST),
            "deny": list(PURPOSE_DENYLIST),
            "purpose_source": "server_owned",
            "unknown_purpose": "deny",
        },
        "read_policy": {
            "admin_projection_artifact_backed": True,
            "database_reads_required": False,
            "existing_schema_registry_extended": False,
            "existing_schema_registry_replaced": False,
            "second_public_registry_allowed": False,
            "visible_for_allowlisted_admin_read": True,
        },
        "required_semantics_policy": {
            "automatic_required_activation": False,
            "legacy_effective_required": "write_source_of_truth",
            "ref_source_required": "metadata_only",
            "required_mismatch_blocks_admin_read": False,
            "required_mismatch_blocks_future_automatic_write_activation": True,
        },
        "rollback_policy": {
            "allowed_target_modes": ["legacy", "ref1_read"],
            "artifact_deletion_required": False,
            "database_migration_required": False,
            "database_update_required": False,
            "existing_records_reclassification_required": False,
            "requires_restart": True,
            "stale_ref2_field_code_behavior": "ignore_as_unknown",
        },
        "runtime_only_fields_policy": {
            "automatic_deprecation_allowed": False,
            "count": 28,
            "delete_allowed": False,
            "preserve": True,
            "rename_allowed": False,
        },
        "runtime_package": {
            "artifact_hashes": {
                "compatibility": str(artifacts["compatibility.json"]["sha256"]),
                "fields": str(artifacts["fields.json"]["sha256"]),
                "flattened_assignments": str(artifacts["characteristic_assignments.json"]["sha256"]),
            },
            "artifact_schema_version": str(manifest["artifact_schema_version"]),
            "compatibility_map_version": str(manifest["compatibility_map_version"]),
            "manifest_sha256": _sha256_file(manifest_path),
            "package_id": str(manifest["artifact_set_id"]),
            "source_hashes": dict(sorted(source_hashes.items())),
        },
        "write_policy": {
            "catalog_product_write_for_ref_only_fields": False,
            "legacy_behavior_unchanged": True,
            "matching_for_ref_only_fields": False,
            "material_write_for_ref_only_fields": False,
            "moderation_for_ref_only_fields": False,
            "module2_for_ref_only_fields": False,
            "module5_for_ref_only_fields": False,
            "normalizer_output_for_ref_only_fields": False,
            "readiness_export_for_ref_only_fields": False,
        },
    }


def serialize_ref2_read_approval(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_expected_ref2_read_approval(
    output_path: Path | str,
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_ref2_read_approval(build_expected_ref2_read_approval(runtime_package_dir)))
    return target


def validate_ref2_read_approval(
    approval_path: Path | str = APPROVAL_PATH,
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
    prerequisite_path: Path | str = REF1_APPROVAL_PATH,
    decisions_path: Path | str = DECISIONS_PATH,
) -> Ref2ApprovalValidationResult:
    path = Path(approval_path)
    package = Path(runtime_package_dir)
    prerequisite = Path(prerequisite_path)
    issues: list[Ref2ApprovalValidationIssue] = []
    try:
        payload = _read_json(path)
        expected = build_expected_ref2_read_approval(package)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return Ref2ApprovalValidationResult(False, None, (Ref2ApprovalValidationIssue("APPROVAL_LOAD_FAILED", str(exc)),))

    keys = set(payload)
    if TOP_LEVEL_KEYS - keys:
        issues.append(Ref2ApprovalValidationIssue("TOP_LEVEL_KEYS_MISSING", ", ".join(sorted(TOP_LEVEL_KEYS - keys))))
    if keys - TOP_LEVEL_KEYS:
        issues.append(Ref2ApprovalValidationIssue("TOP_LEVEL_KEYS_EXTRA", ", ".join(sorted(keys - TOP_LEVEL_KEYS))))

    checks = (
        (payload.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (payload.get("approval_schema_version") == "1.0", "SCHEMA_VERSION_INVALID"),
        (payload.get("approval_version") == "1.0", "APPROVAL_VERSION_INVALID"),
        (payload.get("decision_number") == 37, "DECISION_INVALID"),
        (payload.get("approved_modes") == ["ref2_read"], "APPROVED_MODES_INVALID"),
        (payload.get("prerequisite_approvals") == expected["prerequisite_approvals"], "PREREQUISITE_CONTRACT_INVALID"),
        (payload.get("runtime_package") == expected["runtime_package"], "RUNTIME_PACKAGE_INVALID"),
        (payload.get("counts") == expected["counts"], "COUNTS_INVALID"),
        (payload.get("purpose_policy") == expected["purpose_policy"], "PURPOSE_POLICY_INVALID"),
        (payload.get("required_semantics_policy") == expected["required_semantics_policy"], "REQUIRED_POLICY_INVALID"),
        (payload.get("runtime_only_fields_policy") == expected["runtime_only_fields_policy"], "RUNTIME_ONLY_POLICY_INVALID"),
        (payload.get("overlap_compatibility_policy") == expected["overlap_compatibility_policy"], "OVERLAP_POLICY_INVALID"),
        (payload.get("assignment_policy") == expected["assignment_policy"], "ASSIGNMENT_POLICY_INVALID"),
        (payload.get("packaging_boundary_policy") == expected["packaging_boundary_policy"], "PACKAGING_POLICY_INVALID"),
        (payload.get("read_policy") == expected["read_policy"], "READ_POLICY_INVALID"),
        (payload.get("write_policy") == expected["write_policy"], "WRITE_POLICY_INVALID"),
        (payload.get("rollback_policy") == expected["rollback_policy"], "ROLLBACK_POLICY_INVALID"),
        (payload.get("activation_flags") == expected["activation_flags"], "ACTIVATION_FLAGS_INVALID"),
        (payload.get("canonical_serialization") == expected["canonical_serialization"], "SERIALIZATION_POLICY_INVALID"),
        (payload == expected, "APPROVAL_PAYLOAD_NOT_CANONICAL"),
        (path.read_bytes() == serialize_ref2_read_approval(expected), "APPROVAL_BYTES_NOT_DETERMINISTIC"),
    )
    for passed, code in checks:
        if not passed:
            issues.append(Ref2ApprovalValidationIssue(code, code.replace("_", " ").title()))

    expected_suffix = Path("approvals") / APPROVAL_ID / "approval_manifest.json"
    if Path(*path.parts[-3:]) != expected_suffix:
        issues.append(Ref2ApprovalValidationIssue("APPROVAL_PATH_INVALID", str(path)))
    if APPROVAL_ID != f"ref2-read-v1-{expected['runtime_package']['manifest_sha256'][:12]}":
        issues.append(Ref2ApprovalValidationIssue("APPROVAL_ID_DERIVATION_INVALID", APPROVAL_ID))

    issues.extend(_validate_decision(Path(decisions_path)))
    issues.extend(_validate_prerequisite(prerequisite, expected["runtime_package"]))
    issues.extend(_validate_runtime_package(package))
    return Ref2ApprovalValidationResult(not issues, _sha256_file(path), tuple(issues))


def _validate_decision(path: Path) -> list[Ref2ApprovalValidationIssue]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Ref2ApprovalValidationIssue("DECISION_LOAD_FAILED", str(exc))]
    if text.count("## Решение №037") != 1:
        return [Ref2ApprovalValidationIssue("DECISION_037_MISSING", str(path))]
    if "Статус:\nПринято." not in text.split("## Решение №037", 1)[1]:
        return [Ref2ApprovalValidationIssue("DECISION_037_NOT_ACCEPTED", str(path))]
    return []


def _validate_prerequisite(path: Path, runtime_contract: Mapping[str, Any]) -> list[Ref2ApprovalValidationIssue]:
    issues: list[Ref2ApprovalValidationIssue] = []
    if not path.is_file():
        return [Ref2ApprovalValidationIssue("REF1_APPROVAL_MISSING", str(path))]
    if _sha256_file(path) != REF1_APPROVAL_SHA256:
        issues.append(Ref2ApprovalValidationIssue("REF1_APPROVAL_HASH_INVALID", str(path)))
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return issues + [Ref2ApprovalValidationIssue("REF1_APPROVAL_LOAD_FAILED", str(exc))]
    checks = (
        (payload.get("approval_id") == REF1_APPROVAL_ID, "REF1_APPROVAL_ID_INVALID"),
        (payload.get("approved_modes") == ["ref1_read"], "REF1_MODE_INVALID"),
        (payload.get("write_activation_allowed") is False, "REF1_WRITE_POLICY_INVALID"),
        (payload.get("runtime_package_id") == runtime_contract.get("package_id"), "REF1_PACKAGE_ID_INVALID"),
        (payload.get("runtime_manifest_hash") == runtime_contract.get("manifest_sha256"), "REF1_MANIFEST_HASH_INVALID"),
    )
    for passed, code in checks:
        if not passed:
            issues.append(Ref2ApprovalValidationIssue(code, code.replace("_", " ").title()))
    return issues


def _validate_runtime_package(package: Path) -> list[Ref2ApprovalValidationIssue]:
    issues: list[Ref2ApprovalValidationIssue] = []
    manifest_path = package / "manifest.json"
    try:
        manifest = _read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [Ref2ApprovalValidationIssue("RUNTIME_MANIFEST_LOAD_FAILED", str(exc))]
    if _sha256_file(manifest_path) != RUNTIME_MANIFEST_SHA256:
        issues.append(Ref2ApprovalValidationIssue("RUNTIME_MANIFEST_HASH_INVALID", str(manifest_path)))
    if manifest.get("artifact_set_id") != RUNTIME_PACKAGE_ID or package.name != RUNTIME_PACKAGE_ID:
        issues.append(Ref2ApprovalValidationIssue("RUNTIME_PACKAGE_ID_INVALID", str(package)))
    for name, contract in manifest.get("artifacts", {}).items():
        artifact = package / name
        if not artifact.is_file() or _sha256_file(artifact) != contract.get("sha256") or artifact.stat().st_size != contract.get("size_bytes"):
            issues.append(Ref2ApprovalValidationIssue("RUNTIME_ARTIFACT_CHANGED", name))
    return issues


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    return portable_identity_or_raw(path)