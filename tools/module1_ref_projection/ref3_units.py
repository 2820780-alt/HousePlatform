from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import RefPackageLoader
from .models import (
    CompatibilityClassification,
    IssueSeverity,
    ProjectedConversion,
    ProjectedUnit,
    ProjectionEntity,
    ProjectionIssue,
    ProjectionSource,
)

REF3A_PACKAGE_ID = "REF-3A"
REF3A_FILENAME = "ATOM_REF3_Unit_Dictionary_v1_DRAFT.json"
DEFAULT_RUNTIME_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"
DEFAULT_RUNTIME_UNIT_SERVICE_PATH = Path(__file__).resolve().parents[2] / "app" / "services" / "module1_unit_conversion_registry.py"


@dataclass(frozen=True)
class Ref3UnitProjectionResult:
    source: ProjectionSource
    units: tuple[ProjectedUnit, ...]
    conversions: tuple[ProjectedConversion, ...]
    unit_matrix: tuple[ProjectionEntity, ...]
    conversion_matrix: tuple[ProjectionEntity, ...]
    issues: tuple[ProjectionIssue, ...]
    counts: dict[str, int]

    def summary_dict(self) -> dict[str, Any]:
        return {"source": self.source.as_dict(), "counts": self.counts}


def project_ref3_units(
    reference_root: str | Path,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
    runtime_unit_service_path: str | Path = DEFAULT_RUNTIME_UNIT_SERVICE_PATH,
) -> Ref3UnitProjectionResult:
    reference_root = Path(reference_root)
    runtime_taxonomy_path = Path(runtime_taxonomy_path)
    runtime_unit_service_path = Path(runtime_unit_service_path)
    payload = _read_json(reference_root / REF3A_FILENAME)
    source = _projection_source(reference_root)
    runtime = _load_runtime_units_and_conversions(runtime_taxonomy_path, runtime_unit_service_path)
    review_unit_codes = {_unit_code(item) for item in payload.get("review_queue", []) if isinstance(item, dict)}
    review_unit_codes = {code for code in review_unit_codes if code}
    units = _project_units(payload, source, review_unit_codes)
    unit_by_code = {unit.source_code: unit for unit in units}
    ref_unit_codes = set(unit_by_code)
    runtime_unit_codes = set(runtime["units"])
    issues: list[ProjectionIssue] = []
    issues.extend(_validate_units(units, ref_unit_codes))
    unit_matrix, unit_matrix_issues = _build_unit_matrix(units, runtime_unit_codes)
    issues.extend(unit_matrix_issues)
    conversions = _project_conversions(runtime, source, unit_by_code, ref_unit_codes)
    conversion_matrix = tuple(
        ProjectionEntity(
            entity_id=item.normalized_code,
            entity_type="unit_conversion",
            source_package_id=item.source.package_id,
            classification=item.classification,
            payload=item.as_dict(),
        )
        for item in conversions
    )
    sorted_issues = tuple(sorted(issues, key=lambda item: (item.code, item.entity_id or "", item.message)))
    sorted_units = tuple(sorted(units, key=lambda item: item.source_code))
    sorted_conversions = tuple(sorted(conversions, key=lambda item: (item.source_type, item.normalized_code)))
    sorted_unit_matrix = tuple(sorted(unit_matrix, key=lambda item: (item.entity_type, item.entity_id, item.classification.value)))
    sorted_conversion_matrix = tuple(sorted(conversion_matrix, key=lambda item: (item.entity_type, item.entity_id, item.classification.value)))
    counts = _build_counts(sorted_units, sorted_conversions, sorted_unit_matrix, runtime_unit_codes, sorted_issues)
    return Ref3UnitProjectionResult(
        source=source,
        units=sorted_units,
        conversions=sorted_conversions,
        unit_matrix=sorted_unit_matrix,
        conversion_matrix=sorted_conversion_matrix,
        issues=sorted_issues,
        counts=counts,
    )


