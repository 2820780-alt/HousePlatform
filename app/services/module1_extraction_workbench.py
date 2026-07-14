from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from app.services.module1_data_quality_dashboard import build_material_quality_snapshot
from app.services.module1_extraction_blueprint_registry import ExtractionBlueprintRegistry
from app.services.module1_matching_dedup import build_match_candidate
from app.services.module1_material_normalizer import (
    build_normalization_report,
    infer_material_group,
    normalize_raw_ingestion_item,
)
from app.services.module1_moderation_core import build_moderation_queue_item
from app.services.module1_raw_ingestion_pipeline import (
    Module1RawIngestionItem,
    build_raw_ingestion_readiness_report,
    enrich_raw_ingestion_with_extraction_blueprint,
    enrich_raw_ingestion_with_source_profile,
    validate_raw_ingestion_item,
)
from app.services.module1_source_profile_registry import Module1SourceProfileRegistry
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


FIELD_STATUS_MAPPED = "mapped"
FIELD_STATUS_MISSING = "missing"
FIELD_STATUS_UNKNOWN = "unknown"
FIELD_STATUS_INVALID = "invalid"
FIELD_STATUS_IGNORED = "ignored"


@dataclass(frozen=True)
class ExtractionWorkbenchSample:
    sample_id: str
    legacy_source: str
    raw_payload: Mapping[str, Any]
    source_profile_code: str | None = None
    extraction_profile_code: str | None = None
    material_group: str | None = None


@dataclass(frozen=True)
class ExtractionWorkbenchInput:
    workbench_id: str
    sample: ExtractionWorkbenchSample
    source_profile_code: str | None = None
    extraction_profile_code: str | None = None
    material_group: str | None = None
    no_side_effects: bool = True


@dataclass(frozen=True)
class ExtractionFieldTrace:
    raw_field: str | None
    raw_value: Any
    mapped_field: str | None
    normalized_value: Any | None
    expected_by_blueprint: bool
    required: bool
    module2_required: bool
    status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractionValidationIssue:
    issue_type: str
    severity: str
    field: str | None
    message: str
    source_profile_code: str | None
    extraction_profile_code: str | None
    blueprint_code: str | None
    suggestion: str


@dataclass(frozen=True)
class ExtractionWorkbenchActionHint:
    hint_type: str
    title: str
    message: str
    field: str | None = None
    issue_type: str | None = None
    safe_to_auto_apply: bool = False
    no_side_effects: bool = True


@dataclass(frozen=True)
class ExtractionWorkbenchPipelinePreview:
    raw_ingestion_preview: Mapping[str, Any]
    normalized_candidate_preview: Mapping[str, Any]
    matching_preview: Mapping[str, Any] | None
    moderation_preview: Mapping[str, Any] | None
    quality_preview: Mapping[str, Any] | None
    no_side_effects: bool = True


@dataclass(frozen=True)
class ExtractionWorkbenchReport:
    workbench_id: str
    source_profile_summary: Mapping[str, Any] | None
    extraction_profile_summary: Mapping[str, Any] | None
    blueprint_summary: Mapping[str, Any] | None
    field_traces: tuple[ExtractionFieldTrace, ...]
    validation_issues: tuple[ExtractionValidationIssue, ...]
    pipeline_preview: ExtractionWorkbenchPipelinePreview
    action_hints: tuple[ExtractionWorkbenchActionHint, ...]
    warnings: tuple[str, ...]
    no_side_effects: bool = True


def build_workbench_sample_from_raw_payload(
    raw_payload: Mapping[str, Any] | None,
    *,
    source_profile_code: str | None = None,
    extraction_profile_code: str | None = None,
    material_group: str | None = None,
    legacy_source: str = "raw_payload",
) -> ExtractionWorkbenchSample:
    payload = dict(raw_payload or {})
    resolved_source = _first_text(source_profile_code, payload.get("sourceCode"), payload.get("source_code"))
    resolved_group = _first_text(material_group, payload.get("materialGroup"), payload.get("material_group"), payload.get("group_code"))
    sample_id = _stable_key("m1_workbench_sample", legacy_source, resolved_source, resolved_group, payload)
    return ExtractionWorkbenchSample(
        sample_id=sample_id,
        legacy_source=legacy_source,
        raw_payload=payload,
        source_profile_code=resolved_source,
        extraction_profile_code=extraction_profile_code,
        material_group=resolved_group,
    )


