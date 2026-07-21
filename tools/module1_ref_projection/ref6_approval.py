from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from tools.module1_ref_projection.ref6 import (
    ARTIFACT_SET_ID,
    EXPECTED_COUNTS,
    REFERENCE_ROOT,
    RUNTIME_REFERENCE_ROOT,
    SOURCE_HASHES,
    canonical_json_bytes,
    sha256_file,
    validate_ref6_runtime_artifacts,
)


APPROVAL_ID = "ref6-activation-v1-2256595bd388"
APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
TOP_LEVEL_KEYS = {
    "activation_flags",
    "approval_id",
    "approved_modes",
    "approved_scope",
    "consumer_ownership",
    "counts",
    "decision_number",
    "module",
    "rollback_policy",
    "runtime_artifact",
    "schema_version",
    "source_package",
}


@dataclass(frozen=True)
class Ref6ApprovalIssue:
    code: str
    message: str


@dataclass(frozen=True)
class Ref6ApprovalValidation:
    is_valid: bool
    approval_sha256: str | None
    issues: tuple[Ref6ApprovalIssue, ...]


def build_expected_ref6_approval(
    runtime_package_dir: str | Path = RUNTIME_REFERENCE_ROOT / ARTIFACT_SET_ID,
    reference_root: str | Path = REFERENCE_ROOT,
) -> dict[str, Any]:
    package = Path(runtime_package_dir)
    manifest = validate_ref6_runtime_artifacts(package)
    root = Path(reference_root)
    source_hashes = {
        name: sha256_file(root / name)
        for name in sorted(SOURCE_HASHES)
    }
    if source_hashes != dict(sorted(SOURCE_HASHES.items())):
        raise ValueError("REF-6 approval source hashes do not match the approved package")
    return {
        "activation_flags": {
            "catalog_product_selection_allowed": False,
            "conditional_hint_execution_allowed": False,
            "conditional_hint_read_allowed": True,
            "database_write_allowed": False,
            "material_creation_allowed": False,
            "module2_execution_allowed": False,
            "module5_costing_allowed": False,
            "quantity_calculation_allowed": False,
            "ref3_formula_activation_allowed": False,
            "review_hint_execution_allowed": False,
            "safe_role_hint_execution_as_type_hint_allowed": True,
            "safe_role_hint_read_allowed": True,
            "sku_selection_allowed": False,
        },
        "approval_id": APPROVAL_ID,
        "approved_modes": ["approved"],
        "approved_scope": "module1_ref6_governed_work_material_hints",
        "consumer_ownership": {
            "module1": "role_type_conditions_restrictions",
            "module2": "technology_geometry_volume_quantity",
            "module5": "price_packaging_rounding_estimate",
            "ref6_direct_module5_costing_allowed": False,
        },
        "counts": dict(EXPECTED_COUNTS),
        "decision_number": 41,
        "module": 1,
        "rollback_policy": {
            "artifact_deletion": False,
            "database_migration": False,
            "database_update": False,
            "record_reclassification": False,
            "restart_required": True,
            "target_mode": "legacy",
        },
        "runtime_artifact": {
            "artifact_hashes": {
                name: metadata["sha256"]
                for name, metadata in sorted(manifest["artifacts"].items())
            },
            "manifest_sha256": sha256_file(package / "manifest.json"),
            "package_id": ARTIFACT_SET_ID,
        },
        "schema_version": "1.0",
        "source_package": {
            "package_id": "REF-6",
            "source_hashes": source_hashes,
            "status": "preliminary_approved",
            "version": "1.0-preliminary-approved",
        },
    }


def serialize_ref6_approval(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload)


def write_expected_ref6_approval(path: str | Path = APPROVAL_PATH) -> Path:
    target = Path(path)
    expected = serialize_ref6_approval(build_expected_ref6_approval())
    if target.exists():
        if target.read_bytes() != expected:
            raise ValueError(f"Immutable REF-6 approval already differs: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(expected)
    return target


def validate_ref6_approval(
    path: str | Path = APPROVAL_PATH,
    *,
    runtime_package_dir: str | Path = RUNTIME_REFERENCE_ROOT / ARTIFACT_SET_ID,
    reference_root: str | Path = REFERENCE_ROOT,
) -> Ref6ApprovalValidation:
    candidate = Path(path)
    issues: list[Ref6ApprovalIssue] = []
    if not candidate.is_file():
        return Ref6ApprovalValidation(
            False,
            None,
            (Ref6ApprovalIssue("APPROVAL_MISSING", "Approval file is missing"),),
        )
    raw = candidate.read_bytes()
    approval_hash = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Ref6ApprovalValidation(
            False,
            approval_hash,
            (Ref6ApprovalIssue("APPROVAL_INVALID_JSON", str(exc)),),
        )
    if not isinstance(payload, dict) or set(payload) != TOP_LEVEL_KEYS:
        issues.append(Ref6ApprovalIssue("APPROVAL_KEYS_INVALID", "Approval top-level keys are invalid"))
    try:
        expected = build_expected_ref6_approval(runtime_package_dir, reference_root)
    except (OSError, ValueError) as exc:
        issues.append(Ref6ApprovalIssue("APPROVAL_DEPENDENCY_INVALID", str(exc)))
        expected = None
    if expected is not None and payload != expected:
        issues.append(Ref6ApprovalIssue("APPROVAL_CONTENT_INVALID", "Approval content is not canonical"))
    if raw != serialize_ref6_approval(payload):
        issues.append(Ref6ApprovalIssue("APPROVAL_SERIALIZATION_INVALID", "Approval is not canonical JSON"))
    return Ref6ApprovalValidation(not issues, approval_hash, tuple(issues))
