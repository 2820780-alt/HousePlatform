from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from app.services.module1_alternatives_analogs import (
    build_alternative_readiness_report,
    get_module2_alternative_hints,
    get_module5_selection_hints as get_alternative_module5_hints,
)
from app.services.module1_canonical_material_store import MaterialCanonicalView
from app.services.module1_compatibility_matrix import (
    build_compatibility_readiness_report,
    get_module2_compatibility_hints,
    get_module5_selection_hints as get_compatibility_module5_hints,
)
from app.services.module1_data_quality_dashboard import (
    build_export_readiness_summary,
    build_material_quality_snapshot,
)
from app.services.module1_documents_evidence import build_document_package
from app.services.module1_material_roles import (
    build_material_role_readiness_report,
    get_module2_role_hints,
)
from app.services.module1_participants_directory import build_participant_directory_package
from app.services.module1_price_work_observations import build_price_observation_package
from app.services.module1_technical_profile_packaging import (
    build_material_technical_profile,
)


@dataclass(frozen=True)
class CleanMaterialPackage:
    material_id: str | None
    canonical_name: str
    group: Mapping[str, Any] | None
    category: Mapping[str, Any] | None
    subcategory: Mapping[str, Any] | None
    material_type: Mapping[str, Any] | None
    base_unit: str | None
    normalized_characteristics: Mapping[str, Any]
    quality_score: int
    readiness_status: str
    warnings: tuple[str, ...]
    provenance: Mapping[str, Any]
    source_refs: tuple[Mapping[str, Any], ...]
    no_side_effects: bool = True


@dataclass(frozen=True)
class TechnicalProfilePackage:
    material_id: str | None
    material_group: str | None
    technical_characteristics: Mapping[str, Any]
    module2_required_fields: tuple[str, ...]
    missing_module2_fields: tuple[str, ...]
    packaging_profile: Mapping[str, Any]
    conversion_capabilities: tuple[Mapping[str, Any], ...]
    calculation_readiness: Mapping[str, Any]
    warnings: tuple[str, ...]
    no_side_effects: bool = True


@dataclass(frozen=True)
class MaterialSelectorPackage:
    material_id: str | None
    display_name: str
    group: Mapping[str, Any] | None
    category: Mapping[str, Any] | None
    allowed_roles: tuple[str, ...]
    alternatives_summary: Mapping[str, Any]
    compatibility_summary: Mapping[str, Any]
    documents_summary: Mapping[str, Any]
    participants_summary: Mapping[str, Any]
    price_observation_summary: Mapping[str, Any]
    quality_readiness: Mapping[str, Any]
    warnings: tuple[str, ...]
    no_selected_supplier: bool = True
    no_selected_best_price: bool = True
    no_side_effects: bool = True


@dataclass(frozen=True)
class Module2TechnologyInputPackage:
    clean_material: CleanMaterialPackage
    technical_profile: TechnicalProfilePackage
    material_role_hints: tuple[Mapping[str, Any], ...]
    compatibility_hints: tuple[Mapping[str, Any], ...]
    alternative_hints: tuple[Mapping[str, Any], ...]
    unit_conversion_hints: tuple[Mapping[str, Any], ...]
    missing_fields: tuple[str, ...]
    blockers: tuple[str, ...]
    no_calculation_result: bool = True
    no_side_effects: bool = True


@dataclass(frozen=True)
class Module5EstimateInputHintPackage:
    material_selector: MaterialSelectorPackage
    base_unit: str | None
    packaging_data: Mapping[str, Any]
    price_observation_refs: tuple[Mapping[str, Any], ...]
    participant_supplier_refs: tuple[Mapping[str, Any], ...]
    document_evidence_refs: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    no_estimate_total: bool = True
    no_selected_supplier: bool = True
    no_selected_best_price: bool = True
    no_side_effects: bool = True


@dataclass(frozen=True)
class Module11AnalyticsSignalPackage:
    quality_score: int
    price_observation_presence: bool
    price_observation_count: int
    source_provenance_presence: bool
    source_provenance_count: int
    participant_coverage: Mapping[str, Any]
    document_coverage: Mapping[str, Any]
    readiness_status: str
    warnings: tuple[str, ...]
    no_charts: bool = True
    no_dynamic_analytics: bool = True
    no_side_effects: bool = True