def build_workbench_input(
    raw_payload: Mapping[str, Any] | None = None,
    *,
    sample: ExtractionWorkbenchSample | None = None,
    legacy_shape: Any | None = None,
    source_profile_code: str | None = None,
    extraction_profile_code: str | None = None,
    material_group: str | None = None,
) -> ExtractionWorkbenchInput:
    if sample is None:
        payload = dict(raw_payload or _payload_from_legacy_shape(legacy_shape))
        legacy_source = _first_text(payload.get("legacy_source"), _get(legacy_shape, "legacy_source"), "raw_payload") or "raw_payload"
        sample = build_workbench_sample_from_raw_payload(
            payload,
            source_profile_code=source_profile_code,
            extraction_profile_code=extraction_profile_code,
            material_group=material_group,
            legacy_source=legacy_source,
        )

    resolved_source = _first_text(source_profile_code, sample.source_profile_code)
    resolved_group = _first_text(material_group, sample.material_group)
    resolved_extraction = _first_text(extraction_profile_code, sample.extraction_profile_code)
    workbench_id = _stable_key("m1_workbench", sample.sample_id, resolved_source, resolved_extraction, resolved_group)
    return ExtractionWorkbenchInput(
        workbench_id=workbench_id,
        sample=sample,
        source_profile_code=resolved_source,
        extraction_profile_code=resolved_extraction,
        material_group=resolved_group,
    )


def build_field_trace(
    raw_payload: Mapping[str, Any] | None,
    source_profile: Any | None = None,
    extraction_profile: Any | None = None,
    blueprint: Any | None = None,
) -> tuple[ExtractionFieldTrace, ...]:
    payload = dict(raw_payload or {})
    characteristics = _characteristics(payload)
    registry = UnitConversionRegistry()
    blueprint = blueprint or _resolve_blueprint(payload)
    required = frozenset(getattr(blueprint, "required_fields", tuple()) or tuple())
    module2_required = frozenset(getattr(blueprint, "module2_required_fields", tuple()) or tuple())
    expected_fields = frozenset(getattr(blueprint, "raw_fields", tuple()) or tuple())
    aliases = dict(getattr(blueprint, "field_aliases", {}) or {})
    alias_index = _alias_index(aliases)

    traces: list[ExtractionFieldTrace] = []
    for raw_field, raw_value in _iter_raw_fields(payload, characteristics):
        mapped_field = _map_raw_field(raw_field, alias_index)
        normalized_value = _normalize_trace_value(mapped_field, raw_value, registry)
        is_expected = bool(mapped_field and (mapped_field in expected_fields or mapped_field in required or mapped_field in module2_required))
        status = FIELD_STATUS_MAPPED if is_expected or mapped_field in _COMMON_MAPPED_FIELDS else FIELD_STATUS_UNKNOWN
        warnings: tuple[str, ...] = ()
        if mapped_field == "unit" and raw_value and normalized_value is None:
            status = FIELD_STATUS_INVALID
            warnings = ("Unit is not recognized by Module 1 unit dictionary.",)
        elif mapped_field in _IGNORED_METADATA_FIELDS:
            status = FIELD_STATUS_IGNORED
        traces.append(
            ExtractionFieldTrace(
                raw_field=raw_field,
                raw_value=raw_value,
                mapped_field=mapped_field,
                normalized_value=normalized_value,
                expected_by_blueprint=is_expected,
                required=bool(mapped_field in required),
                module2_required=bool(mapped_field in module2_required),
                status=status,
                warnings=warnings,
            )
        )

    mapped_fields = {trace.mapped_field for trace in traces if trace.mapped_field and trace.status != FIELD_STATUS_INVALID}
    for expected in tuple(required) + tuple(field for field in module2_required if field not in required):
        if expected not in mapped_fields:
            traces.append(
                ExtractionFieldTrace(
                    raw_field=None,
                    raw_value=None,
                    mapped_field=expected,
                    normalized_value=None,
                    expected_by_blueprint=True,
                    required=expected in required,
                    module2_required=expected in module2_required,
                    status=FIELD_STATUS_MISSING,
                    warnings=("Expected extraction field is absent in raw payload.",),
                )
            )

    return tuple(traces)


