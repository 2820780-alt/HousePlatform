from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from app.services.module1_alternatives_analogs import build_alternative_readiness_report
from app.services.module1_canonical_material_store import MaterialCanonicalView
from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_compatibility_matrix import build_compatibility_readiness_report
from app.services.module1_documents_evidence import build_document_package
from app.services.module1_material_roles import build_material_role_readiness_report
from app.services.module1_participants_directory import build_participant_directory_package
from app.services.module1_price_work_observations import build_price_observation_package
from app.services.module1_technical_profile_packaging import build_material_technical_profile


QUALITY_DIMENSIONS = (
    "identity",
    "classification",
    "characteristics",
    "technical_profile",
    "packaging",
    "roles",
    "alternatives",
    "compatibility",
    "documents",
    "participants",
    "price_observations",
    "source_provenance",
    "moderation",
    "export_readiness",
)

SEVERITIES = ("critical", "high", "medium", "low", "info")

BLOCKING_SEVERITIES = frozenset({"critical", "high"})


@dataclass(frozen=True)
class DataQualityIssue:
    issue_type: str
    dimension: str
    severity: str
    message: str
    field: str | None = None
    details: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class DataQualityMetric:
    code: str
    label: str
    value: int | float | str | bool | None
    dimension: str
    status: str


@dataclass(frozen=True)
class DataQualityActionHint:
    action_code: str
    title: str
    dimension: str
    issue_type: str
    target_field: str | None
    safe_to_auto_apply: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataQualityCheckResult:
    dimension: str
    passed: bool
    issues: tuple[DataQualityIssue, ...]
    metrics: tuple[DataQualityMetric, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterialDataQualitySnapshot:
    material_id: str | None
    material_name: str
    group: str | None
    category: Mapping[str, Any] | None
    overall_quality_score: int
    readiness_status: str
    issues: tuple[DataQualityIssue, ...]
    metrics: tuple[DataQualityMetric, ...]
    action_hints: tuple[DataQualityActionHint, ...]
    export_readiness: Mapping[str, Any]
    module2_readiness: Mapping[str, Any]
    module5_readiness_hint: Mapping[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DataQualityDashboardReport:
    total_materials_checked: int
    count_by_readiness_status: Mapping[str, int]
    count_by_severity: Mapping[str, int]
    count_by_issue_type: Mapping[str, int]
    count_by_dimension: Mapping[str, int]
    top_blocking_issues: tuple[DataQualityIssue, ...]
    material_snapshots: tuple[MaterialDataQualitySnapshot, ...]
    export_readiness_summary: Mapping[str, Any]
    warnings: tuple[str, ...]


def build_material_quality_snapshot(canonical_material_view: MaterialCanonicalView) -> MaterialDataQualitySnapshot:
    issues = _dedupe_issues(
        collect_identity_quality_issues(canonical_material_view)
        + collect_characteristic_quality_issues(canonical_material_view)
        + collect_technical_profile_quality_issues(canonical_material_view)
        + collect_role_quality_issues(canonical_material_view)
        + collect_alternative_quality_issues(canonical_material_view)
        + collect_compatibility_quality_issues(canonical_material_view)
        + collect_document_quality_issues(canonical_material_view)
        + collect_participant_quality_issues(canonical_material_view)
        + collect_price_observation_quality_issues(canonical_material_view)
        + collect_source_provenance_quality_issues(canonical_material_view)
        + collect_moderation_quality_issues(canonical_material_view)
    )
    metrics = _build_metrics(canonical_material_view, issues)
    score = calculate_material_quality_score(
        MaterialDataQualitySnapshot(
            material_id=canonical_material_view.material_id,
            material_name=canonical_material_view.canonical_name,
            group=_group_code(canonical_material_view),
            category=canonical_material_view.category,
            overall_quality_score=0,
            readiness_status="pending",
            issues=issues,
            metrics=metrics,
            action_hints=tuple(),
            export_readiness={},
            module2_readiness={},
            module5_readiness_hint={},
            warnings=tuple(),
        )
    )
    readiness = _readiness_status(canonical_material_view, issues, score)
    snapshot = MaterialDataQualitySnapshot(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        group=_group_code(canonical_material_view),
        category=canonical_material_view.category,
        overall_quality_score=score,
        readiness_status=readiness,
        issues=issues,
        metrics=metrics,
        action_hints=tuple(),
        export_readiness={},
        module2_readiness={},
        module5_readiness_hint={},
        warnings=tuple(dict.fromkeys(canonical_material_view.warnings)),
    )
    return MaterialDataQualitySnapshot(
        **{
            **snapshot.__dict__,
            "action_hints": build_quality_action_hints(snapshot),
            "export_readiness": build_export_readiness_summary(snapshot),
            "module2_readiness": _module2_readiness(canonical_material_view, issues),
            "module5_readiness_hint": _module5_readiness_hint(canonical_material_view, issues),
        }
    )


def build_data_quality_dashboard_report(
    canonical_material_views: Iterable[MaterialCanonicalView],
) -> DataQualityDashboardReport:
    snapshots = tuple(build_material_quality_snapshot(view) for view in canonical_material_views)
    all_issues = tuple(issue for snapshot in snapshots for issue in snapshot.issues)
    count_by_status = Counter(snapshot.readiness_status for snapshot in snapshots)
    count_by_severity = Counter(issue.severity for issue in all_issues)
    count_by_type = Counter(issue.issue_type for issue in all_issues)
    count_by_dimension = Counter(issue.dimension for issue in all_issues)
    blocking = tuple(
        sorted(
            (issue for issue in all_issues if issue.severity in BLOCKING_SEVERITIES),
            key=lambda issue: (_severity_rank(issue.severity), issue.dimension, issue.issue_type),
        )[:10]
    )
    return DataQualityDashboardReport(
        total_materials_checked=len(snapshots),
        count_by_readiness_status=MappingProxyType(dict(count_by_status)),
        count_by_severity=MappingProxyType({severity: count_by_severity.get(severity, 0) for severity in SEVERITIES}),
        count_by_issue_type=MappingProxyType(dict(count_by_type)),
        count_by_dimension=MappingProxyType(dict(count_by_dimension)),
        top_blocking_issues=blocking,
        material_snapshots=snapshots,
        export_readiness_summary=MappingProxyType(_aggregate_export_readiness(snapshots)),
        warnings=tuple(),
    )


def collect_identity_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    if not canonical_material_view.material_id:
        issues.append(_issue("identity", "export_blocked", "critical", "Material id is missing.", "material_id"))
    if not canonical_material_view.canonical_name:
        issues.append(_issue("identity", "export_blocked", "critical", "Canonical material name is missing.", "canonical_name"))
    if not _group_code(canonical_material_view):
        issues.append(_issue("classification", "export_blocked", "critical", "Material group is missing.", "group"))
    return tuple(issues)


def collect_characteristic_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    group_code = _group_code(canonical_material_view)
    characteristics = _characteristics_map(canonical_material_view)
    missing = CharacteristicSchemaRegistry().build_missing_required_report(group_code, characteristics)
    return tuple(
        _issue(
            "characteristics",
            "missing_required_characteristic",
            "high",
            f"Required characteristic is missing: {field}.",
            field,
        )
        for field in missing.missing_required
    )


def collect_technical_profile_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    profile = build_material_technical_profile(canonical_material_view)
    issues: list[DataQualityIssue] = []
    for field in profile.missing_module2_fields:
        issues.append(_issue("technical_profile", "missing_module2_field", "high", f"Module 2 field is missing: {field}.", field))
    for field in profile.packaging_profile.missing_fields:
        issues.append(_issue("packaging", "missing_packaging_field", "medium", f"Packaging field is missing: {field}.", field))
    for warning in profile.warnings:
        issues.append(_issue("technical_profile", "compatibility_insufficient_data", "low", warning))
    return tuple(issues)


def collect_role_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    report = build_material_role_readiness_report(build_material_technical_profile(canonical_material_view))
    issues: list[DataQualityIssue] = []
    if not report.roles_found:
        issues.append(_issue("roles", "missing_material_role", "medium", "No material roles are registered for this group."))
    for role_code, fields in report.missing_fields_by_role.items():
        for field in fields:
            issues.append(
                _issue(
                    "roles",
                    "role_blocked_by_missing_fields",
                    "medium",
                    f"Role {role_code} is blocked by missing field {field}.",
                    field,
                    {"roleCode": role_code},
                )
            )
    return tuple(issues)


def collect_alternative_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    report = build_alternative_readiness_report(build_material_technical_profile(canonical_material_view))
    issues: list[DataQualityIssue] = []
    if not report.rules_found:
        issues.append(_issue("alternatives", "missing_alternative_rule", "low", "No alternative rules are registered for this material group."))
    for field in report.missing_fields:
        issues.append(_issue("alternatives", "missing_alternative_rule", "low", f"Alternative evaluation field is missing: {field}.", field))
    return tuple(issues)


def collect_compatibility_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    report = build_compatibility_readiness_report(build_material_technical_profile(canonical_material_view))
    issues: list[DataQualityIssue] = []
    if not report.rules_found:
        issues.append(_issue("compatibility", "missing_compatibility_rule", "low", "No compatibility rules are registered for this material group."))
    for field in report.missing_fields:
        issues.append(_issue("compatibility", "compatibility_insufficient_data", "medium", f"Compatibility field is missing: {field}.", field))
    return tuple(issues)


def collect_document_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    package = build_document_package(canonical_material_view)
    readiness = package.readiness
    issues: list[DataQualityIssue] = []
    for hint in readiness.missing_document_hints:
        issues.append(_issue("documents", "missing_required_document", "high", f"Required document is missing: {hint}.", hint))
    for document in readiness.expired_documents:
        issues.append(_issue("documents", "expired_document", "medium", f"Document is expired: {document}."))
    for raw_link in readiness.raw_links_pending:
        issues.append(_issue("documents", "raw_document_not_linked", "low", f"Raw document link is not linked: {raw_link.url}."))
    return tuple(issues)


def collect_participant_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    readiness = build_participant_directory_package(canonical_material_view).readiness
    issues: list[DataQualityIssue] = []
    mapping = {
        "supplier": ("missing_supplier", "high", "Supplier is missing."),
        "manufacturer": ("missing_manufacturer", "medium", "Manufacturer is missing."),
        "brand": ("missing_brand", "low", "Brand is missing."),
        "regional_coverage": ("missing_region", "medium", "Regional coverage is missing."),
    }
    for detail in readiness.missing_details:
        if detail in mapping:
            issue_type, severity, message = mapping[detail]
            issues.append(_issue("participants", issue_type, severity, message, detail))
    return tuple(issues)


def collect_price_observation_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    package = build_price_observation_package(canonical_material_view)
    readiness = package.readiness
    positive_observations = _positive_price_observations(package.observations)
    issues: list[DataQualityIssue] = []
    if "price_observations" in readiness.missing_details:
        issues.append(_issue("price_observations", "missing_price_observation", "high", "Price observation is missing."))
    if package.observations and not positive_observations:
        issues.append(
            _issue(
                "price_observations",
                "missing_positive_price_observation",
                "high",
                "Positive price observation is required before material readiness.",
                "price_value",
            )
        )
    if "regional_binding" in readiness.missing_details:
        issues.append(_issue("price_observations", "missing_region", "medium", "Price observation region is missing."))
    for key in readiness.duplicate_stable_keys:
        issues.append(_issue("price_observations", "duplicate_price_observation", "medium", f"Duplicate price observation: {key}."))
    for key in readiness.suspicious_observations:
        issues.append(_issue("price_observations", "suspicious_price_observation", "high", f"Suspicious price observation: {key}."))
    return tuple(issues)
def collect_source_provenance_quality_issues(canonical_material_view: MaterialCanonicalView) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    if canonical_material_view.evidence.source_ref_count == 0:
        issues.append(_issue("source_provenance", "missing_source_provenance", "high", "Source provenance is missing."))
    for ref in canonical_material_view.evidence.source_refs:
        confidence = _decimal(ref.get("matchConfidence") or ref.get("confidence"))
        if confidence is not None and confidence < 0.5:
            issues.append(_issue("source_provenance", "low_confidence_source", "medium", "Source confidence is low."))
    return tuple(issues)


def collect_moderation_quality_issues(
    canonical_material_view: MaterialCanonicalView,
    moderation_items: Iterable[Any] | None = None,
) -> tuple[DataQualityIssue, ...]:
    issues: list[DataQualityIssue] = []
    if canonical_material_view.moderation_status == "needs_review" or canonical_material_view.quality.open_issues:
        issues.append(_issue("moderation", "pending_moderation", "high", "Material needs moderation."))
    for item in moderation_items or ():
        status = _as_string(_value(item, "status", "moderationStatus"))
        match_confidence = _decimal(_value(item, "confidence", "matchConfidence"))
        issue_type = _as_string(_value(item, "issue_type", "issueType", "type"))
        if issue_type in {"duplicate_candidate", "possible_duplicate"}:
            issues.append(_issue("moderation", issue_type, "high", f"Moderation issue: {issue_type}."))
        if status in {"pending", "needs_review"}:
            issues.append(_issue("moderation", "pending_moderation", "high", "Moderation item is pending."))
        if match_confidence is not None and match_confidence < 0.6:
            issues.append(_issue("moderation", "low_confidence_match", "medium", "Match confidence is low."))
    return tuple(issues)


def calculate_material_quality_score(snapshot: MaterialDataQualitySnapshot) -> int:
    score = 100
    penalties = {
        "critical": 30,
        "high": 14,
        "medium": 7,
        "low": 3,
        "info": 1,
    }
    for issue in snapshot.issues:
        score -= penalties.get(classify_quality_severity(issue), 1)
    return max(0, min(100, score))


def classify_quality_severity(issue: DataQualityIssue) -> str:
    return issue.severity if issue.severity in SEVERITIES else "info"


def build_quality_action_hints(snapshot: MaterialDataQualitySnapshot) -> tuple[DataQualityActionHint, ...]:
    hints: list[DataQualityActionHint] = []
    for issue in snapshot.issues:
        title = _action_title(issue)
        hints.append(
            DataQualityActionHint(
                action_code=f"review_{issue.issue_type}",
                title=title,
                dimension=issue.dimension,
                issue_type=issue.issue_type,
                target_field=issue.field,
                safe_to_auto_apply=False,
                warnings=("Human review only. This hint does not mutate data.",),
            )
        )
    return tuple(_dedupe_hints(hints))


def group_quality_issues_by_dimension(
    issues: tuple[DataQualityIssue, ...] | list[DataQualityIssue],
) -> Mapping[str, tuple[DataQualityIssue, ...]]:
    grouped: dict[str, list[DataQualityIssue]] = {}
    for issue in issues:
        grouped.setdefault(issue.dimension, []).append(issue)
    return MappingProxyType({dimension: tuple(items) for dimension, items in grouped.items()})


def build_export_readiness_summary(snapshot: MaterialDataQualitySnapshot) -> Mapping[str, Any]:
    blocking = tuple(issue for issue in snapshot.issues if issue.severity in BLOCKING_SEVERITIES)
    return MappingProxyType(
        {
            "ready": not blocking and snapshot.readiness_status in {"ready_for_export", "ready_for_module2"},
            "readinessStatus": snapshot.readiness_status,
            "blockingIssueCount": len(blocking),
            "blockingIssueTypes": tuple(dict.fromkeys(issue.issue_type for issue in blocking)),
            "module1Only": True,
            "autoFixApplied": False,
        }
    )


def _build_metrics(canonical_material_view: MaterialCanonicalView, issues: tuple[DataQualityIssue, ...]) -> tuple[DataQualityMetric, ...]:
    characteristics = _characteristics_map(canonical_material_view)
    return (
        DataQualityMetric("characteristic_count", "Characteristics", len(characteristics), "characteristics", "ok" if characteristics else "missing"),
        DataQualityMetric("document_count", "Documents", canonical_material_view.evidence.document_count, "documents", "ok" if canonical_material_view.evidence.document_count else "missing"),
        DataQualityMetric("source_ref_count", "Source refs", canonical_material_view.evidence.source_ref_count, "source_provenance", "ok" if canonical_material_view.evidence.source_ref_count else "missing"),
        DataQualityMetric("issue_count", "Quality issues", len(issues), "export_readiness", "ok" if not issues else "needs_review"),
    )


def _readiness_status(canonical_material_view: MaterialCanonicalView, issues: tuple[DataQualityIssue, ...], score: int) -> str:
    if any(issue.severity == "critical" for issue in issues):
        return "blocked"
    if any(issue.dimension == "moderation" for issue in issues):
        return "needs_moderation"
    if score < 45:
        return "insufficient_quality"
    if any(issue.severity in {"high", "medium"} for issue in issues):
        return "needs_more_data"
    if build_material_technical_profile(canonical_material_view).readiness.ready_for_module2:
        return "ready_for_module2"
    return "ready_for_export"


def _module2_readiness(canonical_material_view: MaterialCanonicalView, issues: tuple[DataQualityIssue, ...]) -> Mapping[str, Any]:
    profile = build_material_technical_profile(canonical_material_view)
    has_price_blocker = any(
        issue.issue_type in {"missing_price_observation", "missing_positive_price_observation"}
        for issue in issues
    )
    missing_fields = profile.missing_module2_fields + (("positive_price_observation",) if has_price_blocker else tuple())
    return MappingProxyType(
        {
            "ready": profile.readiness.ready_for_module2
            and not any(issue.issue_type == "missing_module2_field" for issue in issues)
            and not has_price_blocker,
            "status": "missing_positive_price" if has_price_blocker else profile.readiness.status,
            "missingFields": missing_fields,
            "module2Calculations": "not_performed_by_module1",
        }
    )
def _module5_readiness_hint(canonical_material_view: MaterialCanonicalView, issues: tuple[DataQualityIssue, ...]) -> Mapping[str, Any]:
    has_price_issue = any(issue.dimension == "price_observations" for issue in issues)
    has_participant_issue = any(issue.dimension == "participants" for issue in issues)
    return MappingProxyType(
        {
            "readyHint": not has_price_issue and not has_participant_issue,
            "missingPriceOrParticipantData": has_price_issue or has_participant_issue,
            "estimateCalculated": False,
            "module5Costing": "not_performed_by_module1",
        }
    )


def _positive_price_observations(observations: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(observation for observation in observations if _positive_decimal(_value(observation, "price_value", "priceValue", "price")))


def _positive_decimal(value: Any) -> bool:
    try:
        if value in (None, ""):
            return False
        return Decimal(str(value).replace(",", ".")) > 0
    except Exception:
        return False
def _aggregate_export_readiness(snapshots: tuple[MaterialDataQualitySnapshot, ...]) -> Mapping[str, Any]:
    ready = tuple(snapshot for snapshot in snapshots if snapshot.export_readiness.get("ready"))
    blocked = tuple(snapshot for snapshot in snapshots if snapshot.readiness_status == "blocked")
    return {
        "readyCount": len(ready),
        "blockedCount": len(blocked),
        "total": len(snapshots),
        "autoFixApplied": False,
    }


def _action_title(issue: DataQualityIssue) -> str:
    if issue.issue_type in {"missing_required_characteristic", "missing_module2_field", "missing_packaging_field"}:
        return f"Add or verify {issue.field}."
    if issue.issue_type == "missing_required_document":
        return f"Link required document {issue.field}."
    if issue.issue_type in {"missing_supplier", "missing_manufacturer", "missing_brand", "missing_region"}:
        return f"Clarify {issue.field or issue.issue_type.replace('missing_', '')}."
    if issue.issue_type == "suspicious_price_observation":
        return "Review suspicious price observation."
    if issue.issue_type == "missing_positive_price_observation":
        return "Add a positive price observation before readiness handoff."
    if issue.issue_type in {"pending_moderation", "possible_duplicate", "duplicate_candidate"}:
        return "Send to moderation review."
    return f"Review {issue.issue_type}."


def _dedupe_hints(hints: list[DataQualityActionHint]) -> tuple[DataQualityActionHint, ...]:
    result = []
    seen = set()
    for hint in hints:
        key = (hint.action_code, hint.target_field, hint.dimension)
        if key in seen:
            continue
        seen.add(key)
        result.append(hint)
    return tuple(result)


def _dedupe_issues(issues: tuple[DataQualityIssue, ...]) -> tuple[DataQualityIssue, ...]:
    result = []
    seen = set()
    for issue in issues:
        key = (issue.issue_type, issue.dimension, issue.severity, issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return tuple(result)


def _issue(
    dimension: str,
    issue_type: str,
    severity: str,
    message: str,
    field: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> DataQualityIssue:
    return DataQualityIssue(
        issue_type=issue_type,
        dimension=dimension,
        severity=severity,
        message=message,
        field=field,
        details=MappingProxyType(dict(details or {})),
    )


def _characteristics_map(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    return {
        characteristic.name: characteristic.value
        for characteristic in canonical_material_view.characteristics
        if characteristic.name
    }


def _group_code(canonical_material_view: MaterialCanonicalView) -> str | None:
    group = canonical_material_view.group or {}
    category = canonical_material_view.category or {}
    return _as_string(group.get("code") or group.get("slug") or category.get("slug"))


def _severity_rank(severity: str) -> int:
    return {severity: index for index, severity in enumerate(SEVERITIES)}.get(severity, 99)


def _value(obj: Any, *names: str) -> Any:
    for name in names:
        if obj is None:
            return None
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if not isinstance(obj, Mapping) and hasattr(obj, name):
            return getattr(obj, name)
    return None


def _decimal(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
