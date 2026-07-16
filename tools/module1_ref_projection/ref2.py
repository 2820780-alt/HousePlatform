from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import RefPackageLoader
from .models import (
    CompatibilityClassification,
    IssueSeverity,
    ProjectedCharacteristicField,
    ProjectedCharacteristicProfile,
    ProjectedProfileAssignment,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
)
from .ref1 import REF1_FILENAME, normalize_code


REF2A_PACKAGE_ID = "REF-2A"
REF2B_PACKAGE_ID = "REF-2B"
REF2A_FILENAME = "ATOM_REF2_Field_Dictionary_v1_DRAFT.json"
REF2B_FILENAME = "ATOM_REF2_Material_Characteristic_Profiles_v1_DRAFT.json"
DEFAULT_RUNTIME_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"
)
KNOWN_PACKAGING_REF2_MISMATCHES = 345


@dataclass(frozen=True)
class Ref2ProjectionResult:
    sources: tuple[ProjectionSource, ...]
    fields: tuple[ProjectedCharacteristicField, ...]
    profiles: tuple[ProjectedCharacteristicProfile, ...]
    assignments: tuple[ProjectedProfileAssignment, ...]
    field_matrix: tuple[ProjectionEntity, ...]
    profile_assignment_matrix: tuple[ProjectionEntity, ...]
    issues: tuple[ProjectionIssue, ...]
    counts: dict[str, int]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "sources": [source.as_dict() for source in self.sources],
            "counts": self.counts,
        }


def project_ref2_characteristics(
    reference_root: str | Path,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
) -> Ref2ProjectionResult:
    reference_root = Path(reference_root)
    runtime_taxonomy_path = Path(runtime_taxonomy_path)
    ref2a_payload = _read_json(reference_root / REF2A_FILENAME)
    ref2b_payload = _read_json(reference_root / REF2B_FILENAME)
    ref1_payload = _read_json(reference_root / REF1_FILENAME)
    sources = _projection_sources(reference_root)
    source_by_id = {source.package_id: source for source in sources}
    source_2a = source_by_id.get(REF2A_PACKAGE_ID, ProjectionSource(REF2A_PACKAGE_ID, "UNKNOWN", "UNKNOWN", reference_root / REF2A_FILENAME))
    source_2b = source_by_id.get(REF2B_PACKAGE_ID, ProjectionSource(REF2B_PACKAGE_ID, "UNKNOWN", "UNKNOWN", reference_root / REF2B_FILENAME))

    fields = _project_fields(ref2a_payload, source_2a)
    profiles = _project_profiles(ref2b_payload, source_2b)
    assignments = _project_assignments(ref2b_payload, source_2b)
    runtime = _load_runtime_characteristics(runtime_taxonomy_path)
    ref1_groups = {normalize_code(item.get("group_id")) for item in ref1_payload.get("groups", []) if item.get("group_id")}
    ref1_material_types = {normalize_code(item.get("material_type_id")) for item in ref1_payload.get("material_types", []) if item.get("material_type_id")}

    issues: list[ProjectionIssue] = []
    issues.extend(_duplicate_issues("field", fields, REF2A_PACKAGE_ID))
    issues.extend(_duplicate_issues("profile", profiles, REF2B_PACKAGE_ID))
    issues.extend(_duplicate_issues("assignment", assignments, REF2B_PACKAGE_ID))
    issues.extend(_validate_profiles(profiles, fields))
    issues.extend(_validate_assignments(assignments, profiles, fields, ref1_groups, ref1_material_types))

    field_matrix, field_issues = _build_field_matrix(fields, runtime)
    issues.extend(field_issues)
    profile_assignment_matrix = _build_profile_assignment_matrix(profiles, assignments, runtime)
    sorted_issues = tuple(sorted(issues, key=lambda item: (item.code, item.entity_id or "", item.message)))
    sorted_fields = tuple(sorted(fields, key=lambda item: item.normalized_code))
    sorted_profiles = tuple(sorted(profiles, key=lambda item: item.normalized_code))
    sorted_assignments = tuple(sorted(assignments, key=lambda item: item.normalized_code))
    sorted_field_matrix = tuple(sorted(field_matrix, key=lambda item: (item.entity_type, item.entity_id, item.classification.value)))
    sorted_profile_assignment_matrix = tuple(
        sorted(profile_assignment_matrix, key=lambda item: (item.entity_type, item.entity_id, item.classification.value))
    )
    counts = _build_counts(sorted_fields, sorted_profiles, sorted_assignments, runtime, sorted_field_matrix, sorted_profile_assignment_matrix, sorted_issues, ref2b_payload)
    return Ref2ProjectionResult(
        sources=sources,
        fields=sorted_fields,
        profiles=sorted_profiles,
        assignments=sorted_assignments,
        field_matrix=sorted_field_matrix,
        profile_assignment_matrix=sorted_profile_assignment_matrix,
        issues=sorted_issues,
        counts=counts,
    )


