from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .combined import project_combined_ref_validation
from .loader import DEFAULT_PACKAGE_FILES, RefPackageLoader
from .models import IssueSeverity
from .portability import portable_identity_or_raw
from .ref1 import DEFAULT_RUNTIME_TAXONOMY_PATH, normalize_code, project_ref1_taxonomy
from .ref2 import project_ref2_characteristics
from .ref3_extended import DEFAULT_WORK_CATALOG_PATH, project_ref3_extended
from .ref3_units import DEFAULT_RUNTIME_UNIT_SERVICE_PATH, project_ref3_units


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
ARTIFACT_SCHEMA_VERSION = "1.0"
GENERATOR_VERSION = "1.0"
COMPATIBILITY_MAP_VERSION = "1.0"
SUPPORTED_LOADER_MODES = ("legacy", "artifact_validation")
ARTIFACT_FILENAMES = (
    "taxonomy.json",
    "fields.json",
    "characteristic_assignments.json",
    "units.json",
    "conversions.json",
    "packaging.json",
    "rules_metadata.json",
    "compatibility.json",
)
MANIFEST_FILENAME = "manifest.json"

_PRESENTATION_FIELDS = {"application", "application_hint"}
_PACKAGING_FIELDS = {
    "area_per_box_m2",
    "area_per_pack_m2",
    "bag_weight_kg",
    "canister_volume_l",
    "sheets_per_pack",
}
_CALCULATED_FIELDS = {"kg_per_meter", "ridge_cap_coverage"}
_PRESERVED_FIELDS = {"certificate", "unit"}
_SEMANTIC_REVIEW_FIELDS = {"weight_kg"}


class RuntimeArtifactBuildError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeArtifactBuildResult:
    artifact_set_id: str
    output_dir: Path
    artifact_hashes: Mapping[str, str]
    source_hashes: Mapping[str, str]
    counts: Mapping[str, Any]
    package_size_bytes: int
    generation_duration_ms: float
    idempotent: bool


