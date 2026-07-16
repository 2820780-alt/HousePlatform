from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import RefPackageLoader
from .models import (
    CompatibilityClassification,
    IssueSeverity,
    ProjectedConsumptionRule,
    ProjectedCoverageRule,
    ProjectedGeometryRule,
    ProjectedPackagingRule,
    ProjectedYieldRule,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
)
from .ref1 import REF1_FILENAME, normalize_code
from .ref2 import REF2A_FILENAME, REF2B_FILENAME
from .ref3_units import REF3A_FILENAME

REF3B_PACKAGE_ID = "REF-3B"
REF3C_PACKAGE_ID = "REF-3C"
REF3B_FILENAME = "ATOM_REF3_Packaging_Quantity_Profiles_v1_DRAFT.json"
REF3C_FILENAME = "ATOM_REF3_Geometry_Coverage_Consumption_Rules_v1_DRAFT.json"
DEFAULT_WORK_CATALOG_PATH = Path(__file__).resolve().parents[2] / "src" / "modules" / "module1" / "seeds" / "work_catalog_seed.json"


@dataclass(frozen=True)
class Ref3ExtendedProjectionResult:
    sources: tuple[ProjectionSource, ...]
    packaging_rules: tuple[ProjectedPackagingRule, ...]
    geometry_rules: tuple[ProjectedGeometryRule, ...]
    coverage_rules: tuple[ProjectedCoverageRule, ...]
    yield_rules: tuple[ProjectedYieldRule, ...]
    consumption_rules: tuple[ProjectedConsumptionRule, ...]
    matrix: tuple[ProjectionEntity, ...]
    packaging_mismatches: tuple[dict[str, Any], ...]
    issues: tuple[ProjectionIssue, ...]
    counts: dict[str, int]

    def summary_dict(self) -> dict[str, Any]:
        return {"sources": [source.as_dict() for source in self.sources], "counts": self.counts}