def write_ref2_projection_outputs(
    reference_root: str | Path,
    output_dir: str | Path,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
) -> Ref2ProjectionResult:
    result = project_ref2_characteristics(reference_root, runtime_taxonomy_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "ref2_projection_summary.json", result.summary_dict())
    _write_json(output_dir / "ref2_field_matrix.json", [entity.as_dict() for entity in result.field_matrix])
    _write_json(output_dir / "ref2_profile_assignment_matrix.json", [entity.as_dict() for entity in result.profile_assignment_matrix])
    _write_json(output_dir / "ref2_issues.json", [issue.as_dict() for issue in result.issues])
    (output_dir / "ref2_report.md").write_text(_build_report(result), encoding="utf-8")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _projection_sources(reference_root: Path) -> tuple[ProjectionSource, ...]:
    summary = RefPackageLoader(reference_root, {REF2A_PACKAGE_ID: REF2A_FILENAME, REF2B_PACKAGE_ID: REF2B_FILENAME}).load()
    return tuple(sorted(summary.sources, key=lambda source: source.package_id))


def _project_fields(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedCharacteristicField]:
    result: list[ProjectedCharacteristicField] = []
    for index, item in enumerate(payload.get("fields", [])):
        source_code = str(item.get("field_code") or "")
        result.append(
            ProjectedCharacteristicField(
                source=source,
                source_code=source_code,
                normalized_code=normalize_code(source_code),
                title=str(item.get("label_ru") or source_code),
                data_type=_optional_string(item.get("data_type")),
                unit_code=_optional_string(item.get("unit_code")),
                aliases=_aliases(item),
                allowed_values=tuple(str(value) for value in item.get("allowed_values") or []),
                status=str(item.get("status") or "UNKNOWN"),
                source_pointer=f"/fields/{index}",
            )
        )
    return result


def _project_profiles(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedCharacteristicProfile]:
    result: list[ProjectedCharacteristicProfile] = []
    for index, item in enumerate(payload.get("profiles", [])):
        source_code = str(item.get("profile_id") or "")
        result.append(
            ProjectedCharacteristicProfile(
                source=source,
                source_code=source_code,
                normalized_code=normalize_code(source_code),
                title=str(item.get("name_ru") or source_code),
                field_codes=_field_codes(item),
                required=_normalized_tuple(item.get("required")),
                module2_required=_normalized_tuple(item.get("module2_required")),
                recommended=_normalized_tuple(item.get("recommended")),
                conditional=_normalized_tuple(item.get("conditional")),
                status=str(item.get("status") or "UNKNOWN"),
                auto_activatable=False,
                source_pointer=f"/profiles/{index}",
            )
        )
    return result