def validate_extraction_sample(workbench_input: ExtractionWorkbenchInput) -> tuple[ExtractionValidationIssue, ...]:
    raw_item = _build_raw_ingestion_item(workbench_input)
    source_registry = Module1SourceProfileRegistry()
    blueprint_registry = ExtractionBlueprintRegistry()
    source_profile_code = workbench_input.source_profile_code or raw_item.source_code
    material_group = _resolve_material_group(workbench_input, raw_item)
    extraction_profile_code = workbench_input.extraction_profile_code
    blueprint = blueprint_registry.get_blueprint(material_group) if material_group else None
    blueprint_code = getattr(blueprint, "group_code", None) if blueprint else material_group
    issues: list[ExtractionValidationIssue] = []

    if source_profile_code and source_registry.get_source_profile(source_profile_code) is None:
        issues.append(_issue("unknown_source_profile", "warning", "source_profile_code", f"Source profile '{source_profile_code}' is not registered.", workbench_input, blueprint_code, "Clarify participant/source."))
    if extraction_profile_code and not _extraction_profile_matches(source_profile_code, extraction_profile_code, material_group):
        issues.append(_issue("unknown_extraction_profile", "warning", "extraction_profile_code", f"Extraction profile '{extraction_profile_code}' is not registered for this source/material group.", workbench_input, blueprint_code, "Clarify ExtractionProfile."))
    if not material_group or blueprint is None:
        issues.append(_issue("unknown_material_group", "error", "material_group", "Material group is unknown or has no extraction blueprint.", workbench_input, blueprint_code, "Clarify required characteristic/material group."))

    raw_validation = validate_raw_ingestion_item(raw_item)
    for field in raw_validation.missing_fields:
        issues.append(_issue("unsupported_raw_shape", "error", field, f"Raw sample is missing '{field}'.", workbench_input, blueprint_code, "Clarify SourceProfile field mapping."))
    for warning in raw_validation.unit_warnings:
        issues.append(_issue("invalid_unit", "warning", "unit", warning, workbench_input, blueprint_code, "Clarify unit mapping."))

    if raw_item.raw_price is None and _has_raw_price_value(workbench_input.sample.raw_payload):
        issues.append(_issue("invalid_price", "warning", "price", "Raw price cannot be parsed as a decimal number.", workbench_input, blueprint_code, "Clarify price extraction rule."))

    if blueprint is not None and material_group:
        extraction_report = blueprint_registry.validate_extracted_payload(material_group, _blueprint_payload(raw_item))
        for field in extraction_report.missing_required:
            issues.append(_issue("missing_required_extraction_field", "error", field, f"Required extraction field '{field}' is missing.", workbench_input, blueprint.group_code, "Add field mapping in SourceProfile."))
        for field in extraction_report.missing_module2_required:
            issues.append(_issue("missing_module2_field", "warning", field, f"Module 2 required field '{field}' is missing.", workbench_input, blueprint.group_code, "Add required characteristic."))
        for unit_warning in extraction_report.unit_warnings:
            issues.append(_issue("invalid_unit", "warning", unit_warning.field, unit_warning.message, workbench_input, blueprint.group_code, "Clarify unit mapping."))
        if blueprint.document_hints and not raw_item.raw_documents:
            issues.append(_issue("missing_document_link", "info", "documents", "No document links were found for the sample.", workbench_input, blueprint.group_code, "Add document link."))

    for trace in build_field_trace(workbench_input.sample.raw_payload, blueprint=blueprint):
        if trace.status == FIELD_STATUS_UNKNOWN:
            issues.append(_issue("unmapped_field", "info", trace.raw_field, f"Raw field '{trace.raw_field}' is not mapped to the current blueprint.", workbench_input, blueprint_code, "Add field mapping in SourceProfile."))

    normalized = normalize_raw_ingestion_item(raw_item)
    if normalized.confidence < Decimal("0.70"):
        issues.append(_issue("low_normalization_confidence", "warning", "confidence", "Normalization confidence is low for this dry-run sample.", workbench_input, blueprint_code, "Send candidate to moderation."))

    return _dedupe_issues(issues)