@dataclass(frozen=True)
class ExportPackageValidationReport:
    package_type: str
    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    json_serializable: bool
    no_side_effects: bool = True


@dataclass(frozen=True)
class ExportReadinessReport:
    material_id: str | None
    ready_for_module2: bool
    ready_for_module5_selection: bool
    ready_for_quality_review: bool
    blocked_by_missing_technical_fields: bool
    blocked_by_missing_identity: bool
    blocked_by_pending_moderation: bool
    blocked_by_low_quality: bool
    warnings: tuple[str, ...]
    no_side_effects: bool = True


@dataclass(frozen=True)
class MaterialExportBundle:
    clean_material: CleanMaterialPackage
    technical_profile: TechnicalProfilePackage
    selector_package: MaterialSelectorPackage
    module2_package: Module2TechnologyInputPackage
    module5_package: Module5EstimateInputHintPackage
    module11_signals: Module11AnalyticsSignalPackage
    validation_report: ExportPackageValidationReport
    export_readiness_report: ExportReadinessReport
    no_side_effects: bool = True


def build_clean_material_package(canonical_material_view: MaterialCanonicalView) -> CleanMaterialPackage:
    quality_snapshot = build_material_quality_snapshot(canonical_material_view)
    technical_profile = build_material_technical_profile(canonical_material_view)
    return CleanMaterialPackage(
        material_id=canonical_material_view.material_id,
        canonical_name=canonical_material_view.canonical_name,
        group=_jsonable(canonical_material_view.group),
        category=_jsonable(canonical_material_view.category),
        subcategory=_jsonable(canonical_material_view.subcategory),
        material_type=_jsonable(canonical_material_view.group),
        base_unit=technical_profile.base_unit,
        normalized_characteristics=_characteristics_map(canonical_material_view),
        quality_score=quality_snapshot.overall_quality_score,
        readiness_status=quality_snapshot.readiness_status,
        warnings=_unique(canonical_material_view.warnings + quality_snapshot.warnings),
        provenance=_jsonable(canonical_material_view.source_provenance),
        source_refs=_jsonable(canonical_material_view.evidence.source_refs),
    )


def build_technical_profile_package(canonical_material_view: MaterialCanonicalView) -> TechnicalProfilePackage:
    technical_profile = build_material_technical_profile(canonical_material_view)
    return TechnicalProfilePackage(
        material_id=technical_profile.material_id,
        material_group=technical_profile.group_code,
        technical_characteristics=_jsonable(technical_profile.technical_characteristics),
        module2_required_fields=technical_profile.module2_required_fields,
        missing_module2_fields=technical_profile.missing_module2_fields,
        packaging_profile=_jsonable(technical_profile.packaging_profile),
        conversion_capabilities=tuple(_jsonable(capability) for capability in technical_profile.unit_conversion_capabilities),
        calculation_readiness=_jsonable(technical_profile.readiness),
        warnings=technical_profile.warnings,
    )


def build_material_selector_package(canonical_material_view: MaterialCanonicalView) -> MaterialSelectorPackage:
    technical_profile = build_material_technical_profile(canonical_material_view)
    role_report = build_material_role_readiness_report(technical_profile)
    alternative_report = build_alternative_readiness_report(technical_profile)
    compatibility_report = build_compatibility_readiness_report(technical_profile)
    document_package = build_document_package(canonical_material_view)
    participant_package = build_participant_directory_package(canonical_material_view)
    price_package = build_price_observation_package(canonical_material_view)
    quality_snapshot = build_material_quality_snapshot(canonical_material_view)
    warnings = _unique(
        role_report.warnings
        + alternative_report.warnings
        + compatibility_report.warnings
        + document_package.warnings
        + participant_package.warnings
        + price_package.warnings
        + quality_snapshot.warnings
    )
    return MaterialSelectorPackage(
        material_id=canonical_material_view.material_id,
        display_name=canonical_material_view.canonical_name,
        group=_jsonable(canonical_material_view.group),
        category=_jsonable(canonical_material_view.category),
        allowed_roles=role_report.applicable_role_codes,
        alternatives_summary={
            "status": alternative_report.status,
            "allowedTargetGroups": alternative_report.allowed_target_groups,
            "forbiddenTargetGroups": alternative_report.forbidden_target_groups,
            "missingFields": alternative_report.missing_fields,
        },
        compatibility_summary={
            "status": compatibility_report.status,
            "allowedContexts": compatibility_report.allowed_contexts,
            "forbiddenContexts": compatibility_report.forbidden_contexts,
            "missingFields": compatibility_report.missing_fields,
        },
        documents_summary={
            "documentCount": len(document_package.documents),
            "missingDocumentHints": document_package.missing_document_hints,
            "status": document_package.readiness.status,
        },
        participants_summary={
            "participantCount": len(participant_package.participants),
            "participantTypes": participant_package.readiness.participant_types,
            "hasSupplier": participant_package.readiness.has_supplier,
            "hasManufacturer": participant_package.readiness.has_manufacturer,
        },
        price_observation_summary={
            "priceObservationCount": len(price_package.observations),
            "hasPrices": price_package.readiness.has_prices,
            "status": price_package.readiness.status,
            "selectedSupplier": None,
            "selectedBestPrice": None,
        },
        quality_readiness={
            "qualityScore": quality_snapshot.overall_quality_score,
            "readinessStatus": quality_snapshot.readiness_status,
            "exportReadiness": build_export_readiness_summary(quality_snapshot),
        },
        warnings=warnings,
    )