def project_ref3_extended(
    reference_root: str | Path,
    work_catalog_path: str | Path = DEFAULT_WORK_CATALOG_PATH,
) -> Ref3ExtendedProjectionResult:
    reference_root = Path(reference_root)
    work_catalog_path = Path(work_catalog_path)
    ref1 = _read_json(reference_root / REF1_FILENAME)
    ref2a = _read_json(reference_root / REF2A_FILENAME)
    ref2b = _read_json(reference_root / REF2B_FILENAME)
    ref3a = _read_json(reference_root / REF3A_FILENAME)
    ref3b = _read_json(reference_root / REF3B_FILENAME)
    ref3c = _read_json(reference_root / REF3C_FILENAME)
    work_catalog = _read_json(work_catalog_path) if work_catalog_path.exists() else {"groups": [], "works": []}
    sources = _projection_sources(reference_root)
    source_by_id = {source.package_id: source for source in sources}
    source_b = source_by_id.get(REF3B_PACKAGE_ID, ProjectionSource(REF3B_PACKAGE_ID, "UNKNOWN", "UNKNOWN", reference_root / REF3B_FILENAME))
    source_c = source_by_id.get(REF3C_PACKAGE_ID, ProjectionSource(REF3C_PACKAGE_ID, "UNKNOWN", "UNKNOWN", reference_root / REF3C_FILENAME))

    material_types = {normalize_code(item.get("material_type_id")) for item in ref1.get("material_types", []) if item.get("material_type_id")}
    profile_ids = {normalize_code(item.get("profile_id")) for item in ref2b.get("profiles", []) if item.get("profile_id")}
    field_codes = {normalize_code(item.get("field_code")) for item in ref2a.get("fields", []) if item.get("field_code")}
    unit_codes = {str(item.get("unit_code")) for item in ref3a.get("units", []) if item.get("unit_code")}
    legacy_field_aliases = _legacy_field_aliases(ref2a, ref3c)

    review_materials = {normalize_code(item.get("material_type_id")) for item in ref3b.get("review_queue", []) if item.get("material_type_id")}
    packaging_profiles = _project_packaging_profiles(ref3b, source_b)
    packaging_assignments = _project_packaging_assignments(ref3b, source_b, review_materials)
    packaging_rules = tuple(sorted(packaging_profiles + packaging_assignments, key=lambda item: (item.rule_kind, item.normalized_code)))
    geometry_rules = tuple(sorted(_project_geometry_rules(ref3c, source_c), key=lambda item: item.normalized_code))
    coverage_rules, yield_rules, consumption_rules = _project_coverage_yield_consumption_rules(ref3c, source_c)

    issues: list[ProjectionIssue] = []
    issues.extend(_duplicate_issues("REF3B_DUPLICATE_PACKAGING_PROFILE", packaging_profiles, source_b))
    issues.extend(_duplicate_issues("REF3B_DUPLICATE_PACKAGING_ASSIGNMENT", packaging_assignments, source_b))
    issues.extend(_duplicate_issues("REF3C_DUPLICATE_GEOMETRY_RULE", list(geometry_rules), source_c))
    issues.extend(_duplicate_issues("REF3C_DUPLICATE_COVERAGE_RULE", list(coverage_rules + yield_rules + consumption_rules), source_c))
    packaging_profile_ids = {normalize_code(item.profile_id) for item in packaging_profiles if item.profile_id}
    issues.extend(_validate_packaging_rules(packaging_rules, material_types, packaging_profile_ids, unit_codes))
    issues.extend(_validate_extended_rules(list(geometry_rules + coverage_rules + yield_rules + consumption_rules), field_codes, unit_codes, legacy_field_aliases))
    issues.extend(_validate_rule_assignments(ref3c, source_c, material_types, {rule.source_code for rule in geometry_rules}, {rule.source_code for rule in coverage_rules + yield_rules + consumption_rules}))

    packaging_mismatches = tuple(_build_packaging_mismatches(ref3b, ref2b))
    work_counts = _work_catalog_counts(work_catalog)
    matrix = _build_matrix(packaging_rules, geometry_rules, coverage_rules, yield_rules, consumption_rules)
    sorted_issues = tuple(sorted(issues, key=lambda item: (item.code, item.entity_id or "", item.message)))
    counts = _build_counts(packaging_rules, geometry_rules, coverage_rules, yield_rules, consumption_rules, packaging_mismatches, sorted_issues, ref3b, work_counts)
    return Ref3ExtendedProjectionResult(
        sources=sources,
        packaging_rules=packaging_rules,
        geometry_rules=geometry_rules,
        coverage_rules=coverage_rules,
        yield_rules=yield_rules,
        consumption_rules=consumption_rules,
        matrix=matrix,
        packaging_mismatches=packaging_mismatches,
        issues=sorted_issues,
        counts=counts,
    )


def write_ref3_extended_projection_outputs(
    reference_root: str | Path,
    output_dir: str | Path,
    work_catalog_path: str | Path = DEFAULT_WORK_CATALOG_PATH,
) -> Ref3ExtendedProjectionResult:
    result = project_ref3_extended(reference_root, work_catalog_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "ref3_extended_summary.json", result.summary_dict())
    _write_json(output_dir / "ref3_extended_matrix.json", [entity.as_dict() for entity in result.matrix])
    _write_json(output_dir / "ref3_extended_issues.json", [issue.as_dict() for issue in result.issues])
    _write_json(output_dir / "ref3_packaging_mismatches.json", list(result.packaging_mismatches))
    (output_dir / "ref3_extended_report.md").write_text(_build_report(result), encoding="utf-8")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _projection_sources(reference_root: Path) -> tuple[ProjectionSource, ...]:
    summary = RefPackageLoader(reference_root, {REF3B_PACKAGE_ID: REF3B_FILENAME, REF3C_PACKAGE_ID: REF3C_FILENAME}).load()
    return tuple(sorted(summary.sources, key=lambda item: item.package_id))