def build_raw_ingestion_preview(workbench_input: ExtractionWorkbenchInput) -> Mapping[str, Any]:
    raw_item = _build_raw_ingestion_item(workbench_input)
    material_group = _resolve_material_group(workbench_input, raw_item)
    enriched = enrich_raw_ingestion_with_source_profile(raw_item)
    if material_group:
        enriched = enrich_raw_ingestion_with_extraction_blueprint(enriched, material_group)
    readiness = build_raw_ingestion_readiness_report(enriched, material_group)
    return {
        "item": _jsonable(asdict(enriched)),
        "readinessReport": _jsonable(asdict(readiness)),
        "rawDataIsCanonical": False,
        "no_side_effects": True,
    }


def build_normalization_preview(workbench_input: ExtractionWorkbenchInput) -> Mapping[str, Any]:
    raw_item = _build_raw_ingestion_item(workbench_input)
    report = build_normalization_report(raw_item)
    return {
        "candidate": _jsonable(asdict(report.candidate)),
        "report": _jsonable(asdict(report)),
        "no_side_effects": True,
    }


def build_matching_preview(
    workbench_input: ExtractionWorkbenchInput,
    existing_materials: Iterable[Mapping[str, Any] | Any] | None = None,
) -> Mapping[str, Any]:
    raw_item = _build_raw_ingestion_item(workbench_input)
    candidate = normalize_raw_ingestion_item(raw_item)
    match_candidate = build_match_candidate(candidate, tuple(existing_materials or ()))
    return {
        "matchCandidate": _jsonable(asdict(match_candidate)),
        "createsLink": False,
        "mergesDuplicate": False,
        "no_side_effects": True,
    }


def build_moderation_preview(
    workbench_input: ExtractionWorkbenchInput,
    existing_materials: Iterable[Mapping[str, Any] | Any] | None = None,
) -> Mapping[str, Any]:
    matching = build_matching_preview(workbench_input, existing_materials)
    queue_item = build_moderation_queue_item(_match_candidate_from_preview(matching))
    return {
        "totalItems": 1,
        "items": (_jsonable(asdict(queue_item)),),
        "decisionApplied": False,
        "no_side_effects": True,
    }


def build_quality_preview(
    workbench_input: ExtractionWorkbenchInput,
    canonical_material_view: Any | None = None,
) -> Mapping[str, Any] | None:
    if canonical_material_view is None:
        return None
    snapshot = build_material_quality_snapshot(canonical_material_view)
    return {
        "snapshot": _jsonable(_dataclass_snapshot(snapshot)),
        "qualityScore": snapshot.overall_quality_score,
        "readinessStatus": snapshot.readiness_status,
        "no_side_effects": True,
    }