def build_module2_technology_input_package(canonical_material_view: MaterialCanonicalView) -> Module2TechnologyInputPackage:
    clean_package = build_clean_material_package(canonical_material_view)
    technical_package = build_technical_profile_package(canonical_material_view)
    technical_profile = build_material_technical_profile(canonical_material_view)
    compatibility_report = build_compatibility_readiness_report(technical_profile)
    readiness = build_export_readiness_report(canonical_material_view)
    blockers = []
    if readiness.blocked_by_missing_identity:
        blockers.append("missing_identity")
    if readiness.blocked_by_missing_technical_fields:
        blockers.append("missing_technical_fields")
    if readiness.blocked_by_pending_moderation:
        blockers.append("pending_moderation")
    if readiness.blocked_by_low_quality:
        blockers.append("low_quality")
    return Module2TechnologyInputPackage(
        clean_material=clean_package,
        technical_profile=technical_package,
        material_role_hints=_jsonable(get_module2_role_hints(technical_profile)),
        compatibility_hints=_jsonable(compatibility_report.module2_hints),
        alternative_hints=_jsonable(get_module2_alternative_hints(technical_profile)),
        unit_conversion_hints=tuple(
            {
                "fromUnit": capability["from_unit"],
                "toUnit": capability["to_unit"],
                "supported": capability["supported"],
                "requiresMaterialProfile": capability["requires_material_profile"],
                "missingFields": capability["missing_fields"],
            }
            for capability in technical_package.conversion_capabilities
        ),
        missing_fields=_unique(technical_package.missing_module2_fields + tuple(technical_package.calculation_readiness.get("missing_required_fields", ()))),
        blockers=tuple(blockers),
    )


def build_module5_estimate_input_hint_package(canonical_material_view: MaterialCanonicalView) -> Module5EstimateInputHintPackage:
    selector = build_material_selector_package(canonical_material_view)
    technical_package = build_technical_profile_package(canonical_material_view)
    document_package = build_document_package(canonical_material_view)
    participant_package = build_participant_directory_package(canonical_material_view)
    price_package = build_price_observation_package(canonical_material_view)
    technical_profile = build_material_technical_profile(canonical_material_view)
    alternative_report = build_alternative_readiness_report(technical_profile)
    compatibility_report = build_compatibility_readiness_report(technical_profile)
    warnings = _unique(
        selector.warnings
        + tuple(getattr(document_package.readiness, "warnings", tuple()))
        + tuple(getattr(participant_package.readiness, "warnings", tuple()))
        + tuple(getattr(price_package.readiness, "warnings", tuple()))
    )
    return Module5EstimateInputHintPackage(
        material_selector=selector,
        base_unit=technical_profile.base_unit,
        packaging_data=technical_package.packaging_profile,
        price_observation_refs=tuple(_price_observation_ref(observation) for observation in price_package.observations),
        participant_supplier_refs=tuple(_participant_ref(participant) for participant in participant_package.participants if participant.participant_type in {"supplier", "manufacturer", "brand", "distributor"}),
        document_evidence_refs=tuple(_document_ref(document) for document in document_package.documents),
        warnings=_unique(warnings + alternative_report.warnings + compatibility_report.warnings),
    )


