from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .ref45 import (
    ARTIFACT_FILENAMES,
    ARTIFACT_SCHEMA_VERSION,
    ARTIFACT_SET_ID,
    EXPECTED_COUNTS,
    REFERENCE_ROOT,
    RUNTIME_REFERENCE_ROOT,
    SOURCE_FILES,
    canonical_json_bytes,
    canonical_serialization_contract,
    sha256_file,
    validate_ref45_runtime_artifacts,
)


APPROVAL_ID = "ref45-activation-v1-5fe5e067d0dd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
TOP_LEVEL_KEYS = frozenset(
    {
        "activation_flags",
        "approval_id",
        "approval_schema_version",
        "approval_version",
        "approved_modes",
        "approved_scope",
        "canonical_serialization",
        "counts",
        "decision_number",
        "review_policy",
        "rollback_policy",
        "runtime_artifact",
        "source_package",
        "substitution_policy",
        "trusted_policy",
    }
)


@dataclass(frozen=True)
class Ref45ApprovalIssue:
    code: str
    message: str


@dataclass(frozen=True)
class Ref45ApprovalValidation:
    is_valid: bool
    approval_sha256: str | None
    issues: tuple[Ref45ApprovalIssue, ...]


def build_expected_ref45_approval(
    runtime_package_dir: str | Path = RUNTIME_REFERENCE_ROOT / ARTIFACT_SET_ID,
    reference_root: str | Path = REFERENCE_ROOT,
) -> dict[str, Any]:
    package = Path(runtime_package_dir)
    reference_root = Path(reference_root)
    manifest = validate_ref45_runtime_artifacts(package)
    artifact_hashes = {
        name.removesuffix(".json"): str(manifest["artifacts"][name]["sha256"])
        for name in ARTIFACT_FILENAMES
    }
    source_hashes = {
        package_id: {
            "filename": filename,
            "sha256": sha256_file(reference_root / filename),
        }
        for package_id, (filename, _expected_hash) in sorted(SOURCE_FILES.items())
    }
    return {
        "activation_flags": {
            "automatic_alias_learning_allowed": False,
            "automatic_replacement_allowed": False,
            "context_alias_auto_resolution_allowed": False,
            "fuzzy_alias_resolution_allowed": False,
            "module2_execution_allowed": False,
            "module5_execution_allowed": False,
            "ref5_read_policy_allowed": True,
            "trusted_alias_resolution_allowed": True,
            "work_mapping_activation_allowed": False,
            "write_activation_allowed": False,
        },
        "approval_id": APPROVAL_ID,
        "approval_schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_version": APPROVAL_VERSION,
        "approved_modes": ["approved"],
        "approved_scope": "module1_ref4_ref5_governed_policy",
        "canonical_serialization": canonical_serialization_contract(),
        "counts": dict(EXPECTED_COUNTS),
        "decision_number": 40,
        "review_policy": {
            "automatic_review_approval_allowed": False,
            "ref4_review_items": 45,
            "ref5_review_items": 10,
            "review_items_active_for_business_resolution": False,
        },
        "rollback_policy": {
            "artifact_deletion_required": False,
            "database_migration_required": False,
            "database_update_required": False,
            "record_reclassification_required": False,
            "requires_restart": True,
            "target_mode": "legacy",
        },
        "runtime_artifact": {
            "artifact_hashes": dict(sorted(artifact_hashes.items())),
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "manifest_sha256": sha256_file(package / "manifest.json"),
            "package_id": ARTIFACT_SET_ID,
        },
        "source_package": {
            "package_status": "preliminary_approved",
            "source_hashes": source_hashes,
            "version": "1.0.1",
        },
        "substitution_policy": {
            "active_read_only_or_safety": 3,
            "automatic_selection_allowed": False,
            "automatic_write_allowed": False,
            "cement_screed_to_dry_screed": "review_only",
            "directed_relation_types": [
                "conditional_replacement",
                "functional_alternative",
                "technical_alternative",
            ],
            "module2_calculation_allowed": False,
            "module5_costing_allowed": False,
            "review_rules": 10,
            "rules": 13,
            "work_material_mappings": 0,
        },
        "trusted_policy": {
            "automatic_rules": 44,
            "brand_alias_creation_allowed": False,
            "dimension_grade_variant_preservation_required": True,
            "fuzzy_matching_allowed": False,
            "generic_alias_subtype_resolution_allowed": False,
            "scope_precedence": ["source_profile", "material_direction", "global"],
        },
    }


def serialize_ref45_approval(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload)


def write_expected_ref45_approval(path: str | Path = APPROVAL_PATH) -> Path:
    target = Path(path)
    expected = serialize_ref45_approval(build_expected_ref45_approval())
    if target.exists():
        if target.read_bytes() != expected:
            raise ValueError(f"Immutable REF-4/5 approval already differs: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(expected)
    return target


def validate_ref45_approval(
    path: str | Path = APPROVAL_PATH,
    *,
    runtime_package_dir: str | Path = RUNTIME_REFERENCE_ROOT / ARTIFACT_SET_ID,
    reference_root: str | Path = REFERENCE_ROOT,
) -> Ref45ApprovalValidation:
    candidate = Path(path)
    issues: list[Ref45ApprovalIssue] = []
    if not candidate.is_file():
        return Ref45ApprovalValidation(False, None, (Ref45ApprovalIssue("APPROVAL_MISSING", "Approval file is missing"),))
    raw = candidate.read_bytes()
    approval_hash = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Ref45ApprovalValidation(False, approval_hash, (Ref45ApprovalIssue("APPROVAL_INVALID_JSON", str(exc)),))
    if not isinstance(payload, dict) or set(payload) != TOP_LEVEL_KEYS:
        issues.append(Ref45ApprovalIssue("APPROVAL_KEYS_INVALID", "Approval top-level keys are invalid"))
    try:
        expected = build_expected_ref45_approval(runtime_package_dir, reference_root)
    except (OSError, ValueError) as exc:
        issues.append(Ref45ApprovalIssue("APPROVAL_DEPENDENCY_INVALID", str(exc)))
        expected = None
    if expected is not None and payload != expected:
        issues.append(Ref45ApprovalIssue("APPROVAL_CONTENT_INVALID", "Approval content is not the canonical approved contract"))
    if raw != serialize_ref45_approval(payload):
        issues.append(Ref45ApprovalIssue("APPROVAL_SERIALIZATION_INVALID", "Approval serialization is not canonical"))
    return Ref45ApprovalValidation(not issues, approval_hash, tuple(issues))