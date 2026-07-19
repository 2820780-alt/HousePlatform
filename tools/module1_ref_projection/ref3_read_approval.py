from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
RUNTIME_PACKAGE_ID = "ref-runtime-v1-122079b1c558fefc"
RUNTIME_PACKAGE_DIR = RUNTIME_REFERENCE_ROOT / RUNTIME_PACKAGE_ID
RUNTIME_MANIFEST_SHA256 = "1a15fed6ebddb77c293b8a77539f790b5733215ef3a748a52f3c83a33fe75e9f"
APPROVAL_ID = "ref3-read-v1-1a15fed6ebdd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / APPROVAL_ID / "approval_manifest.json"
REF1_APPROVAL_ID = "ref1-read-v1-1a15fed6ebdd"
REF1_APPROVAL_SHA256 = "55c9f09aa1db034f22108f02a2f2afe692bdf58650ff4d2a8d0d8b70b1799973"
REF1_APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / REF1_APPROVAL_ID / "approval_manifest.json"
REF2_APPROVAL_ID = "ref2-read-v1-1a15fed6ebdd"
REF2_APPROVAL_SHA256 = "e5e13fba61a3aef4e94b27e22394f41d2ebbeb0b948e5f899742342e19d50e06"
REF2_APPROVAL_PATH = RUNTIME_REFERENCE_ROOT / "approvals" / REF2_APPROVAL_ID / "approval_manifest.json"
DECISIONS_PATH = PROJECT_ROOT / "docs" / "Decisions.md"

TOP_LEVEL_KEYS = frozenset({
    "activation_flags", "approval_id", "approval_schema_version", "approval_version",
    "approved_modes", "approved_scope", "canonical_serialization", "conversion_policy",
    "counts", "decision_number", "packaging_policy", "prerequisite_approvals",
    "projection_policy", "purpose_policy", "rollback_policy", "rule_policy",
    "runtime_package", "unit_alias_policy", "unit_policy", "write_execution_policy",
})
PURPOSE_ALLOWLIST = (
    "admin_conversion_metadata_read",
    "admin_extended_rule_read",
    "admin_packaging_read",
    "admin_unit_dictionary_read",
    "internal_diagnostics",
)
PURPOSE_DENYLIST = (
    "analyzer_business_processing",
    "catalog_product_write",
    "dashboard",
    "existing_material_details",
    "existing_materials_table",
    "matching_candidate",
    "material_write",
    "moderation_approval",
    "module2_execution",
    "module5_execution",
    "normalizer_output",
    "readiness_export",
    "widgets",
    "work_cost",
)
EXPECTED_COUNTS = {
    "conversions_executable": 0,
    "conversions_formula": 7,
    "conversions_simple": 12,
    "conversions_technical": 28,
    "conversions_total": 47,
    "legacy_exact_units_eligible": 14,
    "legacy_exact_units_source": 16,
    "object_scope_calculations": 0,
    "packaging_affected_material_types": 316,
    "packaging_assignments_eligible": 633,
    "packaging_assignments_review_excluded": 51,
    "packaging_assignments_total": 978,
    "packaging_mismatches": 345,
    "packaging_profiles": 21,
    "packaging_review_mismatch_overlap": 22,
    "ref3_units_eligible": 73,
    "ref3_units_review_excluded": 17,
    "ref3_units_total": 90,
    "rules_consumption": 5,
    "rules_coverage": 2,
    "rules_executable": 0,
    "rules_geometry": 7,
    "rules_pure_conversion_candidates": 6,
    "rules_requires_module2_parameters": 7,
    "rules_review_only": 2,
    "rules_total": 15,
    "rules_yield": 1,
    "runtime_units": 16,
    "work_material_mappings": 0,
    "work_scope_calculations": 0,
}


@dataclass(frozen=True)
class Ref3ApprovalValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class Ref3ApprovalValidationResult:
    is_valid: bool
    approval_sha256: str | None
    issues: tuple[Ref3ApprovalValidationIssue, ...]