def build_module11_analytics_signal_package(canonical_material_view: MaterialCanonicalView) -> Module11AnalyticsSignalPackage:
    quality_snapshot = build_material_quality_snapshot(canonical_material_view)
    participant_package = build_participant_directory_package(canonical_material_view)
    document_package = build_document_package(canonical_material_view)
    price_package = build_price_observation_package(canonical_material_view)
    source_refs = canonical_material_view.evidence.source_refs
    warnings = _unique(quality_snapshot.warnings + participant_package.warnings + document_package.warnings + price_package.warnings)
    return Module11AnalyticsSignalPackage(
        quality_score=quality_snapshot.overall_quality_score,
        price_observation_presence=bool(price_package.observations),
        price_observation_count=len(price_package.observations),
        source_provenance_presence=bool(source_refs),
        source_provenance_count=len(source_refs),
        participant_coverage={
            "participantCount": len(participant_package.participants),
            "participantTypes": participant_package.readiness.participant_types,
            "hasSupplier": participant_package.readiness.has_supplier,
            "hasManufacturer": participant_package.readiness.has_manufacturer,
        },
        document_coverage={
            "documentCount": len(document_package.documents),
            "requiredDocumentHints": document_package.required_document_hints,
            "missingDocumentHints": document_package.missing_document_hints,
            "status": document_package.readiness.status,
        },
        readiness_status=quality_snapshot.readiness_status,
        warnings=warnings,
    )


def build_export_readiness_report(canonical_material_view: MaterialCanonicalView) -> ExportReadinessReport:
    technical_profile = build_material_technical_profile(canonical_material_view)
    selector = build_material_selector_package(canonical_material_view)
    quality_snapshot = build_material_quality_snapshot(canonical_material_view)
    blocked_by_missing_identity = not bool(canonical_material_view.material_id and canonical_material_view.canonical_name and technical_profile.group_code)
    blocked_by_missing_technical = bool(
        technical_profile.readiness.missing_required_fields
        or technical_profile.missing_module2_fields
    )
    moderation_status = (canonical_material_view.moderation_status or "").lower()
    blocked_by_pending_moderation = moderation_status in {"pending", "needs_review", "possible_duplicate", "moderation_required"}
    blocked_by_low_quality = quality_snapshot.overall_quality_score < 55
    ready_for_module2 = not (
        blocked_by_missing_identity
        or blocked_by_missing_technical
        or blocked_by_pending_moderation
        or blocked_by_low_quality
    )
    ready_for_module5_selection = not blocked_by_missing_identity and not blocked_by_pending_moderation and bool(
        selector.price_observation_summary.get("hasPrices")
        or selector.participants_summary.get("participantCount")
        or selector.documents_summary.get("documentCount")
    )
    warnings = []
    if blocked_by_missing_identity:
        warnings.append("Material identity is incomplete.")
    if blocked_by_missing_technical:
        warnings.append("Required technical fields are missing.")
    if blocked_by_pending_moderation:
        warnings.append("Material is blocked by pending moderation state.")
    if blocked_by_low_quality:
        warnings.append("Material quality score is too low for direct export.")
    warnings.extend(quality_snapshot.warnings)
    return ExportReadinessReport(
        material_id=canonical_material_view.material_id,
        ready_for_module2=ready_for_module2,
        ready_for_module5_selection=ready_for_module5_selection,
        ready_for_quality_review=not ready_for_module2 or not ready_for_module5_selection,
        blocked_by_missing_technical_fields=blocked_by_missing_technical,
        blocked_by_missing_identity=blocked_by_missing_identity,
        blocked_by_pending_moderation=blocked_by_pending_moderation,
        blocked_by_low_quality=blocked_by_low_quality,
        warnings=_unique(tuple(warnings)),
    )


def validate_export_package(package: Any) -> ExportPackageValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if package is None:
        errors.append("Package is missing.")
    if not getattr(package, "no_side_effects", True):
        errors.append("Package must be marked no_side_effects=True.")
    json_serializable = _is_json_serializable(package)
    if not json_serializable:
        errors.append("Package is not JSON serializable.")
    if isinstance(package, MaterialExportBundle):
        if not package.clean_material.canonical_name:
            errors.append("Clean material canonical_name is missing.")
        if package.module5_package.no_selected_best_price is not True:
            errors.append("Module5 package must not select best price.")
        if package.module2_package.no_calculation_result is not True:
            errors.append("Module2 package must not contain calculation result.")
        if package.module11_signals.no_charts is not True:
            errors.append("Module11 package must not contain charts.")
    return ExportPackageValidationReport(
        package_type=type(package).__name__ if package is not None else "None",
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        json_serializable=json_serializable,
    )


