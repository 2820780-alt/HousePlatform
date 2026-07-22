from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_ref_artifact_portability import portable_identity_or_raw

from app.services.module1_material_seed_registry import MaterialKnowledgeSeedRegistry
from app.services.module1_ref2_read_policy import (
    APPROVAL_ID as REF2_APPROVAL_ID,
    EXPECTED_APPROVAL_SHA256 as REF2_APPROVAL_SHA256,
    Module1Ref2ReadActivation,
    activate_module1_ref2_read,
)
from app.services.module1_ref3_read_projection import Ref3ProjectionCache
from app.services.module1_unit_conversion_registry import list_units


APPROVAL_ID = "ref3-read-v1-1a15fed6ebdd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
EXPECTED_APPROVAL_SHA256 = "429468eda2569c7366504e10f95ad84ea96d17878b5bb1b3a09fcf8e12e97bab"
APPROVED_PURPOSES = (
    "admin_conversion_metadata_read",
    "admin_extended_rule_read",
    "admin_packaging_read",
    "admin_unit_dictionary_read",
    "internal_diagnostics",
)
DENIED_PURPOSES = (
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
TOP_LEVEL_KEYS = frozenset(
    {
        "activation_flags",
        "approval_id",
        "approval_schema_version",
        "approval_version",
        "approved_modes",
        "approved_scope",
        "canonical_serialization",
        "conversion_policy",
        "counts",
        "decision_number",
        "packaging_policy",
        "prerequisite_approvals",
        "projection_policy",
        "purpose_policy",
        "rollback_policy",
        "rule_policy",
        "runtime_package",
        "unit_alias_policy",
        "unit_policy",
        "write_execution_policy",
    }
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
class Module1Ref3ReadIssue:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class Module1Ref3PurposePolicy:
    def purpose_allowed(self, purpose: str) -> bool:
        return purpose in APPROVED_PURPOSES


@dataclass(frozen=True)
class Module1Ref3ReadActivation(Module1Ref2ReadActivation):
    ref3_approval_validated: bool
    ref3_approval_id: str | None
    ref3_approval_sha256: str | None
    ref3_counts: Mapping[str, int]
    ref3_policy: Module1Ref3PurposePolicy | None
    projection_cache: Ref3ProjectionCache | None
    ref3_approval_validation_duration_ms: float
    ref3_startup_overhead_ms: float
    startup_ref3_projection_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = super().as_dict()
        payload.update(
            {
                "allowlist_purposes": list(APPROVED_PURPOSES),
                "cache_entry_count": (
                    self.projection_cache.cache_entry_count
                    if self.projection_cache is not None
                    else 0
                ),
                "mode": self.mode,
                "ref3_approval_id": self.ref3_approval_id,
                "ref3_approval_validated": self.ref3_approval_validated,
                "ref3_counts": dict(self.ref3_counts),
                "startup_ref3_projection_count": self.startup_ref3_projection_count,
            }
        )
        return payload

def activate_module1_ref3_read(
    *,
    artifact_dir: Path,
    ref1_approval_dir: Path,
    ref2_approval_dir: Path,
    ref3_approval_dir: Path,
    approval_allowed_root: Path,
    package_validation: Any,
    registry: MaterialKnowledgeSeedRegistry,
) -> Module1Ref3ReadActivation:
    started = time.perf_counter()
    issues: list[Module1Ref3ReadIssue] = []
    registry_before = _registry_snapshot(registry)
    legacy_units_before = tuple(list_units())

    ref2_started = time.perf_counter()
    ref2_activation = activate_module1_ref2_read(
        artifact_dir=artifact_dir,
        ref1_approval_dir=ref1_approval_dir,
        ref2_approval_dir=ref2_approval_dir,
        approval_allowed_root=approval_allowed_root,
        package_validation=package_validation,
        registry=registry,
    )
    ref2_duration_ms = (time.perf_counter() - ref2_started) * 1000
    if not ref2_activation.is_valid:
        issues.extend(
            Module1Ref3ReadIssue(f"REF2_{issue.code}", issue.message)
            for issue in ref2_activation.issues
        )

    approval_started = time.perf_counter()
    approval_payload: dict[str, Any] = {}
    approval_sha256: str | None = None
    try:
        confined_approval = _confined_approval_dir(
            ref3_approval_dir,
            approval_allowed_root,
        )
    except ValueError as exc:
        issues.append(Module1Ref3ReadIssue("APPROVAL_PATH_INVALID", str(exc)))
        confined_approval = ref3_approval_dir
    approval_path = confined_approval / "approval_manifest.json"
    approval_bytes = b""
    if not approval_path.is_file():
        issues.append(
            Module1Ref3ReadIssue(
                "APPROVAL_MISSING",
                "REF-3 read approval is missing",
            )
        )
    else:
        approval_bytes = approval_path.read_bytes()
        approval_sha256 = portable_identity_or_raw(approval_path)
        if approval_sha256 != EXPECTED_APPROVAL_SHA256:
            issues.append(
                Module1Ref3ReadIssue(
                    "APPROVAL_HASH_INVALID",
                    "REF-3 read approval hash is invalid",
                )
            )
        approval_payload = _read_json(
            approval_path,
            "APPROVAL_INVALID_JSON",
            issues,
        )

    manifest_path = artifact_dir / "manifest.json"
    manifest_payload = _read_json(
        manifest_path,
        "MANIFEST_RELOAD_FAILED",
        issues,
    )
    manifest_sha256 = _sha256_file_or_none(manifest_path)
    if package_validation.manifest_sha256 != manifest_sha256:
        issues.append(
            Module1Ref3ReadIssue(
                "RUNTIME_MANIFEST_CHANGED",
                "Runtime manifest changed after package validation",
            )
        )
    if approval_payload and manifest_payload:
        _validate_approval_contract(
            approval_payload,
            approval_bytes,
            manifest_payload,
            manifest_sha256,
            package_validation,
            ref2_activation,
            issues,
        )
    approval_duration_ms = (time.perf_counter() - approval_started) * 1000

    registry_mutated = (
        ref2_activation.registry_mutated
        or registry_before != _registry_snapshot(registry)
        or legacy_units_before != tuple(list_units())
    )
    if registry_mutated:
        issues.append(
            Module1Ref3ReadIssue(
                "PUBLIC_REGISTRY_MUTATION_DETECTED",
                "REF-3 read activation changed a legacy public registry",
            )
        )

    projection_cache: Ref3ProjectionCache | None = None
    is_valid = not issues and ref2_activation.is_valid
    if is_valid:
        approval_runtime = approval_payload["runtime_package"]
        artifact_hashes = dict(approval_runtime["artifact_hashes"])
        artifact_hashes["taxonomy"] = str(
            manifest_payload["artifacts"]["taxonomy.json"]["sha256"]
        )
        projection_cache = Ref3ProjectionCache(
            artifact_dir=artifact_dir,
            artifact_hashes=artifact_hashes,
            runtime_package_id=str(package_validation.artifact_set_id),
            ref1_approval_id=str(ref2_activation.ref1_approval_id),
            ref2_approval_id=str(ref2_activation.ref2_approval_id),
            ref3_approval_id=APPROVAL_ID,
            ref3_approval_version=APPROVAL_VERSION,
            legacy_unit_codes=legacy_units_before,
        )
    total_duration_ms = (time.perf_counter() - started) * 1000

    return Module1Ref3ReadActivation(
        mode="ref3_read",
        status="PASS" if is_valid else "BLOCKED",
        is_valid=is_valid,
        package_validated=package_validation.is_valid,
        ref1_approval_validated=(
            ref2_activation.ref1_approval_validated if is_valid else False
        ),
        ref2_approval_validated=(
            ref2_activation.ref2_approval_validated if is_valid else False
        ),
        artifact_set_id=package_validation.artifact_set_id,
        manifest_sha256=package_validation.manifest_sha256,
        ref1_approval_id=ref2_activation.ref1_approval_id,
        ref1_approval_sha256=ref2_activation.ref1_approval_sha256,
        ref2_approval_id=ref2_activation.ref2_approval_id,
        ref2_approval_sha256=ref2_activation.ref2_approval_sha256,
        counts=ref2_activation.counts if is_valid else MappingProxyType({}),
        issues=tuple(issues),
        registry_mutated=registry_mutated,
        database_writes=0,
        preference_writes=0,
        business_reads_enabled=is_valid,
        ref_only_writes_enabled=False,
        loaded_object_count=(
            ref2_activation.loaded_object_count if is_valid else 0
        ),
        validation_duration_ms=package_validation.validation_duration_ms,
        ref1_validation_duration_ms=ref2_activation.ref1_validation_duration_ms,
        ref2_approval_validation_duration_ms=(
            ref2_activation.ref2_approval_validation_duration_ms
        ),
        fields_load_duration_ms=ref2_activation.fields_load_duration_ms,
        assignments_load_duration_ms=ref2_activation.assignments_load_duration_ms,
        projection_load_duration_ms=ref2_activation.projection_load_duration_ms,
        total_duration_ms=total_duration_ms,
        projection_size_bytes=(
            ref2_activation.projection_size_bytes if is_valid else 0
        ),
        ref1_activation=(
            ref2_activation.ref1_activation if is_valid else None
        ),
        projection=ref2_activation.projection if is_valid else None,
        policy=ref2_activation.policy if is_valid else None,
        ref3_approval_validated=is_valid,
        ref3_approval_id=(
            _text(approval_payload.get("approval_id"))
            if approval_payload
            else None
        ),
        ref3_approval_sha256=approval_sha256,
        ref3_counts=(
            MappingProxyType(dict(EXPECTED_COUNTS))
            if is_valid
            else MappingProxyType({})
        ),
        ref3_policy=Module1Ref3PurposePolicy() if is_valid else None,
        projection_cache=projection_cache,
        ref3_approval_validation_duration_ms=approval_duration_ms,
        ref3_startup_overhead_ms=max(
            0.0,
            total_duration_ms - ref2_duration_ms,
        ),
        startup_ref3_projection_count=(
            projection_cache.cache_entry_count
            if projection_cache is not None
            else 0
        ),
    )

def _validate_approval_contract(
    approval: Mapping[str, Any],
    approval_bytes: bytes,
    manifest: Mapping[str, Any],
    manifest_sha256: str | None,
    package_validation: Any,
    ref2_activation: Module1Ref2ReadActivation,
    issues: list[Module1Ref3ReadIssue],
) -> None:
    artifacts = manifest.get("artifacts", {})
    source_hashes = {
        str(item.get("filename")): str(item.get("sha256"))
        for item in manifest.get("source_packages", [])
        if isinstance(item, Mapping)
    }
    expected_runtime = {
        "artifact_hashes": {
            "compatibility": str(
                artifacts.get("compatibility.json", {}).get("sha256")
            ),
            "conversions": str(
                artifacts.get("conversions.json", {}).get("sha256")
            ),
            "packaging": str(
                artifacts.get("packaging.json", {}).get("sha256")
            ),
            "rules": str(
                artifacts.get("rules_metadata.json", {}).get("sha256")
            ),
            "units": str(artifacts.get("units.json", {}).get("sha256")),
        },
        "artifact_schema_version": str(manifest.get("artifact_schema_version")),
        "compatibility_map_version": str(
            manifest.get("compatibility_map_version")
        ),
        "manifest_sha256": manifest_sha256,
        "package_id": str(manifest.get("artifact_set_id")),
        "source_hashes": dict(sorted(source_hashes.items())),
    }
    expected_policies = {
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
        "purpose_policy": {
            "allow": list(APPROVED_PURPOSES),
            "deny": list(DENIED_PURPOSES),
            "purpose_source": "server_owned",
            "unknown_purpose": "deny",
        },
        "projection_policy": {
            "cache_bounded": True,
            "cache_invalidation": "restart_or_package_approval_change",
            "cache_key_components": [
                "runtime_package_id",
                "ref3_approval_id",
                "purpose",
            ],
            "existing_public_registries_extended": False,
            "lazy_load": True,
            "projection_names": [
                "units_and_conversions",
                "packaging",
                "extended_rules",
            ],
            "projection_scope": "private_internal",
            "second_public_registry_allowed": False,
            "startup_behavior": "validate_package_and_approvals_only",
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
        "conversion_policy": {
            "formula_conversion_execution_allowed": False,
            "formula_conversions": "metadata_only",
            "legacy_conversion_executor_source_of_truth": True,
            "ref_conversion_execution_allowed": False,
            "simple_conversions": "admin_metadata_only",
            "technical_conversions": "parameters_required_metadata_only",
            "technical_execution_without_parameters_allowed": False,
        },
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
        "rule_policy": {
            "formula_strings_executable": False,
            "module2_execution_allowed": False,
            "object_scope_calculation_allowed": False,
            "ref6_mapping_required_for_work_execution": True,
            "rule_execution_allowed": False,
            "rule_visibility": "admin_metadata_only",
            "work_scope_calculation_allowed": False,
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
        "activation_flags": {
            "conversion_execution_allowed": False,
            "module2_execution_allowed": False,
            "module5_execution_allowed": False,
            "packaging_write_allowed": False,
            "rule_execution_allowed": False,
            "runtime_activation_allowed": True,
            "write_activation_allowed": False,
        },
    }
    expected_prerequisites = [
        {
            "approval_id": "ref1-read-v1-1a15fed6ebdd",
            "approval_sha256": "55c9f09aa1db034f22108f02a2f2afe692bdf58650ff4d2a8d0d8b70b1799973",
            "required_mode": "ref1_read",
        },
        {
            "approval_id": REF2_APPROVAL_ID,
            "approval_sha256": REF2_APPROVAL_SHA256,
            "required_mode": "ref2_read",
        },
    ]
    checks = (
        (set(approval) == TOP_LEVEL_KEYS, "TOP_LEVEL_KEYS_INVALID"),
        (approval.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (
            approval.get("approval_schema_version") == APPROVAL_SCHEMA_VERSION,
            "APPROVAL_SCHEMA_INVALID",
        ),
        (
            approval.get("approval_version") == APPROVAL_VERSION,
            "APPROVAL_VERSION_INVALID",
        ),
        (approval.get("decision_number") == 38, "APPROVAL_DECISION_INVALID"),
        (approval.get("approved_modes") == ["ref3_read"], "APPROVED_MODES_INVALID"),
        (
            approval.get("approved_scope")
            == "module1_ref3_read_only_admin_projections",
            "APPROVED_SCOPE_INVALID",
        ),
        (
            approval.get("prerequisite_approvals") == expected_prerequisites,
            "PREREQUISITE_CONTRACT_INVALID",
        ),
        (approval.get("runtime_package") == expected_runtime, "RUNTIME_PACKAGE_INVALID"),
        (approval.get("counts") == EXPECTED_COUNTS, "COUNTS_INVALID"),
        (
            approval.get("canonical_serialization")
            == expected_policies["canonical_serialization"],
            "SERIALIZATION_POLICY_INVALID",
        ),
        (
            approval.get("purpose_policy") == expected_policies["purpose_policy"],
            "PURPOSE_POLICY_INVALID",
        ),
        (
            approval.get("projection_policy")
            == expected_policies["projection_policy"],
            "PROJECTION_POLICY_INVALID",
        ),
        (
            approval.get("unit_alias_policy")
            == expected_policies["unit_alias_policy"],
            "UNIT_ALIAS_POLICY_INVALID",
        ),
        (
            approval.get("unit_policy") == expected_policies["unit_policy"],
            "UNIT_POLICY_INVALID",
        ),
        (
            approval.get("conversion_policy")
            == expected_policies["conversion_policy"],
            "CONVERSION_POLICY_INVALID",
        ),
        (
            approval.get("packaging_policy")
            == expected_policies["packaging_policy"],
            "PACKAGING_POLICY_INVALID",
        ),
        (
            approval.get("rule_policy") == expected_policies["rule_policy"],
            "RULE_POLICY_INVALID",
        ),
        (
            approval.get("write_execution_policy")
            == expected_policies["write_execution_policy"],
            "WRITE_EXECUTION_POLICY_INVALID",
        ),
        (
            approval.get("rollback_policy")
            == expected_policies["rollback_policy"],
            "ROLLBACK_POLICY_INVALID",
        ),
        (
            approval.get("activation_flags")
            == expected_policies["activation_flags"],
            "ACTIVATION_FLAGS_INVALID",
        ),
        (
            ref2_activation.ref1_approval_validated,
            "REF1_PREREQUISITE_INVALID",
        ),
        (
            ref2_activation.ref2_approval_validated
            and ref2_activation.ref2_approval_id == REF2_APPROVAL_ID
            and ref2_activation.ref2_approval_sha256 == REF2_APPROVAL_SHA256,
            "REF2_PREREQUISITE_INVALID",
        ),
        (
            package_validation.is_valid
            and package_validation.artifact_set_id
            == expected_runtime["package_id"]
            and package_validation.manifest_sha256
            == expected_runtime["manifest_sha256"],
            "PACKAGE_VALIDATION_INVALID",
        ),

    )
    for passed, code in checks:
        if not passed:
            issues.append(
                Module1Ref3ReadIssue(
                    code,
                    code.replace("_", " ").title(),
                )
            )

def _confined_approval_dir(path: Path, allowed_root: Path) -> Path:
    root = allowed_root.resolve()
    target = path.resolve()
    if target.parent != root or target.name != APPROVAL_ID:
        raise ValueError("REF-3 approval directory is outside the approved root")
    return target


def _registry_snapshot(registry: MaterialKnowledgeSeedRegistry) -> tuple[Any, ...]:
    return (
        registry.version,
        registry.module,
        tuple(
            (group.code, group.name, group.children)
            for group in registry.taxonomy
        ),
        tuple(
            (
                code,
                schema.required,
                schema.module2_required,
                schema.recommended,
            )
            for code, schema in sorted(
                registry.characteristic_schemas.items()
            )
        ),
        tuple(sorted(registry.role_mappings.items())),
    )


def _read_json(
    path: Path,
    code: str,
    issues: list[Module1Ref3ReadIssue],
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Module1Ref3ReadIssue(code, str(exc)))
        return {}
    if not isinstance(payload, dict):
        issues.append(Module1Ref3ReadIssue(code, f"Expected JSON object: {path.name}"))
        return {}
    return payload


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_file_or_none(path: Path) -> str | None:
    if not path.is_file():
        return None
    return portable_identity_or_raw(path)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
