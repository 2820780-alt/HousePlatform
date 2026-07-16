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
    ProjectedMaterialGroup,
    ProjectedMaterialType,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
)


REF1_PACKAGE_ID = "REF-1"
REF1_FILENAME = "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json"
DEFAULT_RUNTIME_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"
)


@dataclass(frozen=True)
class Ref1ProjectionResult:
    source: ProjectionSource
    groups: tuple[ProjectedMaterialGroup, ...]
    material_types: tuple[ProjectedMaterialType, ...]
    compatibility_matrix: tuple[ProjectionEntity, ...]
    issues: tuple[ProjectionIssue, ...]
    counts: dict[str, int]

    def summary_dict(self) -> dict[str, Any]:
        return {"source": self.source.as_dict(), "counts": self.counts}


def normalize_code(value: str | None) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return cleaned.strip("_")


def project_ref1_taxonomy(
    reference_root: str | Path,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
) -> Ref1ProjectionResult:
    reference_root = Path(reference_root)
    runtime_taxonomy_path = Path(runtime_taxonomy_path)
    payload = _read_json(reference_root / REF1_FILENAME)
    source = _projection_source(reference_root)
    runtime_groups, runtime_type_to_group = _load_runtime_taxonomy(runtime_taxonomy_path)
    groups = _project_groups(payload, source)
    material_types = _project_material_types(payload, source)
    issues = _validate_ref1(groups, material_types)
    compatibility_matrix, comparison_issues = _build_compatibility_matrix(
        groups, material_types, runtime_groups, runtime_type_to_group
    )
    issues.extend(comparison_issues)
    sorted_issues = tuple(sorted(issues, key=lambda item: (item.code, item.entity_id or "", item.message)))
    sorted_matrix = tuple(sorted(compatibility_matrix, key=lambda item: (item.entity_type, item.entity_id, item.classification.value)))
    counts = _build_counts(groups, material_types, runtime_groups, runtime_type_to_group, sorted_matrix, sorted_issues)
    return Ref1ProjectionResult(
        source=source,
        groups=tuple(sorted(groups, key=lambda item: item.normalized_code)),
        material_types=tuple(sorted(material_types, key=lambda item: item.normalized_code)),
        compatibility_matrix=sorted_matrix,
        issues=sorted_issues,
        counts=counts,
    )


def write_ref1_projection_outputs(
    reference_root: str | Path,
    output_dir: str | Path,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
) -> Ref1ProjectionResult:
    result = project_ref1_taxonomy(reference_root, runtime_taxonomy_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "ref1_projection_summary.json", result.summary_dict())
    _write_json(output_dir / "ref1_compatibility_matrix.json", [entity.as_dict() for entity in result.compatibility_matrix])
    _write_json(output_dir / "ref1_issues.json", [issue.as_dict() for issue in result.issues])
    (output_dir / "ref1_report.md").write_text(_build_report(result), encoding="utf-8")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _projection_source(reference_root: Path) -> ProjectionSource:
    summary = RefPackageLoader(reference_root, {REF1_PACKAGE_ID: REF1_FILENAME}).load()
    for source in summary.sources:
        if source.package_id == REF1_PACKAGE_ID:
            return source
    return ProjectionSource(package_id=REF1_PACKAGE_ID, version="UNKNOWN", status="UNKNOWN", path=reference_root / REF1_FILENAME)


def _load_runtime_taxonomy(path: Path) -> tuple[set[str], dict[str, str]]:
    payload = _read_json(path)
    runtime_groups: set[str] = set()
    runtime_types: dict[str, str] = {}
    for group in payload.get("taxonomy", []):
        group_code = normalize_code(group.get("code"))
        if not group_code:
            continue
        runtime_groups.add(group_code)
        for child in group.get("children", []):
            runtime_types[normalize_code(child)] = group_code
    return runtime_groups, runtime_types


def _project_groups(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedMaterialGroup]:
    groups: list[ProjectedMaterialGroup] = []
    for index, item in enumerate(payload.get("groups", [])):
        source_code = str(item.get("group_id") or "")
        groups.append(
            ProjectedMaterialGroup(
                source=source,
                source_code=source_code,
                normalized_code=normalize_code(source_code),
                title=str(item.get("name_ru") or source_code),
                aliases=_aliases(item),
                status=str(item.get("lifecycle_status") or item.get("status") or "UNKNOWN"),
                source_pointer=f"/groups/{index}",
            )
        )
    return groups