def write_ref3_unit_projection_outputs(
    reference_root: str | Path,
    output_dir: str | Path,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
    runtime_unit_service_path: str | Path = DEFAULT_RUNTIME_UNIT_SERVICE_PATH,
) -> Ref3UnitProjectionResult:
    result = project_ref3_units(reference_root, runtime_taxonomy_path, runtime_unit_service_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "ref3_units_summary.json", result.summary_dict())
    _write_json(output_dir / "ref3_unit_matrix.json", [entity.as_dict() for entity in result.unit_matrix])
    _write_json(output_dir / "ref3_conversion_matrix.json", [entity.as_dict() for entity in result.conversion_matrix])
    _write_json(output_dir / "ref3_units_issues.json", [issue.as_dict() for issue in result.issues])
    (output_dir / "ref3_units_report.md").write_text(_build_report(result), encoding="utf-8")
    return result


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _projection_source(reference_root: Path) -> ProjectionSource:
    summary = RefPackageLoader(reference_root, {REF3A_PACKAGE_ID: REF3A_FILENAME}).load()
    for source in summary.sources:
        if source.package_id == REF3A_PACKAGE_ID:
            return source
    return ProjectionSource(package_id=REF3A_PACKAGE_ID, version="UNKNOWN", status="UNKNOWN", path=reference_root / REF3A_FILENAME)


def _project_units(payload: dict[str, Any], source: ProjectionSource, review_unit_codes: set[str]) -> list[ProjectedUnit]:
    units: list[ProjectedUnit] = []
    for index, item in enumerate(payload.get("units", [])):
        if not isinstance(item, dict):
            continue
        source_code = _unit_code(item)
        if not source_code:
            continue
        aliases = tuple(sorted({_alias_key(alias) for alias in item.get("aliases") or [] if _alias_key(alias)}))
        review_required = source_code in review_unit_codes or bool(item.get("review_flag"))
        units.append(
            ProjectedUnit(
                source=source,
                source_code=source_code,
                normalized_code=source_code,
                title=str(item.get("label_ru") or source_code),
                symbol=_optional_string(item.get("symbol")),
                dimension=_optional_string(item.get("dimension")),
                base_unit_code=_optional_string(item.get("base_unit_code")),
                aliases=aliases,
                status=str(item.get("status") or "UNKNOWN"),
                review_required=review_required,
                auto_activatable=False,
                issues=tuple(["review_required"] if review_required else []),
                source_pointer=f"/units/{index}",
            )
        )
    return units


