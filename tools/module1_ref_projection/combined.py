from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import IssueSeverity, ProjectionIssue, ProjectionSource, ProjectionSummary
from .ref1 import DEFAULT_RUNTIME_TAXONOMY_PATH, project_ref1_taxonomy, normalize_code
from .ref2 import project_ref2_characteristics
from .ref3_extended import DEFAULT_WORK_CATALOG_PATH, project_ref3_extended
from .ref3_units import DEFAULT_RUNTIME_UNIT_SERVICE_PATH, project_ref3_units
from .validator import ProjectionValidator


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CombinedProjectionResult:
    sources: tuple[ProjectionSource, ...]
    ref1: dict[str, Any] | None
    ref2: dict[str, Any] | None
    ref3_units: dict[str, Any] | None
    ref3_extended: dict[str, Any] | None
    counts: dict[str, Any]
    issues: tuple[ProjectionIssue, ...]
    runtime_isolation: dict[str, Any]
    combined_activation_allowed: bool
    activation_blockers: tuple[str, ...]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "sources": [source.as_dict() for source in self.sources],
            "counts": self.counts,
            "runtime_isolation": self.runtime_isolation,
            "combined_activation_allowed": self.combined_activation_allowed,
            "activation_blockers": list(self.activation_blockers),
            "ref1": self.ref1,
            "ref2": self.ref2,
            "ref3_units": self.ref3_units,
            "ref3_extended": self.ref3_extended,
        }

    def issues_dict(self) -> list[dict[str, Any]]:
        return [issue.as_dict() for issue in self.issues]


def project_combined_ref_validation(
    reference_root: str | Path,
    *,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
    runtime_unit_service_path: str | Path = DEFAULT_RUNTIME_UNIT_SERVICE_PATH,
    work_catalog_path: str | Path = DEFAULT_WORK_CATALOG_PATH,
    project_root: str | Path = PROJECT_ROOT,
) -> CombinedProjectionResult:
    reference_root = Path(reference_root)
    runtime_taxonomy_path = Path(runtime_taxonomy_path)
    runtime_unit_service_path = Path(runtime_unit_service_path)
    work_catalog_path = Path(work_catalog_path)
    project_root = Path(project_root)

    envelope = ProjectionValidator(reference_root).validate()
    issues: list[ProjectionIssue] = list(envelope.issues)
    runtime_isolation = _runtime_isolation(project_root)
    issues.extend(_runtime_isolation_issues(runtime_isolation))

    if any(issue.severity is IssueSeverity.BLOCKER for issue in issues):
        sorted_issues = _sorted_issues(issues)
        counts = _blocked_counts(sorted_issues)
        return CombinedProjectionResult(
            sources=envelope.sources,
            ref1=None,
            ref2=None,
            ref3_units=None,
            ref3_extended=None,
            counts=counts,
            issues=sorted_issues,
            runtime_isolation=runtime_isolation,
            combined_activation_allowed=False,
            activation_blockers=("source_package_validation_failed", "inactive_projection_tooling"),
        )

    ref1 = project_ref1_taxonomy(reference_root, runtime_taxonomy_path)
    ref2 = project_ref2_characteristics(reference_root, runtime_taxonomy_path)
    ref3_units = project_ref3_units(reference_root, runtime_taxonomy_path, runtime_unit_service_path)
    ref3_extended = project_ref3_extended(reference_root, work_catalog_path)

    issues.extend(ref1.issues)
    issues.extend(ref2.issues)
    issues.extend(ref3_units.issues)
    issues.extend(ref3_extended.issues)

    details = _combined_details(ref1, ref2, ref3_units, ref3_extended, runtime_taxonomy_path)
    issues.extend(_invariant_issues(details, ref1.counts, ref2.counts, ref3_units.counts, ref3_extended.counts, reference_root))
    issues.extend(_diagnostic_warning_issues(details, reference_root))

    sorted_issues = _sorted_issues(issues)
    severity_counts = _severity_counts(sorted_issues)
    activation_blockers = _activation_blockers(envelope.sources, details, severity_counts)
    counts = {
        "status": "BLOCKED" if severity_counts["blockers"] else "PASS_WITH_WARNINGS" if severity_counts["warnings"] else "PASS",
        "severity": severity_counts,
        "ref1": ref1.counts,
        "ref2": ref2.counts,
        "ref3_units": ref3_units.counts,
        "ref3_extended": ref3_extended.counts,
        "details": details,
    }

    return CombinedProjectionResult(
        sources=envelope.sources,
        ref1=ref1.summary_dict(),
        ref2=ref2.summary_dict(),
        ref3_units=ref3_units.summary_dict(),
        ref3_extended=ref3_extended.summary_dict(),
        counts=counts,
        issues=sorted_issues,
        runtime_isolation=runtime_isolation,
        combined_activation_allowed=False,
        activation_blockers=activation_blockers,
    )