def build_extraction_workbench_report(
    workbench_input: ExtractionWorkbenchInput,
    existing_materials: Iterable[Mapping[str, Any] | Any] | None = None,
    canonical_material_view: Any | None = None,
) -> ExtractionWorkbenchReport:
    raw_item = _build_raw_ingestion_item(workbench_input)
    material_group = _resolve_material_group(workbench_input, raw_item)
    source_registry = Module1SourceProfileRegistry()
    blueprint_registry = ExtractionBlueprintRegistry()
    source_profile_code = workbench_input.source_profile_code or raw_item.source_code
    source_profile = source_registry.get_source_profile(source_profile_code) if source_profile_code else None
    extraction_profile = source_registry.get_extraction_profile(source_profile_code, material_group) if source_profile_code else None
    blueprint = blueprint_registry.get_blueprint(material_group) if material_group else None

    raw_preview = build_raw_ingestion_preview(workbench_input)
    normalization_preview = build_normalization_preview(workbench_input)
    matching_preview = build_matching_preview(workbench_input, existing_materials)
    moderation_preview = build_moderation_preview(workbench_input, existing_materials)
    quality_preview = build_quality_preview(workbench_input, canonical_material_view)
    pipeline_preview = ExtractionWorkbenchPipelinePreview(
        raw_ingestion_preview=raw_preview,
        normalized_candidate_preview=normalization_preview,
        matching_preview=matching_preview,
        moderation_preview=moderation_preview,
        quality_preview=quality_preview,
    )

    validation_issues = list(validate_extraction_sample(workbench_input))
    match_decision = matching_preview["matchCandidate"].get("decision_hint")
    if match_decision in {"possible_duplicate", "exact_match", "strong_match"}:
        validation_issues.append(_issue("possible_duplicate", "warning", None, "Matching preview found an existing material-like candidate.", workbench_input, getattr(blueprint, "group_code", material_group), "Check possible duplicate."))
    if moderation_preview and moderation_preview.get("items"):
        validation_issues.append(_issue("pending_moderation", "info", None, "Moderation queue item preview was built and no decision was applied.", workbench_input, getattr(blueprint, "group_code", material_group), "Send candidate to moderation."))
    if quality_preview and str(quality_preview.get("readinessStatus")) not in {"ready", "ok", "export_ready"}:
        validation_issues.append(_issue("insufficient_quality", "warning", None, "Quality preview reports insufficient readiness.", workbench_input, getattr(blueprint, "group_code", material_group), "Clarify participant/source."))

    issues = _dedupe_issues(validation_issues)
    warnings = tuple(dict.fromkeys(raw_item.warnings + tuple(issue.message for issue in issues if issue.severity in {"warning", "error"})))
    report = ExtractionWorkbenchReport(
        workbench_id=workbench_input.workbench_id,
        source_profile_summary=_source_profile_summary(source_profile),
        extraction_profile_summary=_extraction_profile_summary(extraction_profile),
        blueprint_summary=_blueprint_summary(blueprint),
        field_traces=build_field_trace(workbench_input.sample.raw_payload, source_profile=source_profile, extraction_profile=extraction_profile, blueprint=blueprint),
        validation_issues=issues,
        pipeline_preview=pipeline_preview,
        action_hints=tuple(),
        warnings=warnings,
    )
    return ExtractionWorkbenchReport(
        workbench_id=report.workbench_id,
        source_profile_summary=report.source_profile_summary,
        extraction_profile_summary=report.extraction_profile_summary,
        blueprint_summary=report.blueprint_summary,
        field_traces=report.field_traces,
        validation_issues=report.validation_issues,
        pipeline_preview=report.pipeline_preview,
        action_hints=build_workbench_action_hints(report),
        warnings=report.warnings,
    )


def build_workbench_action_hints(report: ExtractionWorkbenchReport) -> tuple[ExtractionWorkbenchActionHint, ...]:
    hints: list[ExtractionWorkbenchActionHint] = []
    for issue in report.validation_issues:
        hints.append(_hint_for_issue(issue))
    return _dedupe_hints(hints)