def build_runtime_artifact_package(
    reference_root: str | Path,
    output_root: str | Path = DEFAULT_RUNTIME_REFERENCE_ROOT,
    *,
    artifact_set_id: str | None = None,
    legacy_seed_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
    runtime_unit_service_path: str | Path = DEFAULT_RUNTIME_UNIT_SERVICE_PATH,
    work_catalog_path: str | Path = DEFAULT_WORK_CATALOG_PATH,
) -> RuntimeArtifactBuildResult:
    started = time.perf_counter()
    reference_root = Path(reference_root)
    output_root = Path(output_root)
    legacy_seed_path = Path(legacy_seed_path)
    runtime_unit_service_path = Path(runtime_unit_service_path)
    work_catalog_path = Path(work_catalog_path)

    source_summary = RefPackageLoader(reference_root).load()
    blockers = [issue for issue in source_summary.issues if issue.severity is IssueSeverity.BLOCKER]
    if blockers:
        raise RuntimeArtifactBuildError("REF source validation failed: " + "; ".join(issue.code for issue in blockers))

    source_records, source_hashes = _source_records(reference_root, source_summary.sources)
    legacy_hashes = {
        "material_knowledge_seed.json": _sha256_file(legacy_seed_path),
        "module1_unit_conversion_registry.py": _sha256_file(runtime_unit_service_path),
        "work_catalog_seed.json": _sha256_file(work_catalog_path),
    }
    effective_set_id = artifact_set_id or derive_artifact_set_id(source_hashes, legacy_hashes)
    _validate_artifact_set_id(effective_set_id)

    combined = project_combined_ref_validation(
        reference_root,
        runtime_taxonomy_path=legacy_seed_path,
        runtime_unit_service_path=runtime_unit_service_path,
        work_catalog_path=work_catalog_path,
        project_root=PROJECT_ROOT,
    )
    if combined.counts.get("severity", {}).get("blockers", 0):
        raise RuntimeArtifactBuildError("Combined REF projection contains blockers")

    ref1 = project_ref1_taxonomy(reference_root, legacy_seed_path)
    ref2 = project_ref2_characteristics(reference_root, legacy_seed_path)
    ref3_units = project_ref3_units(reference_root, legacy_seed_path, runtime_unit_service_path)
    ref3_extended = project_ref3_extended(reference_root, work_catalog_path)
    raw = _load_source_payloads(reference_root)
    legacy_seed = _read_json(legacy_seed_path)

    review_ref2 = {normalize_code(item.get("material_type_id")) for item in raw["REF-2B"].get("review_queue", [])}
    review_units = {str(item.get("unit_code") or "") for item in raw["REF-3A"].get("review_queue", [])}
    review_packaging = {normalize_code(item.get("material_type_id")) for item in raw["REF-3B"].get("review_queue", [])}
    mismatch_types = {normalize_code(item.get("material_type_id")) for item in ref3_extended.packaging_mismatches}

    legacy_groups, legacy_type_parents = _legacy_taxonomy(legacy_seed)
    runtime_field_usages = _runtime_field_usages(legacy_seed)
    field_matrix = {item.entity_id: item.classification.value for item in ref2.field_matrix}
    unit_matrix = {item.entity_id: item.classification.value for item in ref3_units.unit_matrix}

    payloads: dict[str, dict[str, Any]] = {}
    payloads["taxonomy.json"] = _taxonomy_payload(
        effective_set_id, ref1, legacy_groups, legacy_type_parents
    )
    payloads["fields.json"] = _fields_payload(effective_set_id, ref2, field_matrix)
    payloads["characteristic_assignments.json"] = _assignments_payload(
        effective_set_id, raw["REF-2B"], review_ref2
    )
    payloads["units.json"] = _units_payload(effective_set_id, ref3_units, raw["REF-3A"], review_units)
    payloads["conversions.json"] = _conversions_payload(effective_set_id, ref3_units)
    payloads["packaging.json"] = _packaging_payload(
        effective_set_id,
        raw["REF-3B"],
        review_packaging,
        mismatch_types,
    )
    payloads["rules_metadata.json"] = _rules_payload(effective_set_id, raw["REF-3C"])
    payloads["compatibility.json"] = _compatibility_payload(
        effective_set_id=effective_set_id,
        ref1=ref1,
        ref2=ref2,
        ref3_units=ref3_units,
        ref3_extended=ref3_extended,
        legacy_groups=legacy_groups,
        legacy_type_parents=legacy_type_parents,
        runtime_field_usages=runtime_field_usages,
        field_matrix=field_matrix,
        unit_matrix=unit_matrix,
        review_ref2=review_ref2,
        review_units=review_units,
        review_packaging=review_packaging,
        combined=combined,
        raw_ref2b=raw["REF-2B"],
    )

    artifact_bytes = {name: _json_bytes(payloads[name]) for name in ARTIFACT_FILENAMES}
    artifact_hashes = {name: _sha256_bytes(content) for name, content in artifact_bytes.items()}
    manifest = _manifest_payload(
        artifact_set_id=effective_set_id,
        source_records=source_records,
        source_hashes=source_hashes,
        legacy_hashes=legacy_hashes,
        artifact_bytes=artifact_bytes,
        artifact_hashes=artifact_hashes,
        payloads=payloads,
        combined=combined,
    )
    all_bytes = {**artifact_bytes, MANIFEST_FILENAME: _json_bytes(manifest)}
    target = output_root / effective_set_id
    idempotent = _write_immutable_package(target, all_bytes)
    duration_ms = (time.perf_counter() - started) * 1000
    return RuntimeArtifactBuildResult(
        artifact_set_id=effective_set_id,
        output_dir=target,
        artifact_hashes=artifact_hashes,
        source_hashes=source_hashes,
        counts=manifest["counts"],
        package_size_bytes=sum(len(content) for content in all_bytes.values()),
        generation_duration_ms=duration_ms,
        idempotent=idempotent,
    )


def derive_artifact_set_id(
    source_hashes: Mapping[str, str],
    legacy_hashes: Mapping[str, str],
) -> str:
    fingerprint = _sha256_bytes(
        _json_bytes(
            {
                "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
                "generator_version": GENERATOR_VERSION,
                "source_hashes": dict(sorted(source_hashes.items())),
                "legacy_hashes": dict(sorted(legacy_hashes.items())),
            }
        )
    )
    return f"ref-runtime-v1-{fingerprint[:16]}"