def write_combined_projection_outputs(
    reference_root: str | Path,
    output_dir: str | Path,
    *,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
    runtime_unit_service_path: str | Path = DEFAULT_RUNTIME_UNIT_SERVICE_PATH,
    work_catalog_path: str | Path = DEFAULT_WORK_CATALOG_PATH,
    project_root: str | Path = PROJECT_ROOT,
) -> CombinedProjectionResult:
    result = project_combined_ref_validation(
        reference_root,
        runtime_taxonomy_path=runtime_taxonomy_path,
        runtime_unit_service_path=runtime_unit_service_path,
        work_catalog_path=work_catalog_path,
        project_root=project_root,
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "combined_projection_summary.json", result.summary_dict())
    _write_json(output_dir / "combined_projection_issues.json", result.issues_dict())
    (output_dir / "combined_projection_report.md").write_text(_build_report(result), encoding="utf-8")
    return result


def _combined_details(ref1: Any, ref2: Any, ref3_units: Any, ref3_extended: Any, runtime_taxonomy_path: Path) -> dict[str, int]:
    ref1_exact_groups = sum(
        1 for entity in ref1.compatibility_matrix if entity.entity_type == "material_group" and entity.classification.value == "EXACT_MATCH"
    )
    ref1_exact_types = sum(
        1 for entity in ref1.compatibility_matrix if entity.entity_type == "material_type" and entity.classification.value == "EXACT_MATCH"
    )
    return {
        "ref1_exact_groups": ref1_exact_groups,
        "ref1_exact_material_types": ref1_exact_types,
        "ref1_exact_total_entities": ref1_exact_groups + ref1_exact_types,
        "ref2_runtime_field_usages": _runtime_field_usage_count(runtime_taxonomy_path, excluded_schema_codes={"gypsum_board_regular"}),
        "ref2_runtime_field_usages_current": _runtime_field_usage_count(runtime_taxonomy_path),
        "ref2_review_queue": ref2.counts.get("review_required_assignments", 0),
        "ref3a_review_queue": ref3_units.counts.get("review_required_units", 0),
        "ref3b_review_queue": ref3_extended.counts.get("ref3b_review_required", 0),
        "review_auto_activatable_total": ref2.counts.get("review_auto_activatable", 0)
        + ref3_units.counts.get("review_auto_activatable", 0)
        + ref3_extended.counts.get("ref3b_review_auto_activatable", 0),
        "packaging_ref2_mismatches": ref3_extended.counts.get("packaging_ref2_mismatches", 0),
        "runtime_conversion_simple": ref3_units.counts.get("runtime_conversion_simple", 0),
        "runtime_conversion_technical": ref3_units.counts.get("runtime_conversion_technical", 0),
        "runtime_conversion_seed": ref3_units.counts.get("runtime_conversion_seed", 0),
        "runtime_conversion_total": ref3_units.counts.get("runtime_conversion_records", 0),
        "ref3c_geometry_rules": ref3_extended.counts.get("geometry_rules", 0),
        "ref3c_coverage_rules": ref3_extended.counts.get("coverage_rules", 0),
        "ref3c_yield_rules": ref3_extended.counts.get("yield_rules", 0),
        "ref3c_consumption_rules": ref3_extended.counts.get("consumption_rules", 0),
        "ref3c_non_geometry_total": ref3_extended.counts.get("coverage_rules", 0)
        + ref3_extended.counts.get("yield_rules", 0)
        + ref3_extended.counts.get("consumption_rules", 0),
        "executable_work_material_mappings_before": ref3_extended.counts.get("executable_work_material_mappings_before", 0),
        "executable_work_material_mappings_after": ref3_extended.counts.get("executable_work_material_mappings_after", 0),
        "canonical_alias_ambiguities": ref3_units.counts.get("ambiguous", 0),
        "unknown_references": _unknown_reference_count(ref1.issues + ref2.issues + ref3_units.issues + ref3_extended.issues),
        "object_work_quantity_calculations": 0,
    }


