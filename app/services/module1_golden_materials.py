from __future__ import annotations

import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_alternatives_analogs import build_alternative_readiness_report
from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_compatibility_matrix import build_compatibility_readiness_report
from app.services.module1_data_quality_dashboard import (
    MaterialDataQualitySnapshot,
    build_material_quality_snapshot,
)
from app.services.module1_documents_evidence import build_document_package
from app.services.module1_export_packages import MaterialExportBundle, build_material_export_bundle
from app.services.module1_material_roles import build_material_role_readiness_report
from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)
from app.services.module1_participants_directory import build_participant_directory_package
from app.services.module1_price_work_observations import build_price_observation_package
from app.services.module1_technical_profile_packaging import build_material_technical_profile
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


DEFAULT_GOLDEN_MATERIALS_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "src/modules/module1/seeds/golden_materials_seed.json"
)


class GoldenMaterialsSeedError(ValueError):
    pass


@dataclass(frozen=True)
class GoldenMaterialCharacteristicSet:
    values: Mapping[str, Any]


@dataclass(frozen=True)
class GoldenMaterialPackagingSet:
    values: Mapping[str, Any]


@dataclass(frozen=True)
class GoldenMaterialEvidenceSet:
    documents: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class GoldenMaterialParticipantSet:
    participants: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class GoldenMaterialPriceObservationSet:
    observations: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class GoldenMaterialRecord:
    golden_material_code: str
    display_name: str
    group_code: str
    category: Mapping[str, Any]
    subcategory: Mapping[str, Any] | None
    base_unit: str
    characteristics: GoldenMaterialCharacteristicSet
    packaging: GoldenMaterialPackagingSet
    evidence: GoldenMaterialEvidenceSet
    participants: GoldenMaterialParticipantSet
    price_observations: GoldenMaterialPriceObservationSet
    quality_expectations: Mapping[str, Any]
    module2_readiness_expectation: str
    module5_readiness_hint_expectation: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class GoldenMaterialValidationReport:
    golden_material_code: str
    group_code: str
    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    missing_required_characteristics: tuple[str, ...]
    missing_module2_characteristics: tuple[str, ...]
    export_preview_available: bool
    json_serializable: bool
    no_side_effects: bool = True


@dataclass(frozen=True)
class GoldenMaterialExportPreview:
    golden_material_code: str
    canonical_view: Mapping[str, Any]
    export_bundle: MaterialExportBundle
    validation_report: GoldenMaterialValidationReport
    no_side_effects: bool = True


@dataclass(frozen=True)
class GoldenMaterialRegistry:
    version: str
    module: str
    purpose: str
    golden_materials: Mapping[str, GoldenMaterialRecord]


def load_golden_materials_seed(
    path: Path | str = DEFAULT_GOLDEN_MATERIALS_SEED_PATH,
) -> GoldenMaterialRegistry:
    seed_path = Path(path)
    if not seed_path.exists():
        raise GoldenMaterialsSeedError(f"Module 1 golden materials seed not found: {seed_path}")
    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise GoldenMaterialsSeedError(f"Module 1 golden materials seed is not valid JSON: {exc}") from exc
    return build_golden_material_registry(raw)


@lru_cache(maxsize=1)
def get_golden_material_registry() -> GoldenMaterialRegistry:
    return load_golden_materials_seed(DEFAULT_GOLDEN_MATERIALS_SEED_PATH)


def build_golden_material_registry(raw: Mapping[str, Any]) -> GoldenMaterialRegistry:
    errors = _validate_seed_shape(raw)
    if errors:
        raise GoldenMaterialsSeedError("; ".join(errors))
    records = tuple(_record_from_raw(item) for item in raw["goldenMaterials"])
    by_code = {record.golden_material_code: record for record in records}
    if len(by_code) != len(records):
        raise GoldenMaterialsSeedError("golden material codes must be unique")
    return GoldenMaterialRegistry(
        version=str(raw["version"]),
        module=str(raw["module"]),
        purpose=str(raw["purpose"]),
        golden_materials=MappingProxyType(by_code),
    )


def list_golden_materials() -> tuple[GoldenMaterialRecord, ...]:
    return tuple(get_golden_material_registry().golden_materials.values())


def get_golden_material(golden_material_code: str) -> GoldenMaterialRecord | None:
    return get_golden_material_registry().golden_materials.get(golden_material_code)