def _artifact_header(artifact_set_id: str, artifact_type: str) -> dict[str, Any]:
    return {
        "activation_status": "inactive_validation_only",
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_set_id": artifact_set_id,
        "artifact_type": artifact_type,
        "runtime_activation_allowed": False,
        "write_activation_allowed": False,
    }


def _taxonomy_payload(
    artifact_set_id: str,
    ref1: Any,
    legacy_groups: set[str],
    legacy_type_parents: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    groups = [
        {
            "code": item.normalized_code,
            "legacy_recognized": item.normalized_code in legacy_groups,
            "name_ru": item.title,
            "source_status": item.status,
            "write_eligible": False,
        }
        for item in ref1.groups
    ]
    material_types = [
        {
            "canonical_parent": item.normalized_group_code,
            "code": item.normalized_code,
            "legacy_parent_paths": list(legacy_type_parents.get(item.normalized_code, ())),
            "legacy_recognized": item.normalized_code in legacy_type_parents,
            "name_ru": item.title,
            "source_status": item.status,
            "write_eligible": False,
        }
        for item in ref1.material_types
    ]
    return {
        **_artifact_header(artifact_set_id, "taxonomy"),
        "counts": {"groups": len(groups), "material_types": len(material_types)},
        "groups": groups,
        "material_types": material_types,
    }


def _fields_payload(
    artifact_set_id: str,
    ref2: Any,
    field_matrix: Mapping[str, str],
) -> dict[str, Any]:
    fields = [
        {
            "aliases": list(item.aliases),
            "allowed_values": list(item.allowed_values),
            "code": item.normalized_code,
            "data_type": item.data_type,
            "label_ru": item.title,
            "projection_classification": field_matrix.get(item.normalized_code, "UNKNOWN"),
            "source_status": item.status,
            "unit_code": item.unit_code,
        }
        for item in ref2.fields
    ]
    return {
        **_artifact_header(artifact_set_id, "field_dictionary"),
        "counts": {"fields": len(fields)},
        "fields": fields,
    }


def _assignments_payload(
    artifact_set_id: str,
    raw_ref2b: Mapping[str, Any],
    review_material_types: set[str],
) -> dict[str, Any]:
    assignments = [
        {
            "all_field_codes": sorted(normalize_code(value) for value in item.get("all_field_codes", [])),
            "conditional": sorted(normalize_code(value) for value in item.get("conditional", [])),
            "group_code": normalize_code(item.get("group_id")),
            "inheritance_resolved": True,
            "material_type_id": normalize_code(item.get("material_type_id")),
            "module2_required": sorted(normalize_code(value) for value in item.get("module2_required", [])),
            "recommended": sorted(normalize_code(value) for value in item.get("recommended", [])),
            "required": sorted(normalize_code(value) for value in item.get("required", [])),
            "required_semantics_active": False,
            "source_profile_id": normalize_code(item.get("profile_id")),
            "write_eligible": False,
        }
        for item in sorted(raw_ref2b.get("material_type_assignments", []), key=lambda value: str(value.get("material_type_id")))
        if normalize_code(item.get("material_type_id")) not in review_material_types
    ]
    return {
        **_artifact_header(artifact_set_id, "flattened_characteristic_assignments"),
        "authoring_inheritance_present": False,
        "counts": {
            "assignments": len(assignments),
            "source_assignments": len(raw_ref2b.get("material_type_assignments", [])),
            "review_excluded": len(review_material_types),
        },
        "assignments": assignments,
    }


def _units_payload(
    artifact_set_id: str,
    ref3_units: Any,
    raw_ref3a: Mapping[str, Any],
    review_units: set[str],
) -> dict[str, Any]:
    raw_by_code = {str(item.get("unit_code")): item for item in raw_ref3a.get("units", [])}
    units = []
    for item in ref3_units.units:
        if item.source_code in review_units:
            continue
        raw = raw_by_code.get(item.source_code, {})
        units.append(
            {
                "aliases": list(item.aliases),
                "auto_normalization_allowed": False,
                "base_unit_code": item.base_unit_code,
                "canonical_unit_code": raw.get("canonical_unit_code") or item.source_code,
                "code": item.source_code,
                "dimension": item.dimension,
                "label_ru": item.title,
                "roles": sorted(str(value) for value in raw.get("roles", [])),
                "source_status": item.status,
                "symbol": item.symbol,
                "write_eligible": False,
            }
        )
    return {
        **_artifact_header(artifact_set_id, "units"),
        "counts": {
            "eligible_units": len(units),
            "review_excluded": len(review_units),
            "source_units": len(ref3_units.units),
        },
        "units": units,
    }


def _conversions_payload(artifact_set_id: str, ref3_units: Any) -> dict[str, Any]:
    conversions = []
    for item in ref3_units.conversions:
        conversions.append(
            {
                "classification": item.classification.value,
                "executable": False,
                "factor": item.factor,
                "formula": item.formula,
                "from_unit": item.from_unit,
                "material_group": item.material_group,
                "required_parameters": [list(group) for group in item.required_parameters],
                "source_code": item.normalized_code,
                "source_type": item.source_type,
                "to_unit": item.to_unit,
            }
        )
    counts = Counter(item["source_type"] for item in conversions)
    return {
        **_artifact_header(artifact_set_id, "conversion_metadata"),
        "counts": {
            "conversions": len(conversions),
            "formula": counts["seed"],
            "simple": counts["simple"],
            "technical": counts["technical"],
        },
        "conversions": conversions,
    }


def _packaging_payload(
    artifact_set_id: str,
    raw_ref3b: Mapping[str, Any],
    review_material_types: set[str],
    mismatch_material_types: set[str],
) -> dict[str, Any]:
    excluded = review_material_types | mismatch_material_types
    profiles = [
        {
            "allowed_package_units": sorted(str(value) for value in item.get("allowed_package_units", [])),
            "allowed_price_basis_units": sorted(str(value) for value in item.get("allowed_price_basis_units", [])),
            "name_ru": item.get("name_ru"),
            "primary_quantity_units": sorted(str(value) for value in item.get("primary_quantity_units", [])),
            "profile_id": normalize_code(item.get("profile_id")),
            "recommended_fields": sorted(normalize_code(value) for value in item.get("recommended_fields", [])),
            "required_fields": sorted(normalize_code(value) for value in item.get("required_fields", [])),
        }
        for item in sorted(raw_ref3b.get("packaging_profiles", []), key=lambda value: str(value.get("profile_id")))
    ]
    assignments = [
        {
            "candidate_price_basis_units": sorted(str(value) for value in item.get("candidate_price_basis_units", [])),
            "characteristic_fields_injected": False,
            "material_type_id": normalize_code(item.get("material_type_id")),
            "packaging_profile_id": normalize_code(item.get("packaging_profile_id")),
            "recommended_packaging_fields": sorted(normalize_code(value) for value in item.get("recommended_packaging_fields", [])),
            "required_packaging_fields": sorted(normalize_code(value) for value in item.get("required_packaging_fields", [])),
            "write_eligible": False,
        }
        for item in sorted(raw_ref3b.get("material_type_assignments", []), key=lambda value: str(value.get("material_type_id")))
        if normalize_code(item.get("material_type_id")) not in excluded
    ]
    return {
        **_artifact_header(artifact_set_id, "packaging"),
        "characteristic_contract_separate": True,
        "counts": {
            "assignments": len(assignments),
            "mismatch_material_types_excluded": len(mismatch_material_types),
            "profiles": len(profiles),
            "review_excluded": len(review_material_types),
            "source_assignments": len(raw_ref3b.get("material_type_assignments", [])),
            "unique_excluded_assignments": len(excluded),
        },
        "profiles": profiles,
        "assignments": assignments,
    }


def _rules_payload(artifact_set_id: str, raw_ref3c: Mapping[str, Any]) -> dict[str, Any]:
    geometry = [_inactive_rule(item) for item in sorted(raw_ref3c.get("geometry_rules", []), key=lambda value: str(value.get("rule_id")))]
    extended = [_inactive_rule(item) for item in sorted(raw_ref3c.get("coverage_consumption_rules", []), key=lambda value: str(value.get("rule_id")))]
    semantic_counts = Counter(str(item.get("semantic_type")) for item in extended)
    return {
        **_artifact_header(artifact_set_id, "extended_rules_metadata"),
        "counts": {
            "consumption": semantic_counts["conditional_consumption_rate"] + semantic_counts["operational_consumption"],
            "coverage": semantic_counts["coverage_rate"] + semantic_counts["package_coverage"],
            "geometry": len(geometry),
            "rules": len(geometry) + len(extended),
            "yield": semantic_counts["package_yield"],
        },
        "executable_rule_count": 0,
        "extended_rules": extended,
        "geometry_rules": geometry,
        "object_work_quantity_calculations": 0,
    }


def _inactive_rule(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "executable": False,
        "formula": item.get("formula"),
        "formula_hint": item.get("formula_hint"),
        "formula_inputs": item.get("formula_inputs") or [],
        "formula_outputs": item.get("formula_outputs") or [],
        "module1_boundary": item.get("module1_boundary"),
        "module2_use": item.get("module2_use"),
        "name_ru": item.get("name_ru"),
        "rule_id": normalize_code(item.get("rule_id")),
        "semantic_type": item.get("semantic_type"),
    }


def _compatibility_payload(
    *,
    effective_set_id: str,
    ref1: Any,
    ref2: Any,
    ref3_units: Any,
    ref3_extended: Any,
    legacy_groups: set[str],
    legacy_type_parents: Mapping[str, tuple[str, ...]],
    runtime_field_usages: Mapping[str, tuple[dict[str, str], ...]],
    field_matrix: Mapping[str, str],
    unit_matrix: Mapping[str, str],
    review_ref2: set[str],
    review_units: set[str],
    review_packaging: set[str],
    combined: Any,
    raw_ref2b: Mapping[str, Any],
) -> dict[str, Any]:
    ref_groups = {item.normalized_code: item for item in ref1.groups}
    ref_types = {item.normalized_code: item for item in ref1.material_types}
    taxonomy_types = []
    for code, parents in sorted(legacy_type_parents.items()):
        ref_item = ref_types.get(code)
        canonical_parent = ref_item.normalized_group_code if ref_item else None
        taxonomy_types.append(
            {
                "canonical_parent": canonical_parent,
                "code": code,
                "compatibility_status": "legacy_parent_conflict" if len(parents) > 1 else "recognized",
                "legacy_parent_paths": list(parents),
                "write_eligible": False,
            }
        )

    ref_field_codes = {item.normalized_code for item in ref2.fields}
    runtime_fields = []
    for code, usages in sorted(runtime_field_usages.items()):
        projection = field_matrix.get(code, "RUNTIME_ONLY")
        if code in ref_field_codes:
            classification = "semantic-review" if projection == "EXACT_MATCH" else "alias candidate"
            strategy = "preserve legacy semantics; REF metadata remains inactive"
        else:
            classification, strategy = _runtime_field_strategy(code)
        runtime_fields.append(
            {
                "automatic_action": "FORBIDDEN",
                "classification": classification,
                "code": code,
                "projection_classification": projection,
                "runtime_usages": list(usages),
                "strategy": strategy,
            }
        )

    exact_units = sorted(code for code, status in unit_matrix.items() if status == "EXACT_MATCH")
    ref_only_units = sorted(code for code, status in unit_matrix.items() if status == "REF_ONLY")
    warning_counts = Counter(
        issue.code for issue in combined.issues if issue.severity is IssueSeverity.WARNING
    )
    mismatch_records = sorted(
        (dict(item) for item in ref3_extended.packaging_mismatches),
        key=lambda item: (
            str(item.get("material_type_id")),
            str(item.get("field_code")),
            str(item.get("packaging_profile_id")),
        ),
    )
    mismatch_types = {normalize_code(item.get("material_type_id")) for item in mismatch_records}
    schema_comparison = _schema_comparison(raw_ref2b, runtime_field_usages)

    return {
        **_artifact_header(effective_set_id, "compatibility_and_diagnostics"),
        "behavior_contracts": {
            "artifact_business_reads": False,
            "database_writes": False,
            "legacy_registry_authoritative": True,
            "public_parallel_registry_allowed": False,
            "ref_only_writes": False,
            "registry_mutation": False,
        },
        "compatibility_map_version": COMPATIBILITY_MAP_VERSION,
        "diagnostics": {
            "accepted_warning_counts": dict(sorted(warning_counts.items())),
            "packaging_ref2_mismatch_count": len(mismatch_records),
            "packaging_ref2_mismatch_material_types": len(mismatch_types),
            "packaging_ref2_mismatches": mismatch_records,
        },
        "fields": {
            "overlap_fields": sum(1 for item in runtime_fields if item["projection_classification"] in {"EXACT_MATCH", "ALIAS_MATCH"}),
            "required_semantics_active": False,
            "runtime_fields": runtime_fields,
            "runtime_only_fields": sum(1 for item in runtime_fields if item["projection_classification"] == "RUNTIME_ONLY"),
            "schema_comparison": schema_comparison,
        },
        "review_exclusions": {
            "ref2_assignment_material_types": sorted(review_ref2),
            "ref3_packaging_material_types": sorted(review_packaging),
            "ref3_unit_codes": sorted(review_units),
        },
        "taxonomy": {
            "legacy_groups": sorted(legacy_groups),
            "legacy_material_types": taxonomy_types,
            "ref_only_groups": sorted(set(ref_groups) - legacy_groups),
            "ref_only_material_types": sorted(set(ref_types) - set(legacy_type_parents)),
            "special_conflicts": [
                {
                    "canonical_parent": "waterproofing",
                    "code": "liquid_waterproofing",
                    "compatibility_status": "legacy_paths_preserved_canonical_parent_single",
                    "legacy_parent_paths": list(legacy_type_parents.get("liquid_waterproofing", ())),
                    "reason": "REF-1 canonical parent is authoritative; duplicate canonical types are forbidden",
                    "write_eligible": False,
                }
            ],
        },
        "units": {
            "exact_runtime_units": exact_units,
            "ref_only_units": ref_only_units,
            "special_alias_rules": [
                {
                    "alias": "lm",
                    "automatic_mapping_allowed": False,
                    "canonical_owner": "lm",
                    "canonical_owner_meaning": "lumen",
                    "canonical_output_when_context_confirms": "linear_meter",
                    "compatibility_status": "context_required",
                    "legacy_target": "linear_meter",
                    "rejected_automatic_mapping": True,
                },
                {
                    "alias": "micron",
                    "automatic_mapping_allowed": False,
                    "canonical_owner": "um",
                    "compatibility_status": "deprecated_candidate_review_excluded",
                },
            ],
        },
    }


def _runtime_field_strategy(code: str) -> tuple[str, str]:
    if code in _PRESENTATION_FIELDS:
        return "presentation-only", "preserve outside REF assignment"
    if code in _PACKAGING_FIELDS:
        return "packaging-related", "preserve legacy read; candidate mapping requires review"
    if code in _CALCULATED_FIELDS:
        return "calculated", "preserve current calculation behavior; no automatic REF mapping"
    if code in _PRESERVED_FIELDS:
        return "preserve", "retain outside REF characteristic activation"
    if code in _SEMANTIC_REVIEW_FIELDS:
        return "semantic-review", "preserve ambiguous legacy meaning pending contextual review"
    return "alias candidate", "preserve legacy field; candidate alias requires separate review"


def _schema_comparison(
    raw_ref2b: Mapping[str, Any],
    runtime_field_usages: Mapping[str, tuple[dict[str, str], ...]],
) -> dict[str, Any]:
    assignment_by_type = {
        normalize_code(item.get("material_type_id")): item
        for item in raw_ref2b.get("material_type_assignments", [])
    }
    runtime_contracts: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"required": set(), "module2_required": set(), "recommended": set()}
    )
    for field_code, usages in runtime_field_usages.items():
        for usage in usages:
            runtime_contracts[usage["schema"]][usage["requirement"]].add(field_code)

    required_equal = 0
    module2_equal = 0
    recommended_equal = 0
    comparisons = []
    for schema_code, runtime in sorted(runtime_contracts.items()):
        assignment = assignment_by_type.get(schema_code)
        ref_required = {normalize_code(value) for value in assignment.get("required", [])} if assignment else set()
        ref_module2 = {normalize_code(value) for value in assignment.get("module2_required", [])} if assignment else set()
        ref_recommended = {normalize_code(value) for value in assignment.get("recommended", [])} if assignment else set()
        required_match = runtime["required"] == ref_required
        module2_match = runtime["module2_required"] == ref_module2
        recommended_match = runtime["recommended"] == ref_recommended
        required_equal += int(required_match)
        module2_equal += int(module2_match)
        recommended_equal += int(recommended_match)
        comparisons.append(
            {
                "legacy_required_preserved": True,
                "material_type_id": schema_code,
                "module2_required_equal": module2_match,
                "recommended_equal": recommended_match,
                "ref_required_active": False,
                "required_equal": required_match,
            }
        )
    return {
        "comparisons": comparisons,
        "legacy_schema_count": len(runtime_contracts),
        "module2_required_equal": module2_equal,
        "recommended_equal": recommended_equal,
        "required_equal": required_equal,
    }