def _build_raw_ingestion_item(workbench_input: ExtractionWorkbenchInput) -> Module1RawIngestionItem:
    payload = workbench_input.sample.raw_payload
    characteristics = _characteristics(payload)
    source_code = _first_text(workbench_input.source_profile_code, payload.get("sourceCode"), payload.get("source_code"))
    return Module1RawIngestionItem(
        legacy_source=workbench_input.sample.legacy_source or "raw_payload",
        source_id=_first_text(payload.get("sourceId"), payload.get("source_id")),
        source_code=source_code,
        source_type=_first_text(payload.get("sourceType"), payload.get("source_type")),
        source_url=_first_text(payload.get("sourceUrl"), payload.get("source_url"), payload.get("url"), payload.get("external_url")),
        raw_title=_first_text(payload.get("rawTitle"), payload.get("raw_title"), payload.get("title"), payload.get("name"), payload.get("raw_name")),
        raw_description=_first_text(payload.get("description"), payload.get("raw_description")),
        raw_category=_first_text(payload.get("rawCategory"), payload.get("raw_category"), payload.get("category")),
        raw_price=_decimal(_first(payload.get("rawPrice"), payload.get("raw_price"), payload.get("price"), payload.get("cost"))),
        raw_unit=_first_text(payload.get("rawUnit"), payload.get("raw_unit"), payload.get("unit"), payload.get("price_unit")),
        raw_characteristics=characteristics,
        raw_documents=_documents(payload),
        raw_images=_images(payload),
        raw_availability=_first_text(payload.get("availability"), payload.get("stock")),
        raw_supplier=_first_text(payload.get("supplier"), payload.get("supplier_name")),
        raw_manufacturer=_first_text(payload.get("manufacturer"), payload.get("raw_manufacturer")),
        region=_first_text(payload.get("region")),
        city=_first_text(payload.get("city")),
        extraction_profile_reference=_first_text(workbench_input.extraction_profile_code, payload.get("extractionProfile"), payload.get("extraction_profile")),
        adapter_version=_first_text(payload.get("adapterVersion"), payload.get("adapter_version")),
        source_task_version=_first_text(payload.get("sourceTaskVersion"), payload.get("source_task_version")),
        confidence=_decimal(payload.get("confidence")),
        raw_payload={"legacy_entity": "ExtractionWorkbenchSample", **dict(payload)},
    )


def _resolve_material_group(workbench_input: ExtractionWorkbenchInput, raw_item: Module1RawIngestionItem) -> str | None:
    if workbench_input.material_group:
        return workbench_input.material_group
    if workbench_input.sample.material_group:
        return workbench_input.sample.material_group
    return infer_material_group(raw_item)


def _resolve_blueprint(payload: Mapping[str, Any]) -> Any | None:
    raw_item = _build_raw_ingestion_item(build_workbench_input(payload))
    group_code = infer_material_group(raw_item)
    return ExtractionBlueprintRegistry().get_blueprint(group_code) if group_code else None


def _blueprint_payload(raw_item: Module1RawIngestionItem) -> Mapping[str, Any]:
    payload = dict(raw_item.raw_characteristics or {})
    if raw_item.raw_unit:
        payload.setdefault("unit", raw_item.raw_unit)
    return payload


def _source_profile_summary(profile: Any | None) -> Mapping[str, Any] | None:
    if profile is None:
        return None
    return {
        "sourceCode": profile.source_code,
        "displayName": profile.display_name,
        "sourceType": profile.source_type,
        "status": profile.status,
        "reliability": profile.reliability,
    }


def _extraction_profile_summary(profile: Any | None) -> Mapping[str, Any] | None:
    if profile is None:
        return None
    return {
        "sourceCode": profile.source_code,
        "profileCode": profile.profile_code,
        "targetMaterialGroups": profile.target_material_groups,
        "blueprintRefs": profile.blueprint_refs,
    }


def _blueprint_summary(blueprint: Any | None) -> Mapping[str, Any] | None:
    if blueprint is None:
        return None
    return {
        "groupCode": blueprint.group_code,
        "requiredFields": blueprint.required_fields,
        "module2RequiredFields": blueprint.module2_required_fields,
        "documentHints": blueprint.document_hints,
        "unitHints": blueprint.unit_hints,
    }


def _match_candidate_from_preview(preview: Mapping[str, Any]) -> Any:
    from app.services.module1_matching_dedup import MaterialMatchCandidateDTO

    data = preview["matchCandidate"]
    return MaterialMatchCandidateDTO(
        candidate_id=data["candidate_id"],
        normalized_candidate_snapshot=data["normalized_candidate_snapshot"],
        matched_material_reference=data["matched_material_reference"],
        confidence=Decimal(str(data["confidence"])),
        decision_hint=data["decision_hint"],
        explanation=tuple(data["explanation"]),
        conflicting_fields=tuple(data["conflicting_fields"]),
        missing_fields=tuple(data["missing_fields"]),
        evidence_refs=data["evidence_refs"],
        source_refs=data["source_refs"],
        score_breakdown={key: Decimal(str(value)) for key, value in data["score_breakdown"].items()},
    )