def build_expected_ref3_read_approval(
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
    overlap = _packaging_review_mismatch_overlap(package)
    if overlap != EXPECTED_COUNTS["packaging_review_mismatch_overlap"]:
        raise ValueError(f"Unexpected packaging review/mismatch overlap: {overlap}")

    return {
        "activation_flags": {
            "conversion_execution_allowed": False,
            "module2_execution_allowed": False,
            "module5_execution_allowed": False,
            "packaging_write_allowed": False,
            "rule_execution_allowed": False,
            "runtime_activation_allowed": True,
            "write_activation_allowed": False,
        },
        "approval_id": APPROVAL_ID,
        "approval_schema_version": APPROVAL_SCHEMA_VERSION,
        "approval_version": APPROVAL_VERSION,
        "approved_modes": ["ref3_read"],
        "approved_scope": "module1_ref3_read_only_admin_projections",
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
        "conversion_policy": {
            "formula_conversion_execution_allowed": False,
            "formula_conversions": "metadata_only",
            "legacy_conversion_executor_source_of_truth": True,
            "ref_conversion_execution_allowed": False,
            "simple_conversions": "admin_metadata_only",
            "technical_conversions": "parameters_required_metadata_only",
            "technical_execution_without_parameters_allowed": False,
        },
        "counts": {**EXPECTED_COUNTS, "packaging_review_mismatch_overlap": overlap},
        "decision_number": 38,
        "packaging_policy": {
            "automatic_correction_allowed": False,
            "eligible_assignments_visible_for_admin_read": True,
            "mismatch_policy": "diagnostics_only",
            "package_quantity_is_characteristic": False,
            "packaging_write_allowed": False,
            "price_basis_is_characteristic": False,
            "ref2_field_injection_allowed": False,
            "review_excluded_interpretation": "packaging_review_excluded",
            "review_excluded_visible_as_approved": False,
        },
        "prerequisite_approvals": [
            {
                "approval_id": REF1_APPROVAL_ID,
                "approval_sha256": REF1_APPROVAL_SHA256,
                "required_mode": "ref1_read",
            },
            {
                "approval_id": REF2_APPROVAL_ID,
                "approval_sha256": REF2_APPROVAL_SHA256,
                "required_mode": "ref2_read",
            },
        ],
        "projection_policy": {
            "cache_bounded": True,
            "cache_invalidation": "restart_or_package_approval_change",
            "cache_key_components": ["runtime_package_id", "ref3_approval_id", "purpose"],
            "existing_public_registries_extended": False,
            "lazy_load": True,
            "projection_names": ["units_and_conversions", "packaging", "extended_rules"],
            "projection_scope": "private_internal",
            "second_public_registry_allowed": False,
            "startup_behavior": "validate_package_and_approvals_only",
        },
        "purpose_policy": {
            "allow": list(PURPOSE_ALLOWLIST),
            "deny": list(PURPOSE_DENYLIST),
            "purpose_source": "server_owned",
            "unknown_purpose": "deny",
        },
        "rollback_policy": {
            "allowed_target_modes": ["ref2_read"],
            "artifact_deletion_required": False,
            "database_migration_required": False,
            "database_update_required": False,
            "existing_records_reclassification_required": False,
            "legacy_registry_update_required": False,
            "requires_restart": True,
            "stale_ref3_code_behavior": "ignore_as_unknown",
        },
        "rule_policy": {
            "formula_strings_executable": False,
            "module2_execution_allowed": False,
            "object_scope_calculation_allowed": False,
            "ref6_mapping_required_for_work_execution": True,
            "rule_execution_allowed": False,
            "rule_visibility": "admin_metadata_only",
            "work_scope_calculation_allowed": False,
        },
        "runtime_package": {
            "artifact_hashes": {
                "compatibility": str(artifacts["compatibility.json"]["sha256"]),
                "conversions": str(artifacts["conversions.json"]["sha256"]),
                "packaging": str(artifacts["packaging.json"]["sha256"]),
                "rules": str(artifacts["rules_metadata.json"]["sha256"]),
                "units": str(artifacts["units.json"]["sha256"]),
            },
            "artifact_schema_version": str(manifest["artifact_schema_version"]),
            "compatibility_map_version": str(manifest["compatibility_map_version"]),
            "manifest_sha256": _sha256_file(manifest_path),
            "package_id": str(manifest["artifact_set_id"]),
            "source_hashes": dict(sorted(source_hashes.items())),
        },
        "unit_alias_policy": {
            "automatic_legacy_lm_mapping_allowed": False,
            "canonical_lm_meaning": "lumen",
            "canonical_output_for_linear_meter": "linear_meter",
            "legacy_lm_to_linear_meter": "context_required",
            "linear_meter_canonical_code": "linear_meter",
            "review_excluded_codes": ["linear_meter", "m2_mm"],
        },
        "unit_policy": {
            "eligible_units_visible_for_admin_read": True,
            "existing_runtime_registry_extended": False,
            "existing_runtime_registry_replaced": False,
            "legacy_unit_execution_source_of_truth": True,
            "ref_only_unit_write_allowed": False,
            "review_excluded_interpretation": "unit_review_excluded",
            "review_excluded_units_visible_as_approved": False,
        },
        "write_execution_policy": {
            "catalog_product_write_for_ref3_only_metadata": False,
            "legacy_behavior_unchanged": True,
            "matching_for_ref3_only_metadata": False,
            "material_write_for_ref3_only_metadata": False,
            "moderation_for_ref3_only_metadata": False,
            "module2_execution": False,
            "module5_execution": False,
            "normalizer_output_for_ref3_only_metadata": False,
            "readiness_export_for_ref3_only_metadata": False,
            "work_cost_usage": False,
        },
    }


def serialize_ref3_read_approval(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_expected_ref3_read_approval(
    output_path: Path | str,
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_ref3_read_approval(build_expected_ref3_read_approval(runtime_package_dir)))
    return target


def validate_ref3_read_approval(
    approval_path: Path | str = APPROVAL_PATH,
    runtime_package_dir: Path | str = RUNTIME_PACKAGE_DIR,
    ref1_approval_path: Path | str = REF1_APPROVAL_PATH,
    ref2_approval_path: Path | str = REF2_APPROVAL_PATH,
    decisions_path: Path | str = DECISIONS_PATH,
    reference_root: Path | str = REFERENCE_ROOT,
) -> Ref3ApprovalValidationResult:
    path = Path(approval_path)
    package = Path(runtime_package_dir)
    issues: list[Ref3ApprovalValidationIssue] = []
    try:
        payload = _read_json(path)
        expected = build_expected_ref3_read_approval(package)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return Ref3ApprovalValidationResult(
            False, None, (Ref3ApprovalValidationIssue("APPROVAL_LOAD_FAILED", str(exc)),)
        )

    keys = set(payload)
    if TOP_LEVEL_KEYS - keys:
        issues.append(Ref3ApprovalValidationIssue("TOP_LEVEL_KEYS_MISSING", ", ".join(sorted(TOP_LEVEL_KEYS - keys))))
    if keys - TOP_LEVEL_KEYS:
        issues.append(Ref3ApprovalValidationIssue("TOP_LEVEL_KEYS_EXTRA", ", ".join(sorted(keys - TOP_LEVEL_KEYS))))

    checks = (
        (payload.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (payload.get("approval_schema_version") == "1.0", "SCHEMA_VERSION_INVALID"),
        (payload.get("approval_version") == "1.0", "APPROVAL_VERSION_INVALID"),
        (payload.get("decision_number") == 38, "DECISION_INVALID"),
        (payload.get("approved_modes") == ["ref3_read"], "APPROVED_MODES_INVALID"),
        (payload.get("approved_scope") == expected["approved_scope"], "APPROVED_SCOPE_INVALID"),
        (payload.get("prerequisite_approvals") == expected["prerequisite_approvals"], "PREREQUISITE_CONTRACT_INVALID"),
        (payload.get("runtime_package") == expected["runtime_package"], "RUNTIME_PACKAGE_INVALID"),
        (payload.get("counts") == expected["counts"], "COUNTS_INVALID"),
        (payload.get("purpose_policy") == expected["purpose_policy"], "PURPOSE_POLICY_INVALID"),
        (payload.get("projection_policy") == expected["projection_policy"], "PROJECTION_POLICY_INVALID"),
        (payload.get("unit_alias_policy") == expected["unit_alias_policy"], "UNIT_ALIAS_POLICY_INVALID"),
        (payload.get("unit_policy") == expected["unit_policy"], "UNIT_POLICY_INVALID"),
        (payload.get("conversion_policy") == expected["conversion_policy"], "CONVERSION_POLICY_INVALID"),
        (payload.get("packaging_policy") == expected["packaging_policy"], "PACKAGING_POLICY_INVALID"),
        (payload.get("rule_policy") == expected["rule_policy"], "RULE_POLICY_INVALID"),
        (payload.get("write_execution_policy") == expected["write_execution_policy"], "WRITE_EXECUTION_POLICY_INVALID"),
        (payload.get("rollback_policy") == expected["rollback_policy"], "ROLLBACK_POLICY_INVALID"),
        (payload.get("activation_flags") == expected["activation_flags"], "ACTIVATION_FLAGS_INVALID"),
        (payload.get("canonical_serialization") == expected["canonical_serialization"], "SERIALIZATION_POLICY_INVALID"),
        (payload == expected, "APPROVAL_PAYLOAD_NOT_CANONICAL"),
        (path.read_bytes() == serialize_ref3_read_approval(expected), "APPROVAL_BYTES_NOT_DETERMINISTIC"),
    )
    for passed, code in checks:
        if not passed:
            issues.append(Ref3ApprovalValidationIssue(code, code.replace("_", " ").title()))

    expected_suffix = Path("approvals") / APPROVAL_ID / "approval_manifest.json"
    if Path(*path.parts[-3:]) != expected_suffix:
        issues.append(Ref3ApprovalValidationIssue("APPROVAL_PATH_INVALID", str(path)))
    if APPROVAL_ID != f"ref3-read-v1-{expected['runtime_package']['manifest_sha256'][:12]}":
        issues.append(Ref3ApprovalValidationIssue("APPROVAL_ID_DERIVATION_INVALID", APPROVAL_ID))

    issues.extend(_validate_decision(Path(decisions_path)))
    issues.extend(_validate_prerequisite(Path(ref1_approval_path), REF1_APPROVAL_ID, REF1_APPROVAL_SHA256, "ref1_read"))
    issues.extend(_validate_prerequisite(Path(ref2_approval_path), REF2_APPROVAL_ID, REF2_APPROVAL_SHA256, "ref2_read"))
    issues.extend(_validate_runtime_package(package, Path(reference_root)))
    return Ref3ApprovalValidationResult(not issues, _sha256_file(path), tuple(issues))


def _packaging_review_mismatch_overlap(package: Path) -> int:
    compatibility = _read_json(package / "compatibility.json")
    review_ids = set(compatibility["review_exclusions"]["ref3_packaging_material_types"])
    mismatch_ids = {
        str(item["material_type_id"])
        for item in compatibility["diagnostics"]["packaging_ref2_mismatches"]
    }
    return len(review_ids & mismatch_ids)


def _validate_decision(path: Path) -> list[Ref3ApprovalValidationIssue]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [Ref3ApprovalValidationIssue("DECISION_LOAD_FAILED", str(exc))]
    if text.count("## Решение №038") != 1:
        return [Ref3ApprovalValidationIssue("DECISION_038_MISSING", str(path))]
    if "Статус:\nПринято." not in text.split("## Решение №038", 1)[1]:
        return [Ref3ApprovalValidationIssue("DECISION_038_NOT_ACCEPTED", str(path))]
    return []


def _validate_prerequisite(
    path: Path,
    approval_id: str,
    expected_hash: str,
    required_mode: str,
) -> list[Ref3ApprovalValidationIssue]:
    prefix = required_mode.upper()
    if not path.is_file():
        return [Ref3ApprovalValidationIssue(f"{prefix}_APPROVAL_MISSING", str(path))]
    issues: list[Ref3ApprovalValidationIssue] = []
    if _sha256_file(path) != expected_hash:
        issues.append(Ref3ApprovalValidationIssue(f"{prefix}_APPROVAL_HASH_INVALID", str(path)))
    try:
        payload = _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return issues + [Ref3ApprovalValidationIssue(f"{prefix}_APPROVAL_LOAD_FAILED", str(exc))]
    if payload.get("approval_id") != approval_id:
        issues.append(Ref3ApprovalValidationIssue(f"{prefix}_APPROVAL_ID_INVALID", str(path)))
    if payload.get("approved_modes") != [required_mode]:
        issues.append(Ref3ApprovalValidationIssue(f"{prefix}_APPROVAL_MODE_INVALID", str(path)))
    return issues


def _validate_runtime_package(package: Path, reference_root: Path) -> list[Ref3ApprovalValidationIssue]:
    issues: list[Ref3ApprovalValidationIssue] = []
    manifest_path = package / "manifest.json"
    try:
        manifest = _read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [Ref3ApprovalValidationIssue("RUNTIME_MANIFEST_LOAD_FAILED", str(exc))]
    if _sha256_file(manifest_path) != RUNTIME_MANIFEST_SHA256:
        issues.append(Ref3ApprovalValidationIssue("RUNTIME_MANIFEST_HASH_INVALID", str(manifest_path)))
    if manifest.get("artifact_set_id") != RUNTIME_PACKAGE_ID or package.name != RUNTIME_PACKAGE_ID:
        issues.append(Ref3ApprovalValidationIssue("RUNTIME_PACKAGE_ID_INVALID", str(package)))
    for name, contract in manifest.get("artifacts", {}).items():
        artifact = package / name
        if (
            not artifact.is_file()
            or _sha256_file(artifact) != contract.get("sha256")
            or artifact.stat().st_size != contract.get("size_bytes")
        ):
            issues.append(Ref3ApprovalValidationIssue("RUNTIME_ARTIFACT_CHANGED", name))
    for source in manifest.get("source_packages", []):
        source_path = reference_root / str(source.get("filename"))
        if not source_path.is_file() or _sha256_file(source_path) != source.get("sha256"):
            issues.append(Ref3ApprovalValidationIssue("SOURCE_PACKAGE_CHANGED", str(source_path)))
    try:
        if _packaging_review_mismatch_overlap(package) != 22:
            issues.append(Ref3ApprovalValidationIssue("PACKAGING_OVERLAP_INVALID", str(package)))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        issues.append(Ref3ApprovalValidationIssue("PACKAGING_OVERLAP_UNAVAILABLE", str(exc)))
    return issues


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