def _manifest_payload(
    *,
    artifact_set_id: str,
    source_records: list[dict[str, Any]],
    source_hashes: Mapping[str, str],
    legacy_hashes: Mapping[str, str],
    artifact_bytes: Mapping[str, bytes],
    artifact_hashes: Mapping[str, str],
    payloads: Mapping[str, Mapping[str, Any]],
    combined: Any,
) -> dict[str, Any]:
    artifacts = {
        name: {
            "counts": payloads[name].get("counts", {}),
            "required": True,
            "sha256": artifact_hashes[name],
            "size_bytes": len(artifact_bytes[name]),
        }
        for name in ARTIFACT_FILENAMES
    }
    warning_counts = Counter(
        issue.code for issue in combined.issues if issue.severity is IssueSeverity.WARNING
    )
    counts = {
        "characteristic_assignments": payloads["characteristic_assignments.json"]["counts"],
        "conversions": payloads["conversions.json"]["counts"],
        "fields": payloads["fields.json"]["counts"],
        "packaging": payloads["packaging.json"]["counts"],
        "rules": payloads["rules_metadata.json"]["counts"],
        "taxonomy": payloads["taxonomy.json"]["counts"],
        "units": payloads["units.json"]["counts"],
    }
    return {
        "accepted_diagnostics": dict(sorted(warning_counts.items())),
        "activation_status": "inactive_validation_only",
        "application_contract": {
            "maximum": "module1-material-knowledge-seed-v1",
            "minimum": "module1-material-knowledge-seed-v1",
        },
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "artifact_set_id": artifact_set_id,
        "artifacts": artifacts,
        "compatibility_map_version": COMPATIBILITY_MAP_VERSION,
        "counts": counts,
        "default_loader_mode": "legacy",
        "deterministic_generation_command": "python -m tools.module1_ref_projection build-runtime --reference-root <reference-root> --legacy-seed <legacy-seed> --output <output-root>",
        "exclusions": {
            "packaging_ref2_mismatches": 345,
            "ref2_review_assignments": 48,
            "ref3_packaging_review_assignments": 51,
            "ref3_review_units": 17,
        },
        "generator": {
            "deterministic": True,
            "source_sha256": _sha256_file(Path(__file__)),
            "version": GENERATOR_VERSION,
        },
        "integration_allowed": False,
        "legacy_inputs": dict(sorted(legacy_hashes.items())),
        "runtime_activation_allowed": False,
        "source_bundle_sha256": _sha256_bytes(_json_bytes(dict(sorted(source_hashes.items())))),
        "source_packages": source_records,
        "supported_loader_modes": list(SUPPORTED_LOADER_MODES),
        "write_activation_allowed": False,
    }