def _validate_units(units: list[ProjectedUnit], ref_unit_codes: set[str]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    source = units[0].source if units else ProjectionSource(REF3A_PACKAGE_ID, "UNKNOWN", "UNKNOWN", Path(REF3A_FILENAME))
    for unit_code, count in Counter(unit.source_code for unit in units).items():
        if count > 1:
            issues.append(_issue("REF3_DUPLICATE_UNIT_CODE", IssueSeverity.BLOCKER, f"Duplicate REF-3 unit code: {unit_code}", unit_code, source))
    alias_owners: dict[str, list[str]] = defaultdict(list)
    for unit in units:
        if unit.base_unit_code and unit.base_unit_code not in ref_unit_codes:
            issues.append(_issue("REF3_UNKNOWN_BASE_UNIT", IssueSeverity.WARNING, f"Unit references non-unit base dimension {unit.base_unit_code!r}", unit.source_code, unit.source))
        if not unit.dimension:
            issues.append(_issue("REF3_MISSING_DIMENSION", IssueSeverity.WARNING, "Unit has no dimension", unit.source_code, unit.source))
        if not unit.symbol:
            issues.append(_issue("REF3_MISSING_SYMBOL", IssueSeverity.WARNING, "Unit has no symbol", unit.source_code, unit.source))
        for alias in unit.aliases:
            alias_owners[alias].append(unit.source_code)
    for alias, owners in alias_owners.items():
        if len(set(owners)) > 1:
            issues.append(ProjectionIssue(code="REF3_ALIAS_COLLISION", severity=IssueSeverity.WARNING, message=f"Alias {alias!r} belongs to multiple REF-3 units", package_id=REF3A_PACKAGE_ID, entity_id=alias))
    return issues


def _build_unit_matrix(units: list[ProjectedUnit], runtime_units: set[str]) -> tuple[list[ProjectionEntity], list[ProjectionIssue]]:
    entities: list[ProjectionEntity] = []
    issues: list[ProjectionIssue] = []
    ref_codes = {unit.source_code for unit in units}
    for unit in units:
        classification = _classify_unit(unit, runtime_units, units)
        if classification is CompatibilityClassification.AMBIGUOUS:
            issues.append(_issue("REF3_AMBIGUOUS_UNIT_ALIAS", IssueSeverity.WARNING, "Unit alias matches more than one REF-3 unit", unit.source_code, unit.source))
        entities.append(ProjectionEntity(entity_id=unit.source_code, entity_type="unit", source_package_id=REF3A_PACKAGE_ID, classification=classification, payload=unit.as_dict()))
    for runtime_unit in sorted(runtime_units - ref_codes):
        entities.append(ProjectionEntity(entity_id=runtime_unit, entity_type="unit", source_package_id="runtime", classification=CompatibilityClassification.RUNTIME_ONLY, payload={"normalized_code": runtime_unit}))
    return entities, issues


def _classify_unit(unit: ProjectedUnit, runtime_units: set[str], all_units: list[ProjectedUnit]) -> CompatibilityClassification:
    if unit.review_required:
        return CompatibilityClassification.REVIEW_REQUIRED
    if unit.source_code in runtime_units:
        return CompatibilityClassification.EXACT_MATCH
    alias_hits = [alias for alias in unit.aliases if alias in runtime_units]
    if alias_hits:
        owners = [owner.source_code for owner in all_units if set(owner.aliases) & set(alias_hits)]
        if len(set(owners)) > 1:
            return CompatibilityClassification.AMBIGUOUS
        return CompatibilityClassification.ALIAS_MATCH
    return CompatibilityClassification.REF_ONLY


def _load_runtime_units_and_conversions(runtime_taxonomy_path: Path, runtime_unit_service_path: Path) -> dict[str, Any]:
    module = _load_runtime_unit_module(runtime_unit_service_path)
    unit_aliases = getattr(module, "UNIT_ALIASES", {})
    simple_factors = getattr(module, "SIMPLE_CONVERSION_FACTORS", {})
    technical_sets = getattr(module, "TECHNICAL_REQUIREMENT_SETS", {})
    seed_payload = _read_json(runtime_taxonomy_path)
    seed_conversions = seed_payload.get("unitConversions") or []
    units = tuple(sorted(str(unit) for unit in unit_aliases.keys()))
    alias_index = {str(alias): str(canonical) for canonical, aliases in unit_aliases.items() for alias in aliases}
    simple = [{"from": str(pair[0]), "to": str(pair[1]), "factor": str(factor), "source_type": "simple", "source_pointer": "SIMPLE_CONVERSION_FACTORS"} for pair, factor in simple_factors.items()]
    technical = [{"group": str(pair[0]), "from": str(pair[1]), "to": str(pair[2]), "required_parameters": tuple(tuple(str(field) for field in option) for option in requirement_sets), "source_type": "technical", "source_pointer": "TECHNICAL_REQUIREMENT_SETS"} for pair, requirement_sets in technical_sets.items()]
    seed = [{"group": str(item.get("group") or item.get("material_group") or ""), "from": _canonical_runtime_unit(item.get("from") or item.get("from_unit"), alias_index), "to": _canonical_runtime_unit(item.get("to") or item.get("to_unit"), alias_index), "formula": _optional_string(item.get("formula")), "fallback": _optional_string(item.get("fallback")), "source_type": "seed", "source_pointer": f"unitConversions/{index}"} for index, item in enumerate(seed_conversions) if isinstance(item, dict)]
    return {"units": units, "simple": tuple(simple), "technical": tuple(technical), "seed": tuple(seed)}


def _load_runtime_unit_module(path: Path) -> Any:
    module_name = f"_module1_unit_conversion_registry_projection_{abs(hash(path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load runtime unit registry from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module



def _project_conversions(runtime: dict[str, Any], source: ProjectionSource, unit_by_code: dict[str, ProjectedUnit], ref_unit_codes: set[str]) -> tuple[ProjectedConversion, ...]:
    simple_pairs = {(item["from"], item["to"]) for item in runtime["simple"]}
    conversions: list[ProjectedConversion] = []
    for item in runtime["simple"]:
        classification, issues = _classify_conversion(item, unit_by_code, ref_unit_codes, simple_pairs, source_type="simple")
        conversions.append(_conversion_from_item(source, item, "simple", classification, issues))
    for item in runtime["technical"]:
        classification, issues = _classify_conversion(item, unit_by_code, ref_unit_codes, simple_pairs, source_type="technical")
        conversions.append(_conversion_from_item(source, item, "technical", classification, issues))
    for item in runtime["seed"]:
        classification, issues = _classify_conversion(item, unit_by_code, ref_unit_codes, simple_pairs, source_type="seed")
        conversions.append(_conversion_from_item(source, item, "seed", classification, issues))
    return tuple(conversions)


def _classify_conversion(item: dict[str, Any], unit_by_code: dict[str, ProjectedUnit], ref_unit_codes: set[str], simple_pairs: set[tuple[str, str]], *, source_type: str) -> tuple[CompatibilityClassification, tuple[str, ...]]:
    from_unit = str(item.get("from") or "")
    to_unit = str(item.get("to") or "")
    missing = [unit for unit in (from_unit, to_unit) if unit not in ref_unit_codes]
    if missing:
        return CompatibilityClassification.UNIT_MISSING, tuple(f"missing_unit:{unit}" for unit in missing)
    if source_type == "simple" and _dimension_conflict(unit_by_code[from_unit], unit_by_code[to_unit]):
        return CompatibilityClassification.DIMENSION_CONFLICT, ("dimension_conflict",)
    if source_type == "simple":
        factor = _optional_string(item.get("factor"))
        if factor is None:
            return CompatibilityClassification.UNSAFE, ("missing_factor",)
        if (to_unit, from_unit) not in simple_pairs:
            return CompatibilityClassification.REVERSE_MISSING, ("reverse_missing",)
        return CompatibilityClassification.STRUCTURALLY_COMPATIBLE, tuple()
    if source_type == "seed" and item.get("formula"):
        return CompatibilityClassification.FORMULA_REQUIRED, ("formula_not_activated",)
    if source_type == "technical" and item.get("required_parameters"):
        return CompatibilityClassification.PARAMETER_REQUIRED, ("material_profile_required",)
    return CompatibilityClassification.UNSUPPORTED, ("unsupported_conversion",)


def _conversion_from_item(source: ProjectionSource, item: dict[str, Any], source_type: str, classification: CompatibilityClassification, issues: tuple[str, ...]) -> ProjectedConversion:
    material_group = _optional_string(item.get("group"))
    from_unit = str(item.get("from") or "")
    to_unit = str(item.get("to") or "")
    prefix = material_group + ":" if material_group else ""
    source_code = f"{prefix}{from_unit}->{to_unit}"
    return ProjectedConversion(
        source=source,
        source_code=source_code,
        normalized_code=f"{source_type}:{source_code}",
        from_unit=from_unit,
        to_unit=to_unit,
        source_type=source_type,
        material_group=material_group,
        factor=_optional_string(item.get("factor")),
        formula=_optional_string(item.get("formula")),
        required_parameters=tuple(item.get("required_parameters") or ()),
        classification=classification,
        auto_activatable=False,
        issues=issues,
        source_pointer=_optional_string(item.get("source_pointer")),
    )


def _dimension_conflict(from_unit: ProjectedUnit, to_unit: ProjectedUnit) -> bool:
    if not from_unit.dimension or not to_unit.dimension:
        return False
    if from_unit.base_unit_code and from_unit.base_unit_code in {to_unit.source_code, to_unit.base_unit_code}:
        return False
    if to_unit.base_unit_code and to_unit.base_unit_code in {from_unit.source_code, from_unit.base_unit_code}:
        return False
    return from_unit.dimension != to_unit.dimension


def _build_counts(units: tuple[ProjectedUnit, ...], conversions: tuple[ProjectedConversion, ...], unit_matrix: tuple[ProjectionEntity, ...], runtime_units: set[str], issues: tuple[ProjectionIssue, ...]) -> dict[str, int]:
    ref_unit_codes = {unit.source_code for unit in units}
    conversion_source_counts = Counter(item.source_type for item in conversions)
    conversion_class_counts = Counter(item.classification.value for item in conversions)
    unit_class_counts = Counter(entity.classification.value for entity in unit_matrix if entity.entity_type == "unit")
    return {
        "ref_units": len(units),
        "runtime_units": len(runtime_units),
        "exact": len(ref_unit_codes & runtime_units),
        "exact_classified": unit_class_counts["EXACT_MATCH"],
        "alias_candidates": unit_class_counts["ALIAS_MATCH"],
        "ambiguous": unit_class_counts["AMBIGUOUS"],
        "ref_only": len(ref_unit_codes - runtime_units),
        "runtime_only": len(runtime_units - ref_unit_codes),
        "review_required_units": sum(1 for unit in units if unit.review_required),
        "review_auto_activatable": sum(1 for unit in units if unit.review_required and unit.auto_activatable),
        "runtime_conversion_records": len(conversions),
        "runtime_conversion_simple": conversion_source_counts["simple"],
        "runtime_conversion_technical": conversion_source_counts["technical"],
        "runtime_conversion_seed": conversion_source_counts["seed"],
        "structurally_compatible": conversion_class_counts["STRUCTURALLY_COMPATIBLE"],
        "unit_missing_conversions": conversion_class_counts["UNIT_MISSING"],
        "reverse_missing_conversions": conversion_class_counts["REVERSE_MISSING"],
        "dimension_conflicts": conversion_class_counts["DIMENSION_CONFLICT"],
        "formula_required": conversion_class_counts["FORMULA_REQUIRED"],
        "parameter_required": conversion_class_counts["PARAMETER_REQUIRED"],
        "review_required_conversions": conversion_class_counts["REVIEW_REQUIRED"],
        "unsafe_conversions": conversion_class_counts["UNSAFE"],
        "issues": len(issues),
        "blockers": sum(1 for issue in issues if issue.severity is IssueSeverity.BLOCKER),
        "warnings": sum(1 for issue in issues if issue.severity is IssueSeverity.WARNING),
    }


def _build_report(result: Ref3UnitProjectionResult) -> str:
    lines = ["# REF-3 Units and Safe Conversion Projection", "", "## Counts"]
    for key, value in result.counts.items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Isolation",
        "- REF-3A units are diagnostic projection records only.",
        "- Runtime unit conversion registry is not changed.",
        "- Review units are not auto activatable.",
        "- Conversion classifications do not activate conversion records.",
    ])
    return "\n".join(lines) + "\n"


def _unit_code(item: dict[str, Any]) -> str:
    return str(item.get("unit_code") or item.get("code") or "")


def _canonical_runtime_unit(value: Any, alias_index: dict[str, str]) -> str:
    text = str(value or "").strip()
    cleaned = text.lower().replace("?", "2").replace("?", "3")
    return alias_index.get(cleaned) or alias_index.get(text) or text


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _alias_key(value: Any) -> str:
    return str(value).strip().lower().replace("?", "2").replace("?", "3")


def _issue(code: str, severity: IssueSeverity, message: str, entity_id: str, source: ProjectionSource) -> ProjectionIssue:
    return ProjectionIssue(code=code, severity=severity, message=message, source_path=source.path, package_id=source.package_id, entity_id=entity_id)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