def _project_packaging_profiles(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedPackagingRule]:
    result: list[ProjectedPackagingRule] = []
    for index, item in enumerate(payload.get("packaging_profiles", [])):
        profile_id = str(item.get("profile_id") or "")
        fields = _normalized_tuple((item.get("required_fields") or []) + (item.get("recommended_fields") or []))
        units = _string_tuple((item.get("primary_quantity_units") or []) + (item.get("allowed_price_basis_units") or []) + (item.get("allowed_package_units") or []))
        result.append(
            ProjectedPackagingRule(
                source=source,
                source_code=profile_id,
                normalized_code=normalize_code(profile_id),
                title=str(item.get("name_ru") or profile_id),
                rule_kind="packaging_profile",
                profile_id=profile_id,
                field_codes=fields,
                unit_codes=units,
                auto_activatable=False,
                source_pointer=f"/packaging_profiles/{index}",
            )
        )
    return result


def _project_packaging_assignments(payload: dict[str, Any], source: ProjectionSource, review_materials: set[str]) -> list[ProjectedPackagingRule]:
    result: list[ProjectedPackagingRule] = []
    for index, item in enumerate(payload.get("material_type_assignments", [])):
        material_type_id = str(item.get("material_type_id") or "")
        profile_id = str(item.get("packaging_profile_id") or "")
        fields = _normalized_tuple((item.get("required_packaging_fields") or []) + (item.get("recommended_packaging_fields") or []))
        units = _string_tuple((item.get("allowed_quantity_units") or []) + (item.get("candidate_price_basis_units") or []) + ([item.get("preferred_quantity_unit")] if item.get("preferred_quantity_unit") else []))
        review_required = normalize_code(material_type_id) in review_materials or bool(item.get("review_flags"))
        source_code = f"{material_type_id}->{profile_id}"
        result.append(
            ProjectedPackagingRule(
                source=source,
                source_code=source_code,
                normalized_code=f"{normalize_code(material_type_id)}__{normalize_code(profile_id)}",
                title=str(item.get("clean_name_ru") or material_type_id),
                rule_kind="packaging_assignment",
                material_type_id=material_type_id,
                profile_id=profile_id,
                field_codes=fields,
                unit_codes=units,
                review_required=review_required,
                auto_activatable=False,
                issues=tuple(["review_required"] if review_required else []),
                source_pointer=f"/material_type_assignments/{index}",
            )
        )
    return result


def _project_geometry_rules(payload: dict[str, Any], source: ProjectionSource) -> list[ProjectedGeometryRule]:
    result: list[ProjectedGeometryRule] = []
    for index, item in enumerate(payload.get("geometry_rules", [])):
        rule_id = str(item.get("rule_id") or "")
        result.append(
            ProjectedGeometryRule(
                source=source,
                source_code=rule_id,
                normalized_code=normalize_code(rule_id),
                title=str(item.get("name_ru") or rule_id),
                semantic_type=str(item.get("semantic_type") or "UNKNOWN"),
                field_codes=_rule_field_codes(item),
                unit_codes=_rule_unit_codes(item),
                formula_inputs=_formula_names(item.get("formula_inputs")),
                formula_outputs=_formula_names(item.get("formula_outputs")),
                auto_activatable=False,
                issues=_rule_issues(item),
                source_pointer=f"/geometry_rules/{index}",
            )
        )
    return result


def _project_coverage_yield_consumption_rules(payload: dict[str, Any], source: ProjectionSource) -> tuple[tuple[ProjectedCoverageRule, ...], tuple[ProjectedYieldRule, ...], tuple[ProjectedConsumptionRule, ...]]:
    coverage: list[ProjectedCoverageRule] = []
    yields: list[ProjectedYieldRule] = []
    consumption: list[ProjectedConsumptionRule] = []
    for index, item in enumerate(payload.get("coverage_consumption_rules", [])):
        rule_id = str(item.get("rule_id") or "")
        semantic_type = str(item.get("semantic_type") or "UNKNOWN")
        kwargs = {
            "source": source,
            "source_code": rule_id,
            "normalized_code": normalize_code(rule_id),
            "title": str(item.get("name_ru") or rule_id),
            "semantic_type": semantic_type,
            "field_codes": _rule_field_codes(item),
            "unit_codes": _rule_unit_codes(item),
            "formula_inputs": _formula_names(item.get("formula_inputs")),
            "formula_outputs": _formula_names(item.get("formula_outputs")),
            "auto_activatable": False,
            "issues": _rule_issues(item),
            "source_pointer": f"/coverage_consumption_rules/{index}",
        }
        if "yield" in semantic_type:
            yields.append(ProjectedYieldRule(**kwargs))
        elif "coverage" in semantic_type:
            coverage.append(ProjectedCoverageRule(**kwargs))
        else:
            consumption.append(ProjectedConsumptionRule(**kwargs))
    return (tuple(sorted(coverage, key=lambda item: item.normalized_code)), tuple(sorted(yields, key=lambda item: item.normalized_code)), tuple(sorted(consumption, key=lambda item: item.normalized_code)))