def _extraction_profile_matches(source_code: str | None, extraction_profile_code: str | None, material_group: str | None) -> bool:
    if not source_code or not extraction_profile_code:
        return False
    profile = Module1SourceProfileRegistry().get_extraction_profile(source_code, material_group)
    return bool(profile and profile.profile_code == extraction_profile_code)


def _issue(
    issue_type: str,
    severity: str,
    field: str | None,
    message: str,
    workbench_input: ExtractionWorkbenchInput,
    blueprint_code: str | None,
    suggestion: str,
) -> ExtractionValidationIssue:
    return ExtractionValidationIssue(
        issue_type=issue_type,
        severity=severity,
        field=field,
        message=message,
        source_profile_code=workbench_input.source_profile_code,
        extraction_profile_code=workbench_input.extraction_profile_code,
        blueprint_code=blueprint_code,
        suggestion=suggestion,
    )


def _hint_for_issue(issue: ExtractionValidationIssue) -> ExtractionWorkbenchActionHint:
    mapping = {
        "missing_required_extraction_field": ("add_source_field_mapping", "Add field mapping in SourceProfile"),
        "missing_module2_field": ("add_required_characteristic", "Add required characteristic"),
        "unknown_source_profile": ("clarify_participant_source", "Clarify participant/source"),
        "unknown_extraction_profile": ("clarify_extraction_profile", "Clarify ExtractionProfile"),
        "unknown_material_group": ("add_required_characteristic", "Clarify required characteristic"),
        "unmapped_field": ("add_source_field_mapping", "Add field mapping in SourceProfile"),
        "invalid_unit": ("clarify_unit_mapping", "Clarify unit mapping"),
        "invalid_price": ("clarify_extraction_profile", "Clarify ExtractionProfile"),
        "missing_document_link": ("add_document_link", "Add document link"),
        "low_normalization_confidence": ("send_to_moderation", "Send candidate to moderation"),
        "possible_duplicate": ("check_possible_duplicate", "Check possible duplicate"),
        "pending_moderation": ("send_to_moderation", "Send candidate to moderation"),
        "insufficient_quality": ("clarify_participant_source", "Clarify participant/source"),
        "unsupported_raw_shape": ("add_source_field_mapping", "Add field mapping in SourceProfile"),
    }
    hint_type, title = mapping.get(issue.issue_type, ("review_sample", "Review extraction sample"))
    return ExtractionWorkbenchActionHint(
        hint_type=hint_type,
        title=title,
        message=issue.suggestion,
        field=issue.field,
        issue_type=issue.issue_type,
    )


def _iter_raw_fields(payload: Mapping[str, Any], characteristics: Mapping[str, Any]) -> Iterable[tuple[str, Any]]:
    for key, value in payload.items():
        if key in {"characteristics", "raw_characteristics", "attributes", "specs"}:
            continue
        yield str(key), value
    for key, value in characteristics.items():
        yield str(key), value


def _map_raw_field(raw_field: str, alias_index: Mapping[str, str]) -> str:
    field = raw_field.strip()
    return _RAW_FIELD_MAP.get(field, alias_index.get(field, field))


def _normalize_trace_value(mapped_field: str | None, raw_value: Any, unit_registry: UnitConversionRegistry) -> Any | None:
    if raw_value in (None, ""):
        return None
    if mapped_field == "unit":
        return unit_registry.normalize_unit(str(raw_value))
    if mapped_field == "price":
        return _decimal(raw_value)
    return raw_value


def _alias_index(aliases: Mapping[str, tuple[str, ...]]) -> Mapping[str, str]:
    index: dict[str, str] = {}
    for canonical, field_aliases in aliases.items():
        index[str(canonical)] = str(canonical)
        for alias in field_aliases:
            index[str(alias)] = str(canonical)
    return index