def _project_assignments(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedProfileAssignment]:
    review_ids = {normalize_code(item.get("material_type_id")) for item in payload.get("review_queue", []) if item.get("material_type_id")}
    result: list[ProjectedProfileAssignment] = []
    for index, item in enumerate(payload.get("material_type_assignments", [])):
        material_type_id = str(item.get("material_type_id") or "")
        profile_id = str(item.get("profile_id") or "")
        group_code = item.get("group_id")
        source_code = f"{material_type_id}->{profile_id}"
        normalized_code = f"{normalize_code(material_type_id)}__{normalize_code(profile_id)}"
        result.append(
            ProjectedProfileAssignment(
                source=source,
                source_code=source_code,
                normalized_code=normalized_code,
                material_type_id=material_type_id,
                group_code=str(group_code) if group_code else None,
                profile_id=profile_id,
                field_codes=_field_codes(item),
                review_required=normalize_code(material_type_id) in review_ids,
                auto_activatable=False,
                source_pointer=f"/material_type_assignments/{index}",
            )
        )
    return result


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _aliases(item: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("aliases", "alias_codes", "aliases_ru", "synonyms"):
        raw = item.get(key)
        if isinstance(raw, list):
            values.extend(str(value) for value in raw if value)
        elif isinstance(raw, str) and raw:
            values.append(raw)
    return tuple(sorted({normalize_code(value) for value in values if normalize_code(value)}))


def _normalized_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return tuple()
    return tuple(sorted(normalize_code(value) for value in values if normalize_code(value)))


def _field_codes(item: dict[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for key in ("required", "module2_required", "module2Required", "recommended", "conditional", "all_field_codes"):
        raw = item.get(key)
        if isinstance(raw, list):
            values.update(normalize_code(value) for value in raw if normalize_code(value))
    return tuple(sorted(values))


def _load_runtime_characteristics(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    schemas_payload = payload.get("characteristicSchemas") or {}
    if isinstance(schemas_payload, list):
        schemas_payload = {str(item.get("schemaId") or item.get("groupCode") or index): item for index, item in enumerate(schemas_payload)}
    schemas: dict[str, dict[str, Any]] = {}
    fields: set[str] = set()
    field_definitions: dict[str, dict[str, Any]] = {}
    for schema_code, schema in schemas_payload.items():
        if not isinstance(schema, dict):
            continue
        normalized_schema_code = normalize_code(str(schema_code))
        schema_fields: set[str] = set()
        for key in ("required", "module2Required", "module2_required", "recommended", "conditional"):
            for field_code in schema.get(key, []) or []:
                normalized_field = normalize_code(field_code)
                if normalized_field:
                    fields.add(normalized_field)
                    schema_fields.add(normalized_field)
        raw_defs = schema.get("fieldDefinitions") or schema.get("field_definitions") or {}
        if isinstance(raw_defs, dict):
            for field_code, definition in raw_defs.items():
                normalized_field = normalize_code(field_code)
                if normalized_field and isinstance(definition, dict):
                    field_definitions[normalized_field] = definition
                    fields.add(normalized_field)
                    schema_fields.add(normalized_field)
        schemas[normalized_schema_code] = {"fields": tuple(sorted(schema_fields)), "raw": schema}
    global_defs = payload.get("runtimeFieldDefinitions") or payload.get("fieldDefinitions") or {}
    if isinstance(global_defs, dict):
        for field_code, definition in global_defs.items():
            normalized_field = normalize_code(field_code)
            if normalized_field and isinstance(definition, dict):
                field_definitions[normalized_field] = definition
                fields.add(normalized_field)
    return {"schemas": schemas, "fields": fields, "field_definitions": field_definitions}


def _duplicate_issues(entity_type: str, items: list[Any], package_id: str) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    for code, count in Counter(item.normalized_code for item in items if item.normalized_code).items():
        if count > 1:
            issues.append(
                ProjectionIssue(
                    code="REF2_DUPLICATE_NORMALIZED_CODE",
                    severity=IssueSeverity.BLOCKER,
                    message=f"Duplicate normalized REF-2 {entity_type} code: {code}",
                    package_id=package_id,
                    entity_id=code,
                )
            )
    return issues


def _validate_profiles(profiles: list[ProjectedCharacteristicProfile], fields: list[ProjectedCharacteristicField]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    field_codes = {field.normalized_code for field in fields}
    for profile in profiles:
        for field_code in profile.field_codes:
            if field_code not in field_codes:
                issues.append(_issue("REF2_PROFILE_UNKNOWN_FIELD", IssueSeverity.BLOCKER, f"Profile references unknown field {field_code!r}", profile))
    return issues


def _validate_assignments(
    assignments: list[ProjectedProfileAssignment],
    profiles: list[ProjectedCharacteristicProfile],
    fields: list[ProjectedCharacteristicField],
    ref1_groups: set[str],
    ref1_material_types: set[str],
) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    profile_codes = {profile.normalized_code for profile in profiles}
    field_codes = {field.normalized_code for field in fields}
    for assignment in assignments:
        if normalize_code(assignment.profile_id) not in profile_codes:
            issues.append(_issue("REF2_ASSIGNMENT_UNKNOWN_PROFILE", IssueSeverity.BLOCKER, f"Assignment references unknown profile {assignment.profile_id!r}", assignment))
        if normalize_code(assignment.material_type_id) not in ref1_material_types:
            issues.append(_issue("REF2_ASSIGNMENT_UNKNOWN_MATERIAL_TYPE", IssueSeverity.BLOCKER, f"Assignment references unknown material type {assignment.material_type_id!r}", assignment))
        if assignment.group_code and normalize_code(assignment.group_code) not in ref1_groups:
            issues.append(_issue("REF2_ASSIGNMENT_UNKNOWN_GROUP", IssueSeverity.BLOCKER, f"Assignment references unknown group {assignment.group_code!r}", assignment))
        for field_code in assignment.field_codes:
            if field_code not in field_codes:
                issues.append(_issue("REF2_ASSIGNMENT_UNKNOWN_FIELD", IssueSeverity.BLOCKER, f"Assignment references unknown field {field_code!r}", assignment))
    return issues


def _issue(code: str, severity: IssueSeverity, message: str, item: Any) -> ProjectionIssue:
    return ProjectionIssue(code=code, severity=severity, message=message, source_path=item.source.path, package_id=item.source.package_id, entity_id=item.source_code)


def _build_field_matrix(fields: list[ProjectedCharacteristicField], runtime: dict[str, Any]) -> tuple[list[ProjectionEntity], list[ProjectionIssue]]:
    entities: list[ProjectionEntity] = []
    issues: list[ProjectionIssue] = []
    runtime_fields: set[str] = set(runtime["fields"])
    runtime_defs: dict[str, dict[str, Any]] = runtime["field_definitions"]
    ref_codes = {field.normalized_code for field in fields}
    for field in fields:
        classification = _classify_field(field, runtime_fields, runtime_defs, fields)
        if classification is CompatibilityClassification.INCOMPATIBLE_TYPE:
            issues.append(_issue("REF2_FIELD_TYPE_MISMATCH", IssueSeverity.WARNING, "Runtime field data type differs from REF-2 field", field))
        elif classification is CompatibilityClassification.INCOMPATIBLE_UNIT:
            issues.append(_issue("REF2_FIELD_UNIT_MISMATCH", IssueSeverity.WARNING, "Runtime field unit differs from REF-2 field", field))
        entities.append(_field_entity(field, classification))
    for runtime_field in sorted(runtime_fields - ref_codes):
        entities.append(
            ProjectionEntity(
                entity_id=runtime_field,
                entity_type="characteristic_field",
                source_package_id="runtime",
                classification=CompatibilityClassification.RUNTIME_ONLY,
                payload={"normalized_code": runtime_field},
            )
        )
    return entities, issues


def _classify_field(field: ProjectedCharacteristicField, runtime_fields: set[str], runtime_defs: dict[str, dict[str, Any]], all_fields: list[ProjectedCharacteristicField]) -> CompatibilityClassification:
    if field.normalized_code in runtime_fields:
        runtime_def = runtime_defs.get(field.normalized_code) or {}
        runtime_type = _optional_string(runtime_def.get("data_type") or runtime_def.get("type"))
        runtime_unit = _optional_string(runtime_def.get("unit_code") or runtime_def.get("unit"))
        if runtime_type and field.data_type and normalize_code(runtime_type) != normalize_code(field.data_type):
            return CompatibilityClassification.INCOMPATIBLE_TYPE
        if runtime_unit and field.unit_code and normalize_code(runtime_unit) != normalize_code(field.unit_code):
            return CompatibilityClassification.INCOMPATIBLE_UNIT
        return CompatibilityClassification.EXACT_MATCH
    alias_hits = [alias for alias in field.aliases if alias in runtime_fields]
    if alias_hits:
        owners = [owner.normalized_code for owner in all_fields if set(owner.aliases) & set(alias_hits)]
        if len(set(owners)) > 1:
            return CompatibilityClassification.AMBIGUOUS
        return CompatibilityClassification.ALIAS_MATCH
    return CompatibilityClassification.REF_ONLY


def _field_entity(field: ProjectedCharacteristicField, classification: CompatibilityClassification) -> ProjectionEntity:
    return ProjectionEntity(
        entity_id=field.normalized_code,
        entity_type="characteristic_field",
        source_package_id=REF2A_PACKAGE_ID,
        classification=classification,
        payload=field.as_dict(),
    )


def _build_profile_assignment_matrix(
    profiles: list[ProjectedCharacteristicProfile],
    assignments: list[ProjectedProfileAssignment],
    runtime: dict[str, Any],
) -> list[ProjectionEntity]:
    entities: list[ProjectionEntity] = []
    runtime_schema_ids = set(runtime["schemas"])
    profile_ids = {profile.normalized_code for profile in profiles}
    for profile in profiles:
        entities.append(
            ProjectionEntity(
                entity_id=profile.normalized_code,
                entity_type="characteristic_profile",
                source_package_id=REF2B_PACKAGE_ID,
                classification=CompatibilityClassification.REF_ONLY,
                payload=profile.as_dict(),
            )
        )
    for runtime_schema in sorted(runtime_schema_ids - profile_ids):
        entities.append(
            ProjectionEntity(
                entity_id=runtime_schema,
                entity_type="characteristic_profile",
                source_package_id="runtime",
                classification=CompatibilityClassification.RUNTIME_ONLY,
                payload={"normalized_code": runtime_schema},
            )
        )
    for assignment in assignments:
        material_type_code = normalize_code(assignment.material_type_id)
        classification = CompatibilityClassification.EXACT_MATCH if material_type_code in runtime_schema_ids else CompatibilityClassification.REF_ONLY
        payload = assignment.as_dict()
        payload.update(
            {
                "candidate_profile_id": normalize_code(assignment.profile_id),
                "confidence": 1.0 if classification is CompatibilityClassification.EXACT_MATCH else 0.35,
                "evidence": [
                    f"material_type_id={assignment.material_type_id}",
                    f"profile_id={assignment.profile_id}",
                    "review_required" if assignment.review_required else "draft_assignment",
                ],
                "classification": "REVIEW_REQUIRED" if assignment.review_required else classification.value,
            }
        )
        entities.append(
            ProjectionEntity(
                entity_id=assignment.normalized_code,
                entity_type="profile_assignment",
                source_package_id=REF2B_PACKAGE_ID,
                classification=classification,
                payload=payload,
            )
        )
    return entities


def _build_counts(
    fields: tuple[ProjectedCharacteristicField, ...],
    profiles: tuple[ProjectedCharacteristicProfile, ...],
    assignments: tuple[ProjectedProfileAssignment, ...],
    runtime: dict[str, Any],
    field_matrix: tuple[ProjectionEntity, ...],
    profile_assignment_matrix: tuple[ProjectionEntity, ...],
    issues: tuple[ProjectionIssue, ...],
    ref2b_payload: dict[str, Any],
) -> dict[str, int]:
    field_entities = [entity for entity in field_matrix if entity.entity_type == "characteristic_field"]
    field_counts = Counter(entity.classification.value for entity in field_entities)
    ref_field_codes = {field.normalized_code for field in fields}
    runtime_field_codes = set(runtime["fields"])
    profile_entities = [entity for entity in profile_assignment_matrix if entity.entity_type == "characteristic_profile"]
    assignment_entities = [entity for entity in profile_assignment_matrix if entity.entity_type == "profile_assignment"]
    profile_counts = Counter(entity.classification.value for entity in profile_entities)
    assignment_counts = Counter(entity.classification.value for entity in assignment_entities)
    review_queue = ref2b_payload.get("review_queue") if isinstance(ref2b_payload.get("review_queue"), list) else []
    return {
        "ref_fields": len(fields),
        "runtime_fields": len(runtime["fields"]),
        "field_overlap": field_counts["EXACT_MATCH"],
        "field_alias_candidates": field_counts["ALIAS_MATCH"],
        "field_ambiguous": field_counts["AMBIGUOUS"],
        "field_ref_only": len(ref_field_codes - runtime_field_codes),
        "field_ref_only_classified": field_counts["REF_ONLY"],
        "field_runtime_only": len(runtime_field_codes - ref_field_codes),
        "field_type_mismatches": field_counts["INCOMPATIBLE_TYPE"],
        "field_unit_mismatches": field_counts["INCOMPATIBLE_UNIT"],
        "runtime_schemas": len(runtime["schemas"]),
        "profiles": len(profiles),
        "profile_ref_only": profile_counts["REF_ONLY"],
        "profile_runtime_only": profile_counts["RUNTIME_ONLY"],
        "assignments": len(assignments),
        "assignment_overlap": assignment_counts["EXACT_MATCH"],
        "assignment_ref_only": assignment_counts["REF_ONLY"],
        "review_required_assignments": len(review_queue),
        "review_auto_activatable": sum(1 for assignment in assignments if assignment.review_required and assignment.auto_activatable),
        "packaging_ref2_mismatches": KNOWN_PACKAGING_REF2_MISMATCHES,
        "broken_references": sum(1 for issue in issues if issue.severity is IssueSeverity.BLOCKER),
        "issues": len(issues),
        "blockers": sum(1 for issue in issues if issue.severity is IssueSeverity.BLOCKER),
        "warnings": sum(1 for issue in issues if issue.severity is IssueSeverity.WARNING),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_report(result: Ref2ProjectionResult) -> str:
    lines = ["# REF-2 Fields, Profiles and Assignments Projection", "", "## Counts"]
    for key, value in result.counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Isolation",
            "- REF-2B records are diagnostic only.",
            "- review_required assignments are not auto activatable.",
            "- Production runtime registries are not changed.",
            "",
            "## Packaging Mismatches",
            f"- Known packaging/REF-2 mismatches carried forward as diagnostics: {KNOWN_PACKAGING_REF2_MISMATCHES}.",
        ]
    )
    return "\n".join(lines) + "\n"