def _validate_packaging_rules(packaging_rules: tuple[ProjectedPackagingRule, ...], material_types: set[str], profile_ids: set[str], unit_codes: set[str]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    for rule in packaging_rules:
        if rule.rule_kind == "packaging_assignment":
            if normalize_code(rule.material_type_id) not in material_types:
                issues.append(_issue("REF3B_UNKNOWN_MATERIAL_TYPE", IssueSeverity.BLOCKER, f"Unknown material type {rule.material_type_id!r}", rule))
            if normalize_code(rule.profile_id) not in profile_ids:
                issues.append(_issue("REF3B_UNKNOWN_PACKAGING_PROFILE", IssueSeverity.BLOCKER, f"Unknown packaging profile {rule.profile_id!r}", rule))
        for unit_code in rule.unit_codes:
            if unit_code not in unit_codes:
                issues.append(_issue("REF3B_UNKNOWN_UNIT", IssueSeverity.BLOCKER, f"Unknown unit {unit_code!r}", rule))
    return issues


def _validate_extended_rules(rules: list[Any], field_codes: set[str], unit_codes: set[str], legacy_field_aliases: dict[str, str]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    for rule in rules:
        for field_code in rule.field_codes:
            resolved = legacy_field_aliases.get(field_code, field_code)
            if resolved not in field_codes:
                issues.append(_issue("REF3C_UNKNOWN_FIELD", IssueSeverity.BLOCKER, f"Unknown field {field_code!r}", rule))
        for unit_code in rule.unit_codes:
            if unit_code not in unit_codes:
                issues.append(_issue("REF3C_UNKNOWN_UNIT", IssueSeverity.BLOCKER, f"Unknown unit {unit_code!r}", rule))
        if "missing_formula_declaration" in getattr(rule, "issues", ()):
            issues.append(_issue("REF3C_MISSING_FORMULA_DECLARATION", IssueSeverity.BLOCKER, "Formula-bearing rule has no declared inputs or outputs", rule))
    return issues


def _validate_rule_assignments(payload: dict[str, Any], source: ProjectionSource, material_types: set[str], geometry_rule_ids: set[str], coverage_rule_ids: set[str]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    for index, item in enumerate(payload.get("material_type_rule_assignments", [])):
        material_type_id = str(item.get("material_type_id") or "")
        entity = _synthetic_entity(source, material_type_id, f"/material_type_rule_assignments/{index}")
        if normalize_code(material_type_id) not in material_types:
            issues.append(_issue("REF3C_ASSIGNMENT_UNKNOWN_MATERIAL_TYPE", IssueSeverity.BLOCKER, f"Unknown material type {material_type_id!r}", entity))
        for rule_id in item.get("geometry_rule_ids") or []:
            if str(rule_id) not in geometry_rule_ids:
                issues.append(_issue("REF3C_ASSIGNMENT_UNKNOWN_GEOMETRY_RULE", IssueSeverity.BLOCKER, f"Unknown geometry rule {rule_id!r}", entity))
        for rule_id in item.get("coverage_consumption_rule_ids") or []:
            if str(rule_id) not in coverage_rule_ids:
                issues.append(_issue("REF3C_ASSIGNMENT_UNKNOWN_COVERAGE_RULE", IssueSeverity.BLOCKER, f"Unknown coverage/consumption rule {rule_id!r}", entity))
    return issues



def _build_packaging_mismatches(ref3b: dict[str, Any], ref2b: dict[str, Any]) -> list[dict[str, Any]]:
    ref2_fields = {str(item.get("material_type_id") or ""): set(item.get("all_field_codes") or []) for item in ref2b.get("material_type_assignments", [])}
    mismatches: list[dict[str, Any]] = []
    for item in ref3b.get("material_type_assignments", []):
        material_type_id = str(item.get("material_type_id") or "")
        ref2 = ref2_fields.get(material_type_id, set())
        for field_code in item.get("required_packaging_fields") or []:
            if field_code not in ref2:
                mismatches.append(
                    {
                        "material_type_id": material_type_id,
                        "packaging_profile_id": item.get("packaging_profile_id"),
                        "field_code": field_code,
                        "mismatch_type": "required_packaging_field_missing_from_ref2_profile",
                        "source_pointer": item.get("source_pointer"),
                    }
                )
    return sorted(mismatches, key=lambda item: (item["material_type_id"], item["field_code"]))


def _build_matrix(packaging_rules: tuple[ProjectedPackagingRule, ...], geometry_rules: tuple[ProjectedGeometryRule, ...], coverage_rules: tuple[ProjectedCoverageRule, ...], yield_rules: tuple[ProjectedYieldRule, ...], consumption_rules: tuple[ProjectedConsumptionRule, ...]) -> tuple[ProjectionEntity, ...]:
    entities: list[ProjectionEntity] = []
    for rule in packaging_rules:
        classification = CompatibilityClassification.REVIEW_REQUIRED if rule.review_required else CompatibilityClassification.REF_ONLY
        entities.append(ProjectionEntity(rule.normalized_code, rule.rule_kind, rule.source.package_id, classification, rule.as_dict()))
    for entity_type, rules in (
        ("geometry_rule", geometry_rules),
        ("coverage_rule", coverage_rules),
        ("yield_rule", yield_rules),
        ("consumption_rule", consumption_rules),
    ):
        for rule in rules:
            entities.append(ProjectionEntity(rule.normalized_code, entity_type, rule.source.package_id, CompatibilityClassification.REF_ONLY, rule.as_dict()))
    return tuple(sorted(entities, key=lambda item: (item.entity_type, item.entity_id)))


def _build_counts(packaging_rules: tuple[ProjectedPackagingRule, ...], geometry_rules: tuple[ProjectedGeometryRule, ...], coverage_rules: tuple[ProjectedCoverageRule, ...], yield_rules: tuple[ProjectedYieldRule, ...], consumption_rules: tuple[ProjectedConsumptionRule, ...], packaging_mismatches: tuple[dict[str, Any], ...], issues: tuple[ProjectionIssue, ...], ref3b: dict[str, Any], work_counts: dict[str, int]) -> dict[str, int]:
    packaging_profiles = [rule for rule in packaging_rules if rule.rule_kind == "packaging_profile"]
    packaging_assignments = [rule for rule in packaging_rules if rule.rule_kind == "packaging_assignment"]
    return {
        "packaging_profiles": len(packaging_profiles),
        "packaging_assignments": len(packaging_assignments),
        "packaging_ref2_mismatches": len(packaging_mismatches),
        "ref3b_review_required": len(ref3b.get("review_queue") or []),
        "ref3b_review_auto_activatable": sum(1 for rule in packaging_assignments if rule.review_required and rule.auto_activatable),
        "geometry_rules": len(geometry_rules),
        "coverage_rules": len(coverage_rules),
        "yield_rules": len(yield_rules),
        "consumption_rules": len(consumption_rules),
        "work_groups": work_counts["work_groups"],
        "works": work_counts["works"],
        "executable_work_material_mappings_before": work_counts["executable_work_material_mappings"],
        "executable_work_material_mappings_after": work_counts["executable_work_material_mappings"],
        "issues": len(issues),
        "blockers": sum(1 for issue in issues if issue.severity is IssueSeverity.BLOCKER),
        "warnings": sum(1 for issue in issues if issue.severity is IssueSeverity.WARNING),
    }


def _work_catalog_counts(payload: dict[str, Any]) -> dict[str, int]:
    executable = 0
    for work in payload.get("works", []) or []:
        if not isinstance(work, dict):
            continue
        if any(key in work for key in ("material_type_id", "material_role", "material_role_id", "material_mappings")):
            executable += 1
    return {"work_groups": len(payload.get("groups") or []), "works": len(payload.get("works") or []), "executable_work_material_mappings": executable}


def _duplicate_issues(code: str, items: list[Any], source: ProjectionSource) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    for normalized_code, count in Counter(item.normalized_code for item in items if item.normalized_code).items():
        if count > 1:
            issues.append(ProjectionIssue(code=code, severity=IssueSeverity.BLOCKER, message=f"Duplicate normalized code: {normalized_code}", source_path=source.path, package_id=source.package_id, entity_id=normalized_code))
    return issues


def _rule_field_codes(item: dict[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for key in ("required_fields",):
        values.update(normalize_code(value) for value in item.get(key) or [] if normalize_code(value))
    for key in ("output_field", "rate_field"):
        if normalize_code(item.get(key)):
            values.add(normalize_code(item.get(key)))
    for part in (item.get("formula_inputs") or []) + (item.get("formula_outputs") or []):
        if not isinstance(part, dict) or not normalize_code(part.get("field_code")):
            continue
        if part.get("source") in (None, "material_field"):
            values.add(normalize_code(part.get("field_code")))
    return tuple(sorted(values))


def _rule_unit_codes(item: dict[str, Any]) -> tuple[str, ...]:
    values: set[str] = set()
    for key in ("output_unit", "rate_unit"):
        if item.get(key):
            values.add(str(item[key]))
    for part in (item.get("formula_inputs") or []) + (item.get("formula_outputs") or []):
        if isinstance(part, dict) and part.get("unit_code"):
            values.add(str(part["unit_code"]))
    return tuple(sorted(values))


def _rule_issues(item: dict[str, Any]) -> tuple[str, ...]:
    has_formula = bool(item.get("formula") or item.get("formula_hint"))
    has_declarations = bool(item.get("formula_inputs") or item.get("formula_outputs"))
    return tuple(["missing_formula_declaration"] if has_formula and not has_declarations else [])


def _formula_names(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    names = [str(item.get("name")) for item in value if isinstance(item, dict) and item.get("name")]
    return tuple(sorted(names))


def _legacy_field_aliases(ref2a: dict[str, Any], ref3c: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source in (ref2a.get("legacy_field_aliases") or [], (ref3c.get("legacy_field_aliases") or {}).items()):
        if isinstance(source, list):
            for item in source:
                if isinstance(item, dict) and item.get("legacy_field_code") and item.get("canonical_field_code"):
                    result[normalize_code(item["legacy_field_code"])] = normalize_code(item["canonical_field_code"])
        else:
            for legacy, item in source:
                if isinstance(item, dict) and item.get("canonical_field_code"):
                    result[normalize_code(legacy)] = normalize_code(item["canonical_field_code"])
    return result


def _normalized_tuple(values: list[Any]) -> tuple[str, ...]:
    return tuple(sorted({normalize_code(str(value)) for value in values if normalize_code(str(value))}))


def _string_tuple(values: list[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if value}))


def _synthetic_entity(source: ProjectionSource, source_code: str, source_pointer: str) -> Any:
    return ProjectedPackagingRule(source=source, source_code=source_code, normalized_code=normalize_code(source_code), title=source_code, rule_kind="synthetic", source_pointer=source_pointer)


def _issue(code: str, severity: IssueSeverity, message: str, item: Any) -> ProjectionIssue:
    return ProjectionIssue(code=code, severity=severity, message=message, source_path=item.source.path, package_id=item.source.package_id, entity_id=item.source_code)


def _build_report(result: Ref3ExtendedProjectionResult) -> str:
    lines = ["# REF-3 Extended Rules Projection", "", "## Counts"]
    for key, value in result.counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Isolation",
        "- REF-3B/REF-3C records are diagnostic projection records only.",
        "- Packaging/REF-2 mismatches are reported, not fixed.",
        "- REF-3B review records are not auto activatable.",
        "- Work-material executable mappings are not created.",
    ])
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