def _runtime_field_usage_count(runtime_taxonomy_path: Path, excluded_schema_codes: set[str] | None = None) -> int:
    payload = json.loads(runtime_taxonomy_path.read_text(encoding="utf-8-sig"))
    excluded_schema_codes = excluded_schema_codes or set()
    schemas = payload.get("characteristicSchemas") or {}
    if isinstance(schemas, list):
        schemas = {str(index): item for index, item in enumerate(schemas)}
    usage_count = 0
    for schema_code, schema in schemas.items():
        if normalize_code(str(schema_code)) in excluded_schema_codes:
            continue
        if not isinstance(schema, dict):
            continue
        for key in ("required", "module2Required", "module2_required", "recommended", "conditional"):
            for field_code in schema.get(key, []) or []:
                if normalize_code(str(field_code)):
                    usage_count += 1
        raw_defs = schema.get("fieldDefinitions") or schema.get("field_definitions") or {}
        if isinstance(raw_defs, dict):
            usage_count += sum(1 for field_code in raw_defs if normalize_code(str(field_code)))
    return usage_count


def _runtime_isolation(project_root: Path) -> dict[str, Any]:
    production_roots = [project_root / "app", project_root / "src"]
    tooling_import_hits: list[str] = []
    reference_data_hits: list[str] = []
    for root in production_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            text = path.read_text(encoding="utf-8-sig")
            relative = str(path.relative_to(project_root)).replace("\\", "/")
            if "module1_ref_projection" in text or "tools.module1_ref_projection" in text:
                tooling_import_hits.append(relative)
            if "reference_data" in text or "ATOM_REF1" in text or "ATOM_REF2" in text or "ATOM_REF3" in text:
                reference_data_hits.append(relative)
    return {
        "production_imports_tooling": len(tooling_import_hits),
        "production_reads_reference_data": len(reference_data_hits),
        "tooling_import_hits": tooling_import_hits,
        "reference_data_hits": reference_data_hits,
    }


def _runtime_isolation_issues(runtime_isolation: dict[str, Any]) -> list[ProjectionIssue]:
    issues: list[ProjectionIssue] = []
    if runtime_isolation["production_imports_tooling"]:
        issues.append(
            ProjectionIssue(
                code="COMBINED_PRODUCTION_IMPORTS_TOOLING",
                severity=IssueSeverity.BLOCKER,
                message="Production code imports inactive REF projection tooling.",
            )
        )
    if runtime_isolation["production_reads_reference_data"]:
        issues.append(
            ProjectionIssue(
                code="COMBINED_PRODUCTION_READS_REFERENCE_DATA",
                severity=IssueSeverity.BLOCKER,
                message="Production code reads inactive REF source packages.",
            )
        )
    return issues