def list_golden_materials_by_group(group_code: str) -> tuple[GoldenMaterialRecord, ...]:
    return tuple(record for record in list_golden_materials() if record.group_code == group_code)


def build_golden_material_like_object(golden_material_code: str) -> Mapping[str, Any]:
    record = _require_record(golden_material_code)
    return {
        "id": record.golden_material_code,
        "canonical_name": record.display_name,
        "group_code": record.group_code,
        "category": record.category,
        "subcategory": record.subcategory,
        "base_unit": record.base_unit,
        "characteristics": record.characteristics.values,
        "packaging": record.packaging.values,
        "documents": record.evidence.documents,
        "participants": record.participants.participants,
        "price_observations": record.price_observations.observations,
        "fixtureOnly": True,
        "rawDataIsCanonical": False,
    }


def build_golden_canonical_view(golden_material_code: str) -> MaterialCanonicalView:
    record = _require_record(golden_material_code)
    characteristics = tuple(
        MaterialCharacteristicView(name=str(name), value=value, unit=None)
        for name, value in record.characteristics.values.items()
    )
    source_refs = tuple()
    return MaterialCanonicalView(
        material_id=record.golden_material_code,
        canonical_name=record.display_name,
        category=record.category,
        subcategory=record.subcategory,
        group={"code": record.group_code, "name": record.group_code},
        characteristics=characteristics,
        technical_profile_hints={"baseUnit": {"abbreviation": record.base_unit}},
        evidence=MaterialEvidenceSummary(
            document_count=len(record.evidence.documents),
            source_ref_count=len(source_refs),
            documents=record.evidence.documents,
            source_refs=source_refs,
            moderation_preview_refs=tuple(),
            warnings=tuple(),
        ),
        supplier_price_refs=record.price_observations.observations,
        moderation_status="approved",
        quality=MaterialQualitySummary(
            status="ok",
            open_issues=0,
            critical_issues=0,
            warning_issues=0,
            issues=tuple(),
            warnings=tuple(),
        ),
        source_provenance={
            "canonicalBase": "GoldenMaterialFixture",
            "rawDataIsCanonical": False,
            "fixtureOnly": True,
            "sourceDetailsLocation": "golden_materials_seed",
        },
        status="fixture",
        warnings=record.warnings,
        created_at=None,
        updated_at=None,
    )


def validate_golden_material(record: GoldenMaterialRecord) -> GoldenMaterialValidationReport:
    seed_registry = get_material_knowledge_seed_registry()
    schema_registry = CharacteristicSchemaRegistry(seed_registry)
    unit_registry = UnitConversionRegistry(seed_registry)
    schema = schema_registry.get_schema(record.group_code)
    required = tuple(field.code for field in schema.required) if schema else tuple()
    module2_required = tuple(field.code for field in schema.module2_required) if schema else tuple()
    provided = set(record.characteristics.values)
    missing_required = tuple(field for field in required if field not in provided)
    missing_module2 = tuple(field for field in module2_required if field not in provided)
    errors: list[str] = []
    warnings: list[str] = list(record.warnings)

    if not seed_registry.has_material_group(record.group_code):
        errors.append("group_code is not present in material taxonomy")
    if schema is None:
        errors.append("characteristic schema is missing for group_code")
    if missing_required:
        errors.append("required characteristics are missing")
    if unit_registry.normalize_unit(record.base_unit) is None:
        warnings.append(f"base_unit '{record.base_unit}' is not recognized by unit dictionary")

    export_preview_available = False
    try:
        canonical_view = build_golden_canonical_view(record.golden_material_code)
        technical_profile = build_material_technical_profile(canonical_view)
        build_material_role_readiness_report(technical_profile)
        build_alternative_readiness_report(technical_profile)
        build_compatibility_readiness_report(technical_profile)
        build_document_package(canonical_view)
        build_participant_directory_package(canonical_view)
        build_price_observation_package(canonical_view)
        build_material_quality_snapshot(canonical_view)
        build_material_export_bundle(canonical_view)
        export_preview_available = True
    except Exception as exc:  # pragma: no cover - defensive report path
        errors.append(f"golden material preview failed: {exc}")

    json_serializable = _is_json_serializable(record)
    if not json_serializable:
        errors.append("record is not JSON serializable")

    return GoldenMaterialValidationReport(
        golden_material_code=record.golden_material_code,
        group_code=record.group_code,
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(dict.fromkeys(warnings)),
        missing_required_characteristics=missing_required,
        missing_module2_characteristics=missing_module2,
        export_preview_available=export_preview_available,
        json_serializable=json_serializable,
    )


