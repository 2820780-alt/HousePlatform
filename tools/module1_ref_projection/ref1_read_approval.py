from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
RUNTIME_PACKAGE_ID = "ref-runtime-v1-122079b1c558fefc"
RUNTIME_PACKAGE_DIR = RUNTIME_REFERENCE_ROOT / RUNTIME_PACKAGE_ID
APPROVAL_ID = "ref1-read-v1-1a15fed6ebdd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
APPROVED_PURPOSES = ("admin_taxonomy_read", "internal_diagnostics")
DENIED_PURPOSES = (
    "analyzer_business_processing",
    "catalog_product_write",
    "dashboard",
    "existing_material_details",
    "existing_materials_table",
    "matching_candidate",
    "material_write",
    "moderation_approval",
    "module2_export",
    "module5_export",
    "normalizer_output",
    "readiness_export",
    "widgets",
)


@dataclass(frozen=True)
class ApprovalValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class ApprovalValidationResult:
    is_valid: bool
    approval_sha256: str | None
    issues: tuple[ApprovalValidationIssue, ...]


def build_expected_ref1_read_approval(
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
) -> dict[str, Any]:
    package = Path(runtime_package_dir)
    manifest_path = package / "manifest.json"
    manifest = _read_json(manifest_path)
    source_hashes = {
        str(item["filename"]): str(item["sha256"])
        for item in manifest["source_packages"]
    }
    return {
        "activation_effect": "approval_metadata_only_no_runtime_activation",
        "approval_id": APPROVAL_ID,
        "approval_schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_version": APPROVAL_VERSION,
        "approved_modes": ["ref1_read"],
        "approved_scope": "module1_ref1_read_only_taxonomy_projection",
        "artifact_schema_version": str(manifest["artifact_schema_version"]),
        "canonical_conflict_policies": {
            "liquid_waterproofing": {
                "admin_read_uses_canonical_ref_parent": True,
                "canonical_ref_parent": "waterproofing",
                "code": "liquid_waterproofing",
                "duplicate_canonical_registration_allowed": False,
                "existing_records_migrated": False,
                "legacy_business_lookups_changed": False,
                "legacy_paths": ["primers_chemicals_sealants", "waterproofing"],
                "legacy_paths_metadata_only": True,
                "ref_only_write_allowed": False,
            },
            "lm": {
                "automatic_normalization_allowed": False,
                "canonical_code": "lm",
                "canonical_meaning": "lumen",
                "legacy_lm_to_linear_meter": "context_required",
                "linear_meter_canonical_code": "linear_meter",
                "ref3_activation_allowed": False,
            },
        },
        "compatibility_map_version": str(manifest["compatibility_map_version"]),
        "consumer_allowlist": list(APPROVED_PURPOSES),
        "consumer_bindings": {
            "admin_taxonomy_read": "module1.admin.taxonomy_view",
            "internal_diagnostics": "module1.internal.ref_diagnostics",
        },
        "consumer_denylist": list(DENIED_PURPOSES),
        "decision_number": "036",
        "deterministic": True,
        "integration_allowed_for_read": True,
        "read_policy": {
            "legacy_material_types": {
                "count": 192,
                "recognised_for_legacy_read": True,
                "write_behavior": "unchanged_legacy",
            },
            "ref_only_material_types": {
                "count": 786,
                "recognised_for_ref_read": "allowlisted_purpose_only",
            },
            "unknown_code": "deny",
            "unknown_purpose": "deny",
        },
        "ref2_activation_allowed": False,
        "ref3_activation_allowed": False,
        "rollback_policy": {
            "artifact_deletion_required": False,
            "database_migration_required": False,
            "mode": "legacy",
            "reclassification_required": False,
            "restart_required": True,
            "saved_ref_only_preferences_allowed": False,
            "stale_ref_only_code_behavior": "ignore_as_unknown_without_mapping_or_write",
        },
        "runtime_activation_allowed": True,
        "runtime_manifest_hash": _sha256_file(manifest_path),
        "runtime_package_id": str(manifest["artifact_set_id"]),
        "source_bundle_hash": str(manifest["source_bundle_sha256"]),
        "source_hashes": dict(sorted(source_hashes.items())),
        "write_activation_allowed": False,
        "write_policy": {
            "legacy_material_types": {
                "count": 192,
                "write_behavior": "unchanged_legacy",
            },
            "ref_only_material_types": {
                "count": 786,
                "eligible_for_catalog_product_write": False,
                "eligible_for_export": False,
                "eligible_for_matching": False,
                "eligible_for_material_write": False,
                "eligible_for_moderation_approval": False,
                "eligible_for_normalizer_output": False,
            },
        },
    }