def _invariant_issues(
    details: dict[str, int],
    ref1_counts: dict[str, int],
    ref2_counts: dict[str, int],
    ref3_units_counts: dict[str, int],
    ref3_extended_counts: dict[str, int],
    reference_root: Path,
) -> list[ProjectionIssue]:
    expected = {
        "ref1.ref_groups": (ref1_counts.get("ref_groups"), 37),
        "ref1.ref_types": (ref1_counts.get("ref_types"), 978),
        "ref1.runtime_groups": (ref1_counts.get("runtime_groups"), 19),
        "ref1.runtime_types": (ref1_counts.get("runtime_types"), 192),
        "details.ref1_exact_groups": (details["ref1_exact_groups"], 19),
        "details.ref1_exact_material_types": (details["ref1_exact_material_types"], 192),
        "details.ref1_exact_total_entities": (details["ref1_exact_total_entities"], 211),
        "ref1.ref_only": (ref1_counts.get("ref_only"), 804),
        "ref1.runtime_only": (ref1_counts.get("runtime_only"), 0),
        "ref1.broken_references": (ref1_counts.get("broken_references"), 0),
        "ref2.ref_fields": (ref2_counts.get("ref_fields"), 558),
        "ref2.runtime_fields": (ref2_counts.get("runtime_fields"), 74),
        "details.ref2_runtime_field_usages": (details["ref2_runtime_field_usages"], 113),
        "ref2.field_overlap": (ref2_counts.get("field_overlap"), 46),
        "ref2.field_ref_only": (ref2_counts.get("field_ref_only"), 512),
        "ref2.field_runtime_only": (ref2_counts.get("field_runtime_only"), 28),
        "ref2.profiles": (ref2_counts.get("profiles"), 177),
        "ref2.assignments": (ref2_counts.get("assignments"), 978),
        "ref2.broken_references": (ref2_counts.get("broken_references"), 0),
        "ref2.field_type_mismatches": (ref2_counts.get("field_type_mismatches"), 0),
        "ref2.field_unit_mismatches": (ref2_counts.get("field_unit_mismatches"), 0),
        "details.ref2_review_queue": (details["ref2_review_queue"], 48),
        "ref3_units.ref_units": (ref3_units_counts.get("ref_units"), 90),
        "ref3_units.runtime_units": (ref3_units_counts.get("runtime_units"), 16),
        "ref3_units.exact": (ref3_units_counts.get("exact"), 16),
        "ref3_units.ref_only": (ref3_units_counts.get("ref_only"), 74),
        "ref3_units.runtime_only": (ref3_units_counts.get("runtime_only"), 0),
        "ref3_units.dimension_conflicts": (ref3_units_counts.get("dimension_conflicts"), 0),
        "details.ref3a_review_queue": (details["ref3a_review_queue"], 17),
        "details.runtime_conversion_simple": (details["runtime_conversion_simple"], 12),
        "details.runtime_conversion_technical": (details["runtime_conversion_technical"], 28),
        "details.runtime_conversion_seed": (details["runtime_conversion_seed"], 7),
        "details.runtime_conversion_total": (details["runtime_conversion_total"], 47),
        "ref3_extended.packaging_profiles": (ref3_extended_counts.get("packaging_profiles"), 21),
        "ref3_extended.packaging_assignments": (ref3_extended_counts.get("packaging_assignments"), 978),
        "details.ref3b_review_queue": (details["ref3b_review_queue"], 51),
        "details.packaging_ref2_mismatches": (details["packaging_ref2_mismatches"], 345),
        "details.ref3c_geometry_rules": (details["ref3c_geometry_rules"], 7),
        "details.ref3c_coverage_rules": (details["ref3c_coverage_rules"], 2),
        "details.ref3c_yield_rules": (details["ref3c_yield_rules"], 1),
        "details.ref3c_consumption_rules": (details["ref3c_consumption_rules"], 5),
        "details.ref3c_non_geometry_total": (details["ref3c_non_geometry_total"], 8),
        "details.review_auto_activatable_total": (details["review_auto_activatable_total"], 0),
        "details.executable_work_material_mappings_before": (details["executable_work_material_mappings_before"], 0),
        "details.executable_work_material_mappings_after": (details["executable_work_material_mappings_after"], 0),
        "details.canonical_alias_ambiguities": (details["canonical_alias_ambiguities"], 0),
        "details.unknown_references": (details["unknown_references"], 0),
        "details.object_work_quantity_calculations": (details["object_work_quantity_calculations"], 0),
    }
    issues: list[ProjectionIssue] = []
    for key, (actual, expected_value) in sorted(expected.items()):
        if actual != expected_value:
            issues.append(
                ProjectionIssue(
                    code="COMBINED_INVARIANT_MISMATCH",
                    severity=IssueSeverity.BLOCKER,
                    message=f"{key} expected {expected_value}, got {actual}",
                    source_path=reference_root,
                    entity_id=key,
                )
            )
    return issues