def _project_material_types(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedMaterialType]:
    material_types: list[ProjectedMaterialType] = []
    for index, item in enumerate(payload.get("material_types", [])):
        source_code = str(item.get("material_type_id") or "")
        group_code = item.get("group_id")
        material_types.append(
            ProjectedMaterialType(
                source=source,
                source_code=source_code,
                normalized_code=normalize_code(source_code),
                title=str(item.get("clean_name_ru") or source_code),
                group_code=str(group_code) if group_code else None,
                normalized_group_code=normalize_code(str(group_code)) if group_code else None,
                aliases=_aliases(item),
                status=str(item.get("lifecycle_status") or item.get("authoring_status") or "UNKNOWN"),
                source_pointer=f"/material_types/{index}",
            )
        )
    return material_types


def _aliases(item: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("aliases", "alias_codes", "synonyms"):
        raw = item.get(key)
        if isinstance(raw, list):
            values.extend(str(value) for value in raw if value)
        elif isinstance(raw, str) and raw:
            values.append(raw)
    return tuple(sorted(normalize_code(value) for value in values if normalize_code(value)))


def _validate_ref1(groups: list[ProjectedMaterialGroup], material_types: list[ProjectedMaterialType]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    issues.extend(_duplicate_code_issues("material_group", groups))
    issues.extend(_duplicate_code_issues("material_type", material_types))
    issues.extend(_alias_issues("material_group", groups))
    issues.extend(_alias_issues("material_type", material_types))
    group_codes = {group.normalized_code for group in groups}
    for item in material_types:
        if not item.normalized_group_code:
            issues.append(_issue("REF1_TYPE_WITHOUT_GROUP", IssueSeverity.BLOCKER, "REF-1 material type has no group reference", item))
        elif item.normalized_group_code not in group_codes:
            issues.append(_issue("REF1_UNKNOWN_GROUP", IssueSeverity.BLOCKER, f"REF-1 material type references unknown group {item.group_code!r}", item))
    return issues


def _issue(code: str, severity: IssueSeverity, message: str, item: ProjectedMaterialGroup | ProjectedMaterialType) -> ProjectionIssue:
    return ProjectionIssue(code=code, severity=severity, message=message, source_path=item.source.path, package_id=REF1_PACKAGE_ID, entity_id=item.source_code)


def _duplicate_code_issues(entity_type: str, items: list[ProjectedMaterialGroup] | list[ProjectedMaterialType]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    for code, count in Counter(item.normalized_code for item in items if item.normalized_code).items():
        if count > 1:
            issues.append(ProjectionIssue(code="REF1_DUPLICATE_NORMALIZED_CODE", severity=IssueSeverity.BLOCKER, message=f"Duplicate normalized {entity_type} code: {code}", package_id=REF1_PACKAGE_ID, entity_id=code))
    return issues


def _alias_issues(entity_type: str, items: list[ProjectedMaterialGroup] | list[ProjectedMaterialType]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    alias_owner: dict[str, list[str]] = defaultdict(list)
    for item in items:
        for alias in item.aliases:
            alias_owner[alias].append(item.normalized_code)
        for alias, count in Counter(item.aliases).items():
            if count > 1:
                issues.append(_issue("REF1_DUPLICATE_ALIAS", IssueSeverity.WARNING, f"Duplicate alias {alias!r} inside {entity_type} {item.source_code!r}", item))
    for alias, owners in alias_owner.items():
        if len(set(owners)) > 1:
            issues.append(ProjectionIssue(code="REF1_ALIAS_COLLISION", severity=IssueSeverity.WARNING, message=f"Alias {alias!r} belongs to multiple {entity_type} records", package_id=REF1_PACKAGE_ID, entity_id=alias))
    return issues


def _build_compatibility_matrix(
    groups: list[ProjectedMaterialGroup],
    material_types: list[ProjectedMaterialType],
    runtime_groups: set[str],
    runtime_type_to_group: dict[str, str],
) -> tuple[list[ProjectionEntity], list[ProjectionIssue]]:
    entities: list[ProjectionEntity] = []
    issues: list[ProjectionIssue] = []
    ref_group_codes = {group.normalized_code for group in groups}
    ref_type_codes = {item.normalized_code for item in material_types}
    for group in groups:
        entities.append(_projection_entity("material_group", group.normalized_code, _classify_ref_item(group, runtime_groups, groups), group))
    for runtime_group in sorted(runtime_groups - ref_group_codes):
        entities.append(_runtime_only_entity("material_group", runtime_group))
    for item in material_types:
        classification = _classify_ref_item(item, set(runtime_type_to_group), material_types)
        if not item.normalized_group_code or item.normalized_group_code not in ref_group_codes:
            classification = CompatibilityClassification.INVALID_REFERENCE
        elif classification is CompatibilityClassification.EXACT_MATCH:
            runtime_group = runtime_type_to_group[item.normalized_code]
            if runtime_group != item.normalized_group_code:
                classification = CompatibilityClassification.STRUCTURE_MISMATCH
                issues.append(_issue("REF1_RUNTIME_GROUP_MISMATCH", IssueSeverity.WARNING, f"Runtime group {runtime_group!r} differs from REF-1 group {item.normalized_group_code!r}", item))
        entities.append(_projection_entity("material_type", item.normalized_code, classification, item))
    for runtime_type in sorted(set(runtime_type_to_group) - ref_type_codes):
        entities.append(_runtime_only_entity("material_type", runtime_type))
    return entities, issues


def _classify_ref_item(item: ProjectedMaterialGroup | ProjectedMaterialType, runtime_codes: set[str], all_items: list[ProjectedMaterialGroup] | list[ProjectedMaterialType]) -> CompatibilityClassification:
    if item.normalized_code in runtime_codes:
        return CompatibilityClassification.EXACT_MATCH
    alias_hits = [alias for alias in item.aliases if alias in runtime_codes]
    if alias_hits:
        owners = [owner.normalized_code for owner in all_items if set(owner.aliases) & set(alias_hits)]
        if len(set(owners)) > 1:
            return CompatibilityClassification.AMBIGUOUS
        return CompatibilityClassification.ALIAS_MATCH
    return CompatibilityClassification.REF_ONLY


def _projection_entity(entity_type: str, code: str, classification: CompatibilityClassification, item: ProjectedMaterialGroup | ProjectedMaterialType) -> ProjectionEntity:
    return ProjectionEntity(entity_id=code, entity_type=entity_type, source_package_id=REF1_PACKAGE_ID, classification=classification, payload=item.as_dict())


def _runtime_only_entity(entity_type: str, code: str) -> ProjectionEntity:
    return ProjectionEntity(entity_id=code, entity_type=entity_type, source_package_id="runtime", classification=CompatibilityClassification.RUNTIME_ONLY, payload={"normalized_code": code})


def _build_counts(groups: list[ProjectedMaterialGroup], material_types: list[ProjectedMaterialType], runtime_groups: set[str], runtime_type_to_group: dict[str, str], matrix: tuple[ProjectionEntity, ...], issues: tuple[ProjectionIssue, ...]) -> dict[str, int]:
    classifications = Counter(entity.classification.value for entity in matrix)
    return {
        "ref_groups": len(groups),
        "ref_types": len(material_types),
        "runtime_groups": len(runtime_groups),
        "runtime_types": len(runtime_type_to_group),
        "exact": classifications["EXACT_MATCH"],
        "alias_candidates": classifications["ALIAS_MATCH"],
        "ambiguous": classifications["AMBIGUOUS"],
        "ref_only": classifications["REF_ONLY"],
        "runtime_only": classifications["RUNTIME_ONLY"],
        "broken_references": sum(1 for issue in issues if issue.code in {"REF1_TYPE_WITHOUT_GROUP", "REF1_UNKNOWN_GROUP"}),
        "issues": len(issues),
        "blockers": sum(1 for issue in issues if issue.severity is IssueSeverity.BLOCKER),
        "warnings": sum(1 for issue in issues if issue.severity is IssueSeverity.WARNING),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_report(result: Ref1ProjectionResult) -> str:
    lines = ["# REF-1 Taxonomy Projection", "", f"Source: {result.source.path}", "", "## Counts"]
    for key, value in result.counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Notes", "- This report is generated by inactive tooling only.", "- No production runtime registries are changed."])
    return "\n".join(lines) + "\n"