def build_material_export_bundle(canonical_material_view: MaterialCanonicalView) -> MaterialExportBundle:
    clean_package = build_clean_material_package(canonical_material_view)
    technical_package = build_technical_profile_package(canonical_material_view)
    selector_package = build_material_selector_package(canonical_material_view)
    module2_package = build_module2_technology_input_package(canonical_material_view)
    module5_package = build_module5_estimate_input_hint_package(canonical_material_view)
    module11_package = build_module11_analytics_signal_package(canonical_material_view)
    readiness = build_export_readiness_report(canonical_material_view)
    bundle = MaterialExportBundle(
        clean_material=clean_package,
        technical_profile=technical_package,
        selector_package=selector_package,
        module2_package=module2_package,
        module5_package=module5_package,
        module11_signals=module11_package,
        validation_report=ExportPackageValidationReport(
            package_type="MaterialExportBundle",
            is_valid=True,
            errors=tuple(),
            warnings=tuple(),
            json_serializable=True,
        ),
        export_readiness_report=readiness,
    )
    validation = validate_export_package(bundle)
    return MaterialExportBundle(
        clean_material=bundle.clean_material,
        technical_profile=bundle.technical_profile,
        selector_package=bundle.selector_package,
        module2_package=bundle.module2_package,
        module5_package=bundle.module5_package,
        module11_signals=bundle.module11_signals,
        validation_report=validation,
        export_readiness_report=bundle.export_readiness_report,
    )


def build_bulk_export_report(canonical_material_views: Iterable[MaterialCanonicalView]) -> Mapping[str, Any]:
    bundles = tuple(build_material_export_bundle(view) for view in canonical_material_views)
    by_readiness = {
        "readyForModule2": sum(1 for bundle in bundles if bundle.export_readiness_report.ready_for_module2),
        "readyForModule5Selection": sum(1 for bundle in bundles if bundle.export_readiness_report.ready_for_module5_selection),
        "needsQualityReview": sum(1 for bundle in bundles if bundle.export_readiness_report.ready_for_quality_review),
        "blockedByTechnicalFields": sum(1 for bundle in bundles if bundle.export_readiness_report.blocked_by_missing_technical_fields),
        "blockedByModeration": sum(1 for bundle in bundles if bundle.export_readiness_report.blocked_by_pending_moderation),
        "blockedByLowQuality": sum(1 for bundle in bundles if bundle.export_readiness_report.blocked_by_low_quality),
    }
    return {
        "totalMaterials": len(bundles),
        "byReadiness": by_readiness,
        "materialIds": tuple(bundle.clean_material.material_id for bundle in bundles),
        "filesWritten": False,
        "no_side_effects": True,
    }


def _characteristics_map(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    return {
        characteristic.name: _jsonable(characteristic.value)
        for characteristic in canonical_material_view.characteristics
        if characteristic.name
    }


def _price_observation_ref(observation: Any) -> Mapping[str, Any]:
    return {
        "observationId": observation.observation_id,
        "stableKey": observation.stable_key,
        "priceValue": _jsonable(observation.price_value),
        "currency": observation.currency,
        "priceUnit": observation.price_unit,
        "participant": _participant_ref(observation.participant) if observation.participant else None,
        "sourceRef": _jsonable(observation.source_ref),
        "selectedAsBestPrice": False,
    }


def _participant_ref(participant: Any) -> Mapping[str, Any]:
    return {
        "participantId": participant.participant_id,
        "stableKey": participant.stable_key,
        "participantType": participant.participant_type,
        "displayName": participant.display_name,
        "confidence": _jsonable(participant.confidence),
    }


def _document_ref(document: Any) -> Mapping[str, Any]:
    return {
        "documentId": document.document_id,
        "title": document.title,
        "documentType": document.document_type,
        "fileUrl": document.file_url,
        "sourceUrl": document.source_url,
        "status": document.status,
    }


def _is_json_serializable(value: Any) -> bool:
    try:
        import json

        json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return False
    return True


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
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


def _unique(values: Iterable[Any]) -> tuple[Any, ...]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return tuple(result)