def _diagnostic_warning_issues(details: dict[str, int], reference_root: Path) -> list[ProjectionIssue]:
    warnings: list[ProjectionIssue] = []
    for key in ("ref2_review_queue", "ref3a_review_queue", "ref3b_review_queue"):
        if details[key]:
            warnings.append(
                ProjectionIssue(
                    code="COMBINED_REVIEW_SUBSET_DIAGNOSTIC_ONLY",
                    severity=IssueSeverity.WARNING,
                    message=f"{key} contains {details[key]} review records; review subsets are not auto activated.",
                    source_path=reference_root,
                    entity_id=key,
                )
            )
    if details["packaging_ref2_mismatches"]:
        warnings.append(
            ProjectionIssue(
                code="COMBINED_PACKAGING_REF2_MISMATCHES",
                severity=IssueSeverity.WARNING,
                message=f"{details['packaging_ref2_mismatches']} packaging/REF-2 mismatches are diagnostic only.",
                source_path=reference_root,
                entity_id="packaging_ref2_mismatches",
            )
        )
    if details["runtime_conversion_technical"] or details["runtime_conversion_seed"]:
        warnings.append(
            ProjectionIssue(
                code="COMBINED_CONVERSION_REQUIRES_REVIEW",
                severity=IssueSeverity.WARNING,
                message="Technical and formula conversions are not safe for automatic runtime activation.",
                source_path=reference_root,
                entity_id="runtime_conversions",
            )
        )
    return warnings


def _activation_blockers(sources: tuple[ProjectionSource, ...], details: dict[str, int], severity_counts: dict[str, int]) -> tuple[str, ...]:
    reasons = {
        "inactive_projection_tooling",
        "runtime_integration_decision_missing",
        "runtime_compatibility_migration_missing",
    }
    if any(source.status != "approved_for_runtime" for source in sources):
        reasons.add("source_status_not_approved_for_runtime")
    if any(source.integration_allowed is not True for source in sources):
        reasons.add("integration_allowed_not_true")
    if details["ref2_review_queue"] or details["ref3a_review_queue"] or details["ref3b_review_queue"]:
        reasons.add("review_subsets_exist")
    if severity_counts["warnings"]:
        reasons.add("warnings_require_decision")
    if severity_counts["blockers"]:
        reasons.add("blockers_exist")
    return tuple(sorted(reasons))


def _unknown_reference_count(issues: tuple[ProjectionIssue, ...]) -> int:
    return sum(
        1
        for issue in issues
        if issue.severity is IssueSeverity.BLOCKER and ("UNKNOWN" in issue.code or "INVALID_REFERENCE" in issue.code)
    )


def _severity_counts(issues: tuple[ProjectionIssue, ...]) -> dict[str, int]:
    counts = Counter(issue.severity.value for issue in issues)
    return {
        "blockers": counts[IssueSeverity.BLOCKER.value],
        "warnings": counts[IssueSeverity.WARNING.value],
        "info": counts[IssueSeverity.INFO.value],
        "total": len(issues),
    }


def _blocked_counts(issues: tuple[ProjectionIssue, ...]) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "severity": _severity_counts(issues),
        "ref1": {},
        "ref2": {},
        "ref3_units": {},
        "ref3_extended": {},
        "details": {},
    }


def _sorted_issues(issues: list[ProjectionIssue]) -> tuple[ProjectionIssue, ...]:
    return tuple(sorted(issues, key=lambda item: (item.severity.value, item.code, item.package_id or "", item.entity_id or "", item.message)))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_report(result: CombinedProjectionResult) -> str:
    lines = [
        "# Combined REF Projection Validation",
        "",
        f"Status: {result.counts['status']}",
        f"combined_activation_allowed: {str(result.combined_activation_allowed).lower()}",
        "",
        "## Severity",
    ]
    for key, value in result.counts["severity"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Counts"])
    for section in ("ref1", "ref2", "ref3_units", "ref3_extended"):
        lines.append(f"### {section}")
        for key, value in result.counts.get(section, {}).items():
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Details"])
    for key, value in result.counts.get("details", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Activation blockers"])
    for reason in result.activation_blockers:
        lines.append(f"- {reason}")
    lines.extend(["", "## Isolation"])
    for key, value in result.runtime_isolation.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