def _source_records(reference_root: Path, sources: tuple[Any, ...]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    source_by_id = {source.package_id: source for source in sources}
    records = []
    hashes = {}
    for expected_id, filename in sorted(DEFAULT_PACKAGE_FILES.items()):
        source = source_by_id.get(expected_id)
        path = reference_root / filename
        digest = _sha256_file(path)
        hashes[expected_id] = digest
        records.append(
            {
                "filename": filename,
                "integration_allowed": source.integration_allowed if source else None,
                "package_id": source.package_id if source else expected_id,
                "sha256": digest,
                "status": source.status if source else "UNKNOWN",
                "version": source.version if source else "UNKNOWN",
            }
        )
    return records, hashes


def _load_source_payloads(reference_root: Path) -> dict[str, dict[str, Any]]:
    return {
        package_id: _read_json(reference_root / filename)
        for package_id, filename in DEFAULT_PACKAGE_FILES.items()
    }


def _legacy_taxonomy(payload: Mapping[str, Any]) -> tuple[set[str], dict[str, tuple[str, ...]]]:
    groups: set[str] = set()
    parents: dict[str, set[str]] = defaultdict(set)
    for group in payload.get("taxonomy", []):
        group_code = normalize_code(group.get("code"))
        if not group_code:
            continue
        groups.add(group_code)
        for child in group.get("children", []):
            child_code = normalize_code(child)
            if child_code:
                parents[child_code].add(group_code)
    return groups, {code: tuple(sorted(values)) for code, values in sorted(parents.items())}


def _runtime_field_usages(payload: Mapping[str, Any]) -> dict[str, tuple[dict[str, str], ...]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for schema_code, schema in sorted((payload.get("characteristicSchemas") or {}).items()):
        for source_key, requirement in (
            ("required", "required"),
            ("module2Required", "module2_required"),
            ("recommended", "recommended"),
        ):
            for field_code in schema.get(source_key, []):
                result[normalize_code(field_code)].append(
                    {"requirement": requirement, "schema": normalize_code(schema_code)}
                )
    return {
        code: tuple(sorted(usages, key=lambda item: (item["schema"], item["requirement"])))
        for code, usages in sorted(result.items())
    }


def _write_immutable_package(target: Path, payloads: Mapping[str, bytes]) -> bool:
    expected_names = set(payloads)
    if target.exists():
        existing_names = {path.name for path in target.iterdir() if path.is_file()}
        if existing_names != expected_names:
            raise RuntimeArtifactBuildError(f"Existing artifact set is incomplete or has extra files: {target}")
        if all((target / name).read_bytes() == content for name, content in payloads.items()):
            return True
        raise RuntimeArtifactBuildError(f"Immutable artifact set already exists with different content: {target}")
    target.mkdir(parents=True, exist_ok=False)
    for name in sorted(payloads):
        (target / name).write_bytes(payloads[name])
    return False


def _validate_artifact_set_id(value: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{7,95}", value):
        raise RuntimeArtifactBuildError("artifact_set_id must be a stable lowercase path-safe identifier")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_file(path: Path) -> str:
    return portable_identity_or_raw(path)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build deterministic inactive Module 1 REF runtime artifacts")
    parser.add_argument("--reference-root", required=True)
    parser.add_argument("--legacy-seed", default=str(DEFAULT_RUNTIME_TAXONOMY_PATH))
    parser.add_argument("--runtime-unit-service", default=str(DEFAULT_RUNTIME_UNIT_SERVICE_PATH))
    parser.add_argument("--work-catalog", default=str(DEFAULT_WORK_CATALOG_PATH))
    parser.add_argument("--artifact-set-id")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = build_runtime_artifact_package(
        args.reference_root,
        args.output,
        artifact_set_id=args.artifact_set_id,
        legacy_seed_path=args.legacy_seed,
        runtime_unit_service_path=args.runtime_unit_service,
        work_catalog_path=args.work_catalog,
    )
    print(
        json.dumps(
            {
                "artifact_hashes": dict(result.artifact_hashes),
                "artifact_set_id": result.artifact_set_id,
                "counts": dict(result.counts),
                "generation_duration_ms": round(result.generation_duration_ms, 3),
                "idempotent": result.idempotent,
                "output_dir": str(result.output_dir),
                "package_size_bytes": result.package_size_bytes,
                "runtime_activation_allowed": False,
                "source_hashes": dict(result.source_hashes),
                "write_activation_allowed": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0