def _characteristics(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("characteristics", "raw_characteristics", "attributes", "specs"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _documents(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    documents = payload.get("documents") or payload.get("raw_documents") or payload.get("documentLinks") or payload.get("document_links") or ()
    if isinstance(documents, str):
        return ({"url": documents},)
    result: list[Mapping[str, Any]] = []
    for item in documents if isinstance(documents, (list, tuple)) else ():
        if isinstance(item, Mapping):
            result.append(dict(item))
        elif item:
            result.append({"url": str(item)})
    return tuple(result)


def _images(payload: Mapping[str, Any]) -> tuple[str, ...]:
    images = payload.get("images") or payload.get("raw_images") or ()
    if isinstance(images, str):
        return (images,)
    return tuple(str(item) for item in images if item) if isinstance(images, (list, tuple)) else tuple()


def _payload_from_legacy_shape(value: Any | None) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    payload = _get(value, "raw_payload") or _get(value, "payload") or _get(value, "parsed_data")
    if isinstance(payload, Mapping):
        return payload
    return {
        "sourceCode": _get(value, "source_code"),
        "sourceId": _get(value, "source_id"),
        "title": _first(_get(value, "raw_name"), _get(value, "name")),
        "category": _get(value, "raw_category"),
        "price": _first(_get(value, "raw_price"), _get(value, "price")),
        "unit": _first(_get(value, "raw_unit"), _get(value, "unit")),
    }


def _has_raw_price_value(payload: Mapping[str, Any]) -> bool:
    return _first(payload.get("rawPrice"), payload.get("raw_price"), payload.get("price"), payload.get("cost")) not in (None, "")


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _first_text(*values: Any) -> str | None:
    value = _first(*values)
    return str(value) if value not in (None, "") else None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(_dataclass_snapshot(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_jsonable(item) for item in value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value



def _dataclass_snapshot(value: Any) -> Mapping[str, Any]:
    return {field.name: getattr(value, field.name) for field in fields(value)}

def _stable_key(prefix: str, *parts: Any) -> str:
    payload = json.dumps(_jsonable(parts), ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _dedupe_issues(issues: Iterable[ExtractionValidationIssue]) -> tuple[ExtractionValidationIssue, ...]:
    seen: set[tuple[str, str | None, str]] = set()
    result: list[ExtractionValidationIssue] = []
    for issue in issues:
        key = (issue.issue_type, issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return tuple(result)


def _dedupe_hints(hints: Iterable[ExtractionWorkbenchActionHint]) -> tuple[ExtractionWorkbenchActionHint, ...]:
    seen: set[tuple[str, str | None, str | None]] = set()
    result: list[ExtractionWorkbenchActionHint] = []
    for hint in hints:
        key = (hint.hint_type, hint.field, hint.issue_type)
        if key in seen:
            continue
        seen.add(key)
        result.append(hint)
    return tuple(result)


_RAW_FIELD_MAP: Mapping[str, str] = {
    "title": "raw_title",
    "name": "raw_title",
    "rawTitle": "raw_title",
    "raw_title": "raw_title",
    "raw_name": "raw_title",
    "category": "raw_category",
    "rawCategory": "raw_category",
    "raw_category": "raw_category",
    "price": "price",
    "rawPrice": "price",
    "raw_price": "price",
    "cost": "price",
    "unit": "unit",
    "rawUnit": "unit",
    "raw_unit": "unit",
    "price_unit": "unit",
    "documents": "documents",
    "documentLinks": "documents",
    "document_links": "documents",
    "sourceCode": "source_code",
    "source_code": "source_code",
    "sourceUrl": "source_url",
    "source_url": "source_url",
    "url": "source_url",
}

_COMMON_MAPPED_FIELDS = frozenset(
    {
        "raw_title",
        "raw_category",
        "price",
        "unit",
        "documents",
        "source_url",
        "source_code",
    }
)

_IGNORED_METADATA_FIELDS = frozenset(
    {
        "source_code",
        "source_url",
        "adapter_version",
        "source_task_version",
        "region",
        "city",
    }
)