def validate_all_golden_materials() -> tuple[GoldenMaterialValidationReport, ...]:
    return tuple(validate_golden_material(record) for record in list_golden_materials())


def build_golden_material_export_preview(golden_material_code: str) -> GoldenMaterialExportPreview:
    record = _require_record(golden_material_code)
    validation = validate_golden_material(record)
    canonical_view = build_golden_canonical_view(golden_material_code)
    return GoldenMaterialExportPreview(
        golden_material_code=golden_material_code,
        canonical_view=_jsonable(canonical_view),
        export_bundle=build_material_export_bundle(canonical_view),
        validation_report=validation,
    )


def build_golden_material_quality_snapshot(golden_material_code: str) -> MaterialDataQualitySnapshot:
    return build_material_quality_snapshot(build_golden_canonical_view(golden_material_code))


def build_golden_material_test_matrix() -> Mapping[str, Any]:
    records = list_golden_materials()
    reports = validate_all_golden_materials()
    covered_groups = tuple(sorted({record.group_code for record in records}))
    return {
        "totalGoldenMaterials": len(records),
        "coveredGroups": covered_groups,
        "validRecords": sum(1 for report in reports if report.is_valid),
        "invalidRecords": tuple(report.golden_material_code for report in reports if not report.is_valid),
        "exportPreviewReady": sum(1 for report in reports if report.export_preview_available),
        "fixtureOnly": True,
        "databaseWrites": False,
        "no_side_effects": True,
    }


def _record_from_raw(item: Mapping[str, Any]) -> GoldenMaterialRecord:
    return GoldenMaterialRecord(
        golden_material_code=str(item["goldenMaterialCode"]),
        display_name=str(item["displayName"]),
        group_code=str(item["groupCode"]),
        category=MappingProxyType(dict(item.get("category") or {})),
        subcategory=MappingProxyType(dict(item.get("subcategory") or {})) if item.get("subcategory") else None,
        base_unit=str(item["baseUnit"]),
        characteristics=GoldenMaterialCharacteristicSet(MappingProxyType(dict(item.get("characteristics") or {}))),
        packaging=GoldenMaterialPackagingSet(MappingProxyType(dict(item.get("packaging") or {}))),
        evidence=GoldenMaterialEvidenceSet(tuple(dict(document) for document in item.get("documents", ()))),
        participants=GoldenMaterialParticipantSet(tuple(dict(participant) for participant in item.get("participants", ()))),
        price_observations=GoldenMaterialPriceObservationSet(tuple(dict(observation) for observation in item.get("priceObservations", ()))),
        quality_expectations=MappingProxyType(dict(item.get("qualityExpectations") or {})),
        module2_readiness_expectation=str(item.get("module2ReadinessExpectation") or ""),
        module5_readiness_hint_expectation=str(item.get("module5ReadinessHintExpectation") or ""),
        warnings=tuple(str(warning) for warning in item.get("warnings", ())),
    )


def _validate_seed_shape(raw: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    for section in ("version", "module", "purpose", "goldenMaterials"):
        if section not in raw:
            errors.append(f"missing required section: {section}")
    if errors:
        return tuple(errors)
    if not isinstance(raw["goldenMaterials"], list) or not raw["goldenMaterials"]:
        errors.append("goldenMaterials must be a non-empty list")
        return tuple(errors)
    required_fields = ("goldenMaterialCode", "displayName", "groupCode", "baseUnit", "characteristics")
    for index, item in enumerate(raw["goldenMaterials"]):
        if not isinstance(item, Mapping):
            errors.append(f"goldenMaterials[{index}] must be an object")
            continue
        for field in required_fields:
            if field not in item:
                errors.append(f"goldenMaterials[{index}] missing required field: {field}")
    return tuple(errors)


def _require_record(golden_material_code: str) -> GoldenMaterialRecord:
    record = get_golden_material(golden_material_code)
    if record is None:
        raise GoldenMaterialsSeedError(f"Golden material is not registered: {golden_material_code}")
    return record


def _participant_source_ref(participant: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "sourceId": participant.get("participantId"),
        "sourceName": participant.get("displayName"),
        "sourceType": participant.get("participantType"),
        "reliability": "fixture",
        "fixtureOnly": True,
    }


def _is_json_serializable(value: Any) -> bool:
    try:
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
