from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_material_seed_registry import MaterialKnowledgeSeedRegistry
from app.services.module1_ref1_read_policy import (
    APPROVAL_ID as REF1_APPROVAL_ID,
    EXPECTED_APPROVAL_SHA256 as REF1_APPROVAL_SHA256,
    Module1Ref1ReadActivation,
    activate_module1_ref1_read,
)


APPROVAL_ID = "ref2-read-v1-1a15fed6ebdd"
APPROVAL_VERSION = "1.0"
APPROVAL_SCHEMA_VERSION = "1.0"
EXPECTED_APPROVAL_SHA256 = "e5e13fba61a3aef4e94b27e22394f41d2ebbeb0b948e5f899742342e19d50e06"
APPROVED_PURPOSES = ("admin_characteristic_schema_read", "internal_diagnostics")
DENIED_PURPOSES = (
    "analyzer_business_processing",
    "catalog_product_write",
    "dashboard",
    "documents_business_processing",
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
TOP_LEVEL_KEYS = frozenset(
    {
        "activation_flags",
        "approval_id",
        "approval_schema_version",
        "approval_version",
        "approved_modes",
        "approved_scope",
        "assignment_policy",
        "canonical_serialization",
        "counts",
        "decision_number",
        "overlap_compatibility_policy",
        "packaging_boundary_policy",
        "prerequisite_approvals",
        "purpose_policy",
        "read_policy",
        "required_semantics_policy",
        "rollback_policy",
        "runtime_only_fields_policy",
        "runtime_package",
        "write_policy",
    }
)

READ_COMPATIBLE_FIELDS = frozenset(
    {
        "board_type",
        "compatible_substrates",
        "consumption_kg_m2_mm",
        "consumption_l_m2",
        "coverage_area_per_pack_m2",
        "density_class",
        "edge_type",
        "height_mm",
        "max_layer_mm",
        "metal_thickness_mm",
        "min_layer_mm",
        "min_roof_slope_deg",
        "pieces_per_m3",
        "pieces_per_pallet",
        "primer_type",
        "rectified",
        "sheet_area_m2",
        "strength_class",
        "underlayment_required",
        "weight_per_piece_kg",
        "wet_room_allowed",
    }
)
REQUIRED_SEMANTICS_MISMATCH_FIELDS = frozenset(
    {
        "end_overlap_mm",
        "fastening_pattern_code",
        "frost_resistant",
        "mastic_required_zones",
        "side_overlap_mm",
        "wave_step_mm",
    }
)
REVIEW_REQUIRED_FIELDS = frozenset(
    {
        "cable_type",
        "concrete_class",
        "conductor_material",
        "cores_count",
        "cross_section_mm2",
        "density_kg_m3",
        "diameter_mm",
        "insulation_type",
        "length_mm",
        "min_order_m3",
        "mobility_class",
        "moisture_percent",
        "profile_type",
        "standard_bar_length_m",
        "steel_class",
        "thickness_mm",
        "volume_per_piece_m3",
        "width_mm",
        "wood_species",
    }
)


@dataclass(frozen=True)
class Module1Ref2ReadIssue:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class Ref2ProjectedField:
    field_code: str
    field_title: str
    value_type: str
    unit_code: str | None
    ref_source_required: bool
    legacy_effective_required: bool
    compatibility_status: str
    warning_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "compatibility_status": self.compatibility_status,
            "eligible_for_catalog_product_write": False,
            "eligible_for_matching": False,
            "eligible_for_material_write": False,
            "eligible_for_moderation": False,
            "eligible_for_normalizer_output": False,
            "field_code": self.field_code,
            "field_title": self.field_title,
            "legacy_effective_required": self.legacy_effective_required,
            "read_only": True,
            "ref_source_required": self.ref_source_required,
            "unit_code": self.unit_code,
            "value_type": self.value_type,
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class Ref2ProjectedSchema:
    material_type_code: str
    material_type_title: str
    canonical_group_code: str
    canonical_group_title: str
    schema_status: str
    source_profile_id: str | None
    fields: tuple[Ref2ProjectedField, ...]
    warning_codes: tuple[str, ...]
    packaging_boundary_warnings: tuple[str, ...]
    legacy_schema_present: bool
    field_availability: str
    runtime_package_id: str
    ref1_approval_id: str
    ref1_approval_version: str
    ref2_approval_id: str
    ref2_approval_version: str

    @property
    def approved_field_count(self) -> int:
        return len(self.fields)

    @property
    def warning_count(self) -> int:
        return len(self.warning_codes) + sum(len(field.warning_codes) for field in self.fields)

    def as_summary(self) -> dict[str, Any]:
        return {
            "approved_field_count": self.approved_field_count,
            "eligible_for_catalog_product_write": False,
            "eligible_for_material_write": False,
            "legacy_schema_present": self.legacy_schema_present,
            "material_type_code": self.material_type_code,
            "material_type_title": self.material_type_title,
            "read_only": True,
            "ref1_approval_id": self.ref1_approval_id,
            "ref1_approval_version": self.ref1_approval_version,
            "ref2_approval_id": self.ref2_approval_id,
            "ref2_approval_version": self.ref2_approval_version,
            "runtime_package_id": self.runtime_package_id,
            "schema_status": self.schema_status,
            "warning_count": self.warning_count,
        }

    def as_detail(self) -> dict[str, Any]:
        compatibility_counts = Counter(field.compatibility_status for field in self.fields)
        return {
            **self.as_summary(),
            "canonical_group": {
                "code": self.canonical_group_code,
                "title": self.canonical_group_title,
            },
            "canonical_path": [self.canonical_group_code, self.material_type_code],
            "compatibility_summary": dict(sorted(compatibility_counts.items())),
            "field_availability": self.field_availability,
            "fields": [field.as_dict() for field in self.fields],
            "packaging_boundary_warnings": list(self.packaging_boundary_warnings),
            "source_profile": {
                "flattened": True,
                "profile_id": self.source_profile_id,
            },
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class Ref2ReadProjection:
    schemas: tuple[Ref2ProjectedSchema, ...]
    schema_by_code: Mapping[str, Ref2ProjectedSchema]
    counts: Mapping[str, int]
    compatibility_summary: Mapping[str, int]

    def page(self, *, offset: int, limit: int) -> tuple[Ref2ProjectedSchema, ...]:
        return self.schemas[offset : offset + limit]

    def get(self, material_type_code: str) -> Ref2ProjectedSchema | None:
        return self.schema_by_code.get(str(material_type_code or "").strip())


@dataclass(frozen=True)
class Module1Ref2PurposePolicy:
    def purpose_allowed(self, purpose: str) -> bool:
        return purpose in APPROVED_PURPOSES


@dataclass(frozen=True)
class Module1Ref2ReadActivation:
    mode: str
    status: str
    is_valid: bool
    package_validated: bool
    ref1_approval_validated: bool
    ref2_approval_validated: bool
    artifact_set_id: str | None
    manifest_sha256: str | None
    ref1_approval_id: str | None
    ref1_approval_sha256: str | None
    ref2_approval_id: str | None
    ref2_approval_sha256: str | None
    counts: Mapping[str, int]
    issues: tuple[Module1Ref2ReadIssue, ...]
    registry_mutated: bool
    database_writes: int
    preference_writes: int
    business_reads_enabled: bool
    ref_only_writes_enabled: bool
    loaded_object_count: int
    validation_duration_ms: float
    ref1_validation_duration_ms: float
    ref2_approval_validation_duration_ms: float
    fields_load_duration_ms: float
    assignments_load_duration_ms: float
    projection_load_duration_ms: float
    total_duration_ms: float
    projection_size_bytes: int
    ref1_activation: Module1Ref1ReadActivation | None
    projection: Ref2ReadProjection | None
    policy: Module1Ref2PurposePolicy | None

    @property
    def success(self) -> bool:
        return self.is_valid

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowlist_purposes": list(APPROVED_PURPOSES),
            "artifact_set_id": self.artifact_set_id,
            "business_reads_enabled": self.business_reads_enabled,
            "counts": dict(self.counts),
            "database_writes": self.database_writes,
            "is_valid": self.is_valid,
            "issues": [issue.as_dict() for issue in self.issues],
            "loaded_object_count": self.loaded_object_count,
            "manifest_sha256": self.manifest_sha256,
            "mode": self.mode,
            "package_validated": self.package_validated,
            "preference_writes": self.preference_writes,
            "ref1_approval_id": self.ref1_approval_id,
            "ref1_approval_validated": self.ref1_approval_validated,
            "ref2_approval_id": self.ref2_approval_id,
            "ref2_approval_validated": self.ref2_approval_validated,
            "ref_only_writes_enabled": self.ref_only_writes_enabled,
            "registry_mutated": self.registry_mutated,
            "status": self.status,
            "validation_duration_ms": self.validation_duration_ms,
        }


def activate_module1_ref2_read(
    *,
    artifact_dir: Path,
    ref1_approval_dir: Path,
    ref2_approval_dir: Path,
    approval_allowed_root: Path,
    package_validation: Any,
    registry: MaterialKnowledgeSeedRegistry,
) -> Module1Ref2ReadActivation:
    started = time.perf_counter()
    issues: list[Module1Ref2ReadIssue] = []
    registry_before = _registry_snapshot(registry)

    ref1_started = time.perf_counter()
    ref1_activation = activate_module1_ref1_read(
        artifact_dir=artifact_dir,
        approval_dir=ref1_approval_dir,
        approval_allowed_root=approval_allowed_root,
        package_validation=package_validation,
        registry=registry,
    )
    ref1_duration_ms = (time.perf_counter() - ref1_started) * 1000
    if not ref1_activation.is_valid:
        issues.extend(
            Module1Ref2ReadIssue(f"REF1_{issue.code}", issue.message)
            for issue in ref1_activation.issues
        )

    approval_started = time.perf_counter()
    approval_payload: dict[str, Any] = {}
    approval_sha256: str | None = None
    manifest_payload: dict[str, Any] = {}
    try:
        confined_approval = _confined_approval_dir(
            ref2_approval_dir,
            approval_allowed_root,
            APPROVAL_ID,
        )
    except ValueError as exc:
        issues.append(Module1Ref2ReadIssue("APPROVAL_PATH_INVALID", str(exc)))
        confined_approval = ref2_approval_dir

    approval_path = confined_approval / "approval_manifest.json"
    if not approval_path.is_file():
        issues.append(Module1Ref2ReadIssue("APPROVAL_MISSING", "REF-2 read approval is missing"))
    else:
        approval_sha256 = _sha256_file(approval_path)
        if approval_sha256 != EXPECTED_APPROVAL_SHA256:
            issues.append(Module1Ref2ReadIssue("APPROVAL_HASH_INVALID", "REF-2 read approval hash is invalid"))
        approval_payload = _read_json(approval_path, "APPROVAL_INVALID_JSON", issues)

    manifest_path = artifact_dir / "manifest.json"
    manifest_payload = _read_json(manifest_path, "MANIFEST_RELOAD_FAILED", issues)
    if package_validation.manifest_sha256 != _sha256_file_or_none(manifest_path):
        issues.append(Module1Ref2ReadIssue("RUNTIME_MANIFEST_CHANGED", "Runtime manifest changed after package validation"))
    if approval_payload and manifest_payload:
        _validate_approval_contract(
            approval_payload,
            manifest_payload,
            package_validation,
            ref1_activation,
            issues,
        )
    approval_duration_ms = (time.perf_counter() - approval_started) * 1000

    fields_started = time.perf_counter()
    fields_payload: dict[str, Any] = {}
    if not issues:
        fields_payload = _read_validated_artifact(artifact_dir, manifest_payload, "fields.json", issues)
    fields_duration_ms = (time.perf_counter() - fields_started) * 1000

    assignments_started = time.perf_counter()
    assignments_payload: dict[str, Any] = {}
    compatibility_payload: dict[str, Any] = {}
    taxonomy_payload: dict[str, Any] = {}
    if not issues:
        assignments_payload = _read_validated_artifact(
            artifact_dir,
            manifest_payload,
            "characteristic_assignments.json",
            issues,
        )
        compatibility_payload = _read_validated_artifact(
            artifact_dir,
            manifest_payload,
            "compatibility.json",
            issues,
        )
        taxonomy_payload = _read_validated_artifact(
            artifact_dir,
            manifest_payload,
            "taxonomy.json",
            issues,
        )
    assignments_duration_ms = (time.perf_counter() - assignments_started) * 1000

    projection_started = time.perf_counter()
    projection: Ref2ReadProjection | None = None
    counts: dict[str, int] = {}
    projection_size_bytes = 0
    if not issues and ref1_activation.is_valid:
        projection, counts = _build_projection(
            fields_payload,
            assignments_payload,
            compatibility_payload,
            taxonomy_payload,
            approval_payload,
            registry,
            issues,
        )
        if projection is not None:
            projection_size_bytes = len(
                json.dumps(
                    [schema.as_detail() for schema in projection.schemas],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
    projection_duration_ms = (time.perf_counter() - projection_started) * 1000

    registry_mutated = registry_before != _registry_snapshot(registry)
    if registry_mutated:
        issues.append(Module1Ref2ReadIssue("REGISTRY_MUTATION_DETECTED", "REF-2 read activation changed the legacy registry"))

    total_duration_ms = (time.perf_counter() - started) * 1000
    is_valid = not issues and projection is not None
    return Module1Ref2ReadActivation(
        mode="ref2_read",
        status="PASS" if is_valid else "BLOCKED",
        is_valid=is_valid,
        package_validated=package_validation.is_valid,
        ref1_approval_validated=ref1_activation.is_valid,
        ref2_approval_validated=is_valid,
        artifact_set_id=package_validation.artifact_set_id,
        manifest_sha256=package_validation.manifest_sha256,
        ref1_approval_id=ref1_activation.approval_id,
        ref1_approval_sha256=ref1_activation.approval_sha256,
        ref2_approval_id=approval_payload.get("approval_id") if approval_payload else None,
        ref2_approval_sha256=approval_sha256,
        counts=MappingProxyType(dict(sorted(counts.items()))),
        issues=tuple(issues),
        registry_mutated=registry_mutated,
        database_writes=0,
        preference_writes=0,
        business_reads_enabled=is_valid,
        ref_only_writes_enabled=False,
        loaded_object_count=(counts.get("fields", 0) + counts.get("assignments_total", 0)),
        validation_duration_ms=package_validation.validation_duration_ms,
        ref1_validation_duration_ms=ref1_duration_ms,
        ref2_approval_validation_duration_ms=approval_duration_ms,
        fields_load_duration_ms=fields_duration_ms,
        assignments_load_duration_ms=assignments_duration_ms,
        projection_load_duration_ms=projection_duration_ms,
        total_duration_ms=total_duration_ms,
        projection_size_bytes=projection_size_bytes,
        ref1_activation=ref1_activation if ref1_activation.is_valid else None,
        projection=projection if is_valid else None,
        policy=Module1Ref2PurposePolicy() if is_valid else None,
    )


def _validate_approval_contract(
    approval: Mapping[str, Any],
    manifest: Mapping[str, Any],
    package_validation: Any,
    ref1_activation: Module1Ref1ReadActivation,
    issues: list[Module1Ref2ReadIssue],
) -> None:
    expected = _expected_approval(manifest, package_validation.manifest_sha256)
    checks = (
        (set(approval) == TOP_LEVEL_KEYS, "APPROVAL_KEYS_INVALID"),
        (approval.get("approval_schema_version") == APPROVAL_SCHEMA_VERSION, "APPROVAL_SCHEMA_INVALID"),
        (approval.get("approval_id") == APPROVAL_ID, "APPROVAL_ID_INVALID"),
        (approval.get("approval_version") == APPROVAL_VERSION, "APPROVAL_VERSION_INVALID"),
        (approval.get("decision_number") == 37, "APPROVAL_DECISION_INVALID"),
        (approval.get("approved_modes") == ["ref2_read"], "APPROVED_MODES_INVALID"),
        (approval.get("prerequisite_approvals") == expected["prerequisite_approvals"], "PREREQUISITE_CONTRACT_INVALID"),
        (approval.get("runtime_package") == expected["runtime_package"], "RUNTIME_PACKAGE_INVALID"),
        (approval.get("counts") == expected["counts"], "COUNTS_INVALID"),
        (approval.get("purpose_policy") == expected["purpose_policy"], "PURPOSE_POLICY_INVALID"),
        (approval.get("required_semantics_policy") == expected["required_semantics_policy"], "REQUIRED_POLICY_INVALID"),
        (approval.get("runtime_only_fields_policy") == expected["runtime_only_fields_policy"], "RUNTIME_ONLY_POLICY_INVALID"),
        (approval.get("overlap_compatibility_policy") == expected["overlap_compatibility_policy"], "OVERLAP_POLICY_INVALID"),
        (approval.get("assignment_policy") == expected["assignment_policy"], "ASSIGNMENT_POLICY_INVALID"),
        (approval.get("packaging_boundary_policy") == expected["packaging_boundary_policy"], "PACKAGING_POLICY_INVALID"),
        (approval.get("read_policy") == expected["read_policy"], "READ_POLICY_INVALID"),
        (approval.get("write_policy") == expected["write_policy"], "WRITE_POLICY_INVALID"),
        (approval.get("rollback_policy") == expected["rollback_policy"], "ROLLBACK_POLICY_INVALID"),
        (approval.get("activation_flags") == expected["activation_flags"], "ACTIVATION_FLAGS_INVALID"),
        (approval.get("canonical_serialization") == expected["canonical_serialization"], "SERIALIZATION_POLICY_INVALID"),
        (approval == expected, "APPROVAL_PAYLOAD_NOT_CANONICAL"),
        (ref1_activation.approval_id == REF1_APPROVAL_ID, "REF1_APPROVAL_ID_INVALID"),
        (ref1_activation.approval_sha256 == REF1_APPROVAL_SHA256, "REF1_APPROVAL_HASH_INVALID"),
    )
    for passed, code in checks:
        if not passed:
            issues.append(Module1Ref2ReadIssue(code, code.replace("_", " ").title()))


def _expected_approval(manifest: Mapping[str, Any], manifest_sha256: str | None) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", {})
    source_hashes = {
        str(item.get("filename")): str(item.get("sha256"))
        for item in manifest.get("source_packages", [])
        if isinstance(item, Mapping)
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
        "prerequisite_approvals": [
            {
                "approval_id": REF1_APPROVAL_ID,
                "approval_sha256": REF1_APPROVAL_SHA256,
                "required_mode": "ref1_read",
            }
        ],
        "purpose_policy": {
            "allow": list(APPROVED_PURPOSES),
            "deny": list(DENIED_PURPOSES),
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
                "compatibility": str(artifacts.get("compatibility.json", {}).get("sha256")),
                "fields": str(artifacts.get("fields.json", {}).get("sha256")),
                "flattened_assignments": str(artifacts.get("characteristic_assignments.json", {}).get("sha256")),
            },
            "artifact_schema_version": str(manifest.get("artifact_schema_version")),
            "compatibility_map_version": str(manifest.get("compatibility_map_version")),
            "manifest_sha256": manifest_sha256,
            "package_id": str(manifest.get("artifact_set_id")),
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


def _build_projection(
    fields_payload: Mapping[str, Any],
    assignments_payload: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    taxonomy_payload: Mapping[str, Any],
    approval: Mapping[str, Any],
    registry: MaterialKnowledgeSeedRegistry,
    issues: list[Module1Ref2ReadIssue],
) -> tuple[Ref2ReadProjection | None, dict[str, int]]:
    fields = _unique_by_code(fields_payload.get("fields"), "code", "fields", issues)
    assignments = _unique_by_code(
        assignments_payload.get("assignments"),
        "material_type_id",
        "assignments",
        issues,
    )
    material_types = _unique_by_code(
        taxonomy_payload.get("material_types"),
        "code",
        "material_types",
        issues,
    )
    groups = _unique_by_code(taxonomy_payload.get("groups"), "code", "groups", issues)
    review_codes = frozenset(compatibility.get("review_exclusions", {}).get("ref2_assignment_material_types", []))
    packaging_mismatches = compatibility.get("diagnostics", {}).get("packaging_ref2_mismatches", [])
    packaging_codes = frozenset(
        str(item.get("material_type_id"))
        for item in packaging_mismatches
        if isinstance(item, Mapping) and item.get("material_type_id")
    )
    runtime_fields = compatibility.get("fields", {}).get("runtime_fields", [])
    runtime_field_codes = {
        str(item.get("code"))
        for item in runtime_fields
        if isinstance(item, Mapping) and item.get("code")
    }
    runtime_only_codes = {
        str(item.get("code"))
        for item in runtime_fields
        if isinstance(item, Mapping) and item.get("projection_classification") == "RUNTIME_ONLY"
    }
    overlap_codes = runtime_field_codes - runtime_only_codes
    approved_overlap_codes = READ_COMPATIBLE_FIELDS | REVIEW_REQUIRED_FIELDS | REQUIRED_SEMANTICS_MISMATCH_FIELDS

    expected_contract = approval.get("counts", {})
    profiles = {str(item.get("source_profile_id")) for item in assignments.values()}
    contract_checks = (
        (len(fields) == 558, "FIELDS_COUNT_MISMATCH"),
        (len(assignments) == 930, "ELIGIBLE_ASSIGNMENT_COUNT_MISMATCH"),
        (len(review_codes) == 48, "REVIEW_EXCLUSION_COUNT_MISMATCH"),
        (not (set(assignments) & review_codes), "REVIEW_ASSIGNMENT_LEAKAGE"),
        (set(assignments) | set(review_codes) == set(material_types), "INCOMPLETE_FLATTENED_ASSIGNMENTS"),
        (0 < len(profiles) <= 177, "PROFILE_REFERENCE_COUNT_INVALID"),
        (assignments_payload.get("authoring_inheritance_present") is False, "AUTHORING_INHERITANCE_LEAKAGE"),
        (len(packaging_mismatches) == 345, "PACKAGING_MISMATCH_COUNT_INVALID"),
        (len(packaging_codes) == 316, "PACKAGING_AFFECTED_COUNT_INVALID"),
        (compatibility.get("fields", {}).get("required_semantics_active") is False, "REF_REQUIRED_SEMANTICS_ACTIVE"),
        (len(runtime_fields) == 74, "RUNTIME_FIELD_COUNT_MISMATCH"),
        (len(runtime_only_codes) == 28, "RUNTIME_ONLY_FIELD_COUNT_MISMATCH"),
        (overlap_codes == approved_overlap_codes, "OVERLAP_FIELD_SET_MISMATCH"),
        (len(READ_COMPATIBLE_FIELDS) == expected_contract.get("overlap_read_compatible"), "READ_COMPATIBLE_COUNT_MISMATCH"),
        (len(REVIEW_REQUIRED_FIELDS) == expected_contract.get("overlap_review_required"), "REVIEW_REQUIRED_COUNT_MISMATCH"),
        (len(REQUIRED_SEMANTICS_MISMATCH_FIELDS) == expected_contract.get("overlap_required_semantics_mismatch"), "REQUIRED_MISMATCH_COUNT_INVALID"),
    )
    for passed, code in contract_checks:
        if not passed:
            issues.append(Module1Ref2ReadIssue(code, code.replace("_", " ").title()))

    for material_type_code, assignment in assignments.items():
        all_codes = tuple(str(value) for value in assignment.get("all_field_codes", []))
        bucket_codes = {
            str(value)
            for key in ("required", "module2_required", "recommended", "conditional")
            for value in assignment.get(key, [])
        }
        if len(all_codes) != len(set(all_codes)) or not bucket_codes.issubset(set(all_codes)):
            issues.append(Module1Ref2ReadIssue("INCOMPLETE_FLATTENED_SCHEMA", material_type_code))
        if not set(all_codes).issubset(fields):
            issues.append(Module1Ref2ReadIssue("UNKNOWN_FIELD_REFERENCE", material_type_code))
        if assignment.get("inheritance_resolved") is not True:
            issues.append(Module1Ref2ReadIssue("INHERITANCE_NOT_RESOLVED", material_type_code))
        if assignment.get("required_semantics_active") is not False or assignment.get("write_eligible") is not False:
            issues.append(Module1Ref2ReadIssue("WRITE_OR_REQUIRED_LEAKAGE", material_type_code))

    if issues:
        return None, {}

    legacy_schemas = registry.characteristic_schemas
    warning_schema_codes = (packaging_codes | set(legacy_schemas)) & set(assignments)
    schemas: list[Ref2ProjectedSchema] = []
    artifact_set_id = str(fields_payload.get("artifact_set_id"))
    for material_type_code in sorted(material_types):
        taxonomy = material_types[material_type_code]
        group_code = str(taxonomy.get("canonical_parent"))
        group = groups.get(group_code, {})
        legacy_schema = legacy_schemas.get(material_type_code)
        if material_type_code in review_codes:
            schemas.append(
                Ref2ProjectedSchema(
                    material_type_code=material_type_code,
                    material_type_title=str(taxonomy.get("name_ru") or material_type_code),
                    canonical_group_code=group_code,
                    canonical_group_title=str(group.get("name_ru") or group_code),
                    schema_status="review_excluded",
                    source_profile_id=None,
                    fields=tuple(),
                    warning_codes=("REF2_ASSIGNMENT_REVIEW_EXCLUDED",),
                    packaging_boundary_warnings=("PACKAGING_DIAGNOSTICS_NOT_APPLIED",) if material_type_code in packaging_codes else tuple(),
                    legacy_schema_present=legacy_schema is not None,
                    field_availability="withheld_pending_review",
                    runtime_package_id=artifact_set_id,
                    ref1_approval_id=REF1_APPROVAL_ID,
                    ref1_approval_version="1.0",
                    ref2_approval_id=APPROVAL_ID,
                    ref2_approval_version=APPROVAL_VERSION,
                )
            )
            continue

        assignment = assignments[material_type_code]
        required_codes = set(assignment.get("required", []))
        legacy_required = set(legacy_schema.required) if legacy_schema else set()
        projected_fields: list[Ref2ProjectedField] = []
        for field_code in sorted(str(value) for value in assignment.get("all_field_codes", [])):
            field = fields[field_code]
            compatibility_status = _field_compatibility_status(field_code)
            field_warnings: list[str] = []
            if compatibility_status == "review_required":
                field_warnings.append("FIELD_COMPATIBILITY_REVIEW_REQUIRED")
            elif compatibility_status == "required_semantics_mismatch":
                field_warnings.append("REQUIRED_SEMANTICS_MISMATCH")
            if (
                legacy_schema is not None
                and field_code in overlap_codes
                and (field_code in required_codes) != (field_code in legacy_required)
            ):
                field_warnings.append("REF_LEGACY_REQUIRED_DIFFERENCE")
            projected_fields.append(
                Ref2ProjectedField(
                    field_code=field_code,
                    field_title=str(field.get("label_ru") or field_code),
                    value_type=str(field.get("data_type") or "unknown"),
                    unit_code=_text(field.get("unit_code")),
                    ref_source_required=field_code in required_codes,
                    legacy_effective_required=field_code in legacy_required,
                    compatibility_status=compatibility_status,
                    warning_codes=tuple(field_warnings),
                )
            )
        schema_warnings: list[str] = []
        packaging_warnings: tuple[str, ...] = tuple()
        if material_type_code in packaging_codes:
            schema_warnings.append("PACKAGING_REF2_MISMATCH")
            packaging_warnings = ("PACKAGING_REF2_MISMATCH_DIAGNOSTIC_ONLY",)
        if legacy_schema is not None:
            schema_warnings.append("LEGACY_SCHEMA_CONTRACT_PRESERVED")
        schemas.append(
            Ref2ProjectedSchema(
                material_type_code=material_type_code,
                material_type_title=str(taxonomy.get("name_ru") or material_type_code),
                canonical_group_code=group_code,
                canonical_group_title=str(group.get("name_ru") or group_code),
                schema_status="readable_with_warnings" if material_type_code in warning_schema_codes else "fully_readable",
                source_profile_id=str(assignment.get("source_profile_id")),
                fields=tuple(projected_fields),
                warning_codes=tuple(schema_warnings),
                packaging_boundary_warnings=packaging_warnings,
                legacy_schema_present=legacy_schema is not None,
                field_availability="approved_read_only",
                runtime_package_id=artifact_set_id,
                ref1_approval_id=REF1_APPROVAL_ID,
                ref1_approval_version="1.0",
                ref2_approval_id=APPROVAL_ID,
                ref2_approval_version=APPROVAL_VERSION,
            )
        )

    status_counts = Counter(schema.schema_status for schema in schemas)
    counts = {
        "assignments_blocked": 0,
        "assignments_eligible": len(assignments),
        "assignments_fully_readable": status_counts["fully_readable"],
        "assignments_readable_with_warnings": status_counts["readable_with_warnings"],
        "assignments_review_excluded": status_counts["review_excluded"],
        "assignments_total": len(schemas),
        "fields": len(fields),
        "profiles": int(expected_contract.get("profiles", 0)),
    }
    if counts != {key: expected_contract[key] for key in counts}:
        issues.append(Module1Ref2ReadIssue("PROJECTION_COUNT_MISMATCH", f"Expected approved counts; got {counts}"))
        return None, counts

    compatibility_summary = MappingProxyType(
        {
            "overlap_total": 46,
            "read_compatible": 21,
            "review_required": 19,
            "required_semantics_mismatch": 6,
            "runtime_only_fields": 28,
            "packaging_mismatches": 345,
            "packaging_affected_material_types": 316,
        }
    )
    schema_tuple = tuple(schemas)
    return (
        Ref2ReadProjection(
            schemas=schema_tuple,
            schema_by_code=MappingProxyType({schema.material_type_code: schema for schema in schema_tuple}),
            counts=MappingProxyType(
                {
                    "fully_readable": status_counts["fully_readable"],
                    "readable_with_warnings": status_counts["readable_with_warnings"],
                    "review_excluded": status_counts["review_excluded"],
                    "blocked": 0,
                }
            ),
            compatibility_summary=compatibility_summary,
        ),
        counts,
    )


def _field_compatibility_status(field_code: str) -> str:
    if field_code in READ_COMPATIBLE_FIELDS:
        return "read_compatible"
    if field_code in REVIEW_REQUIRED_FIELDS:
        return "review_required"
    if field_code in REQUIRED_SEMANTICS_MISMATCH_FIELDS:
        return "required_semantics_mismatch"
    return "ref_only"


def _confined_approval_dir(path: Path, allowed_root: Path, expected_id: str) -> Path:
    resolved = path.resolve()
    root = allowed_root.resolve()
    if root not in resolved.parents or resolved.name != expected_id:
        raise ValueError("Approval directory is outside the configured approval root")
    return resolved


def _read_validated_artifact(
    artifact_dir: Path,
    manifest: Mapping[str, Any],
    filename: str,
    issues: list[Module1Ref2ReadIssue],
) -> dict[str, Any]:
    contract = manifest.get("artifacts", {}).get(filename, {})
    path = artifact_dir / filename
    if not path.is_file() or _sha256_file_or_none(path) != contract.get("sha256"):
        issues.append(Module1Ref2ReadIssue("ARTIFACT_HASH_MISMATCH", filename))
        return {}
    return _read_json(path, "ARTIFACT_INVALID_JSON", issues)


def _unique_by_code(
    records: Any,
    key: str,
    label: str,
    issues: list[Module1Ref2ReadIssue],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    if not isinstance(records, list):
        issues.append(Module1Ref2ReadIssue("COLLECTION_INVALID", label))
        return result
    for item in records:
        code = _text(item.get(key)) if isinstance(item, Mapping) else None
        if not code:
            issues.append(Module1Ref2ReadIssue("IDENTIFIER_MISSING", label))
        elif code in result:
            issues.append(Module1Ref2ReadIssue("DUPLICATE_IDENTIFIER", f"{label}:{code}"))
        else:
            result[code] = item
    return result


def _registry_snapshot(registry: MaterialKnowledgeSeedRegistry) -> tuple[Any, ...]:
    return (
        registry.version,
        tuple((group.code, group.name, group.children) for group in registry.taxonomy),
        tuple(
            (code, schema.required, schema.module2_required, schema.recommended)
            for code, schema in sorted(registry.characteristic_schemas.items())
        ),
        tuple(sorted(registry.role_mappings)),
        registry.compatibility_rules,
        registry.alternative_rules,
        registry.unit_conversions,
    )


def _read_json(
    path: Path,
    error_code: str,
    issues: list[Module1Ref2ReadIssue],
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(Module1Ref2ReadIssue(error_code, str(exc)))
        return {}
    if not isinstance(payload, dict):
        issues.append(Module1Ref2ReadIssue(error_code, "Expected a JSON object"))
        return {}
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_file_or_none(path: Path) -> str | None:
    try:
        return _sha256_file(path)
    except OSError:
        return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