def serialize_ref1_read_approval(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_expected_ref1_read_approval(
    output_path: Path | str,
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_ref1_read_approval(build_expected_ref1_read_approval(runtime_package_dir)))
    return target


def validate_ref1_read_approval(
    approval_path: Path | str = APPROVAL_PATH,
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
) -> ApprovalValidationResult:
    path = Path(approval_path)
    package = Path(runtime_package_dir)
    issues: list[ApprovalValidationIssue] = []
    try:
        payload = _read_json(path)
        expected = build_expected_ref1_read_approval(package)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return ApprovalValidationResult(
            False,
            None,
            (ApprovalValidationIssue("APPROVAL_LOAD_FAILED", str(exc)),),
        )

    checks = (
        (payload.get("approval_schema_version") == APPROVAL_SCHEMA_VERSION, "SCHEMA_VERSION_INVALID"),
        (payload.get("decision_number") == "036", "DECISION_INVALID"),
        (payload.get("runtime_package_id") == RUNTIME_PACKAGE_ID, "PACKAGE_ID_INVALID"),
        (payload.get("runtime_manifest_hash") == expected["runtime_manifest_hash"], "MANIFEST_HASH_INVALID"),
        (payload.get("source_hashes") == expected["source_hashes"], "SOURCE_HASHES_INVALID"),
        (payload.get("source_bundle_hash") == expected["source_bundle_hash"], "SOURCE_BUNDLE_HASH_INVALID"),
        (payload.get("artifact_schema_version") == "1.0", "ARTIFACT_SCHEMA_INVALID"),
        (payload.get("compatibility_map_version") == "1.0", "COMPATIBILITY_VERSION_INVALID"),
        (payload.get("approved_modes") == ["ref1_read"], "APPROVED_MODES_INVALID"),
        (payload.get("consumer_allowlist") == list(APPROVED_PURPOSES), "ALLOWLIST_INVALID"),
        (payload.get("consumer_denylist") == list(DENIED_PURPOSES), "DENYLIST_INVALID"),
        (payload.get("read_policy", {}).get("unknown_purpose") == "deny", "UNKNOWN_PURPOSE_POLICY_INVALID"),
        (payload.get("runtime_activation_allowed") is True, "RUNTIME_ACTIVATION_INVALID"),
        (payload.get("write_activation_allowed") is False, "WRITE_ACTIVATION_INVALID"),
        (payload.get("ref2_activation_allowed") is False, "REF2_ACTIVATION_INVALID"),
        (payload.get("ref3_activation_allowed") is False, "REF3_ACTIVATION_INVALID"),
        (payload.get("rollback_policy", {}).get("mode") == "legacy", "ROLLBACK_MODE_INVALID"),
        (_liquid_policy_valid(payload), "LIQUID_WATERPROOFING_POLICY_INVALID"),
        (_lm_policy_valid(payload), "LM_POLICY_INVALID"),
        (payload == expected, "APPROVAL_PAYLOAD_NOT_CANONICAL"),
        (path.read_bytes() == serialize_ref1_read_approval(expected), "APPROVAL_BYTES_NOT_DETERMINISTIC"),
    )
    for passed, code in checks:
        if not passed:
            issues.append(ApprovalValidationIssue(code, code.replace("_", " ").title()))

    issues.extend(_validate_runtime_package(package))
    return ApprovalValidationResult(not issues, _sha256_file(path), tuple(issues))


def _validate_runtime_package(package: Path) -> list[ApprovalValidationIssue]:
    issues: list[ApprovalValidationIssue] = []
    manifest = _read_json(package / "manifest.json")
    if manifest.get("artifact_set_id") != package.name:
        issues.append(
            ApprovalValidationIssue(
                "RUNTIME_PACKAGE_ID_MISMATCH",
                "Runtime package directory differs from manifest",
            )
        )
    for name, contract in manifest.get("artifacts", {}).items():
        path = package / name
        if (
            not path.is_file()
            or _sha256_file(path) != contract.get("sha256")
            or path.stat().st_size != contract.get("size_bytes")
        ):
            issues.append(ApprovalValidationIssue("RUNTIME_ARTIFACT_CHANGED", name))
    return issues


def _liquid_policy_valid(payload: Mapping[str, Any]) -> bool:
    policy = payload.get("canonical_conflict_policies", {}).get("liquid_waterproofing", {})
    return (
        policy.get("code") == "liquid_waterproofing"
        and policy.get("canonical_ref_parent") == "waterproofing"
        and policy.get("legacy_paths") == ["primers_chemicals_sealants", "waterproofing"]
        and policy.get("legacy_paths_metadata_only") is True
        and policy.get("existing_records_migrated") is False
        and policy.get("duplicate_canonical_registration_allowed") is False
        and policy.get("ref_only_write_allowed") is False
        and policy.get("legacy_business_lookups_changed") is False
    )


def _lm_policy_valid(payload: Mapping[str, Any]) -> bool:
    policy = payload.get("canonical_conflict_policies", {}).get("lm", {})
    return (
        policy.get("canonical_code") == "lm"
        and policy.get("canonical_meaning") == "lumen"
        and policy.get("linear_meter_canonical_code") == "linear_meter"
        and policy.get("legacy_lm_to_linear_meter") == "context_required"
        and policy.get("automatic_normalization_allowed") is False
        and policy.get("ref3_activation_allowed") is False
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()