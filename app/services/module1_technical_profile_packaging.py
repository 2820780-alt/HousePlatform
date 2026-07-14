from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from app.services.module1_canonical_material_store import MaterialCanonicalView
from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_extraction_blueprint_registry import ExtractionBlueprintRegistry
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


PACKAGING_FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "package_unit": ("package_unit", "unit", "normalized_unit"),
    "package_weight_kg": ("package_weight_kg", "weight_kg", "bag_weight_kg"),
    "package_volume_m3": ("package_volume_m3", "package_volume", "volume_per_package_m3"),
    "package_volume_l": ("package_volume_l", "canister_volume_l", "package_volume_liter"),
    "package_area_m2": ("package_area_m2", "area_per_pack_m2", "area_per_box_m2"),
    "pieces_per_package": ("pieces_per_package", "pieces_per_pack", "sheets_per_pack", "slabs_per_pack"),
    "pieces_per_pallet": ("pieces_per_pallet", "pallet_quantity", "pieces_per_pallet_qty"),
    "roll_width_m": ("roll_width_m", "roll_width_mm"),
    "roll_length_m": ("roll_length_m", "roll_length_mm"),
    "roll_area_m2": ("roll_area_m2",),
    "sheet_length_mm": ("sheet_length_mm", "length_mm"),
    "sheet_width_mm": ("sheet_width_mm", "width_mm"),
    "sheet_area_m2": ("sheet_area_m2",),
    "bag_weight_kg": ("bag_weight_kg", "package_weight_kg"),
    "pallet_quantity": ("pallet_quantity", "pieces_per_pallet"),
}

GROUP_CONVERSION_PAIRS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "rebar": (("linear_meter", "kg"), ("kg", "linear_meter"), ("kg", "ton")),
    "aerated_concrete_block": (("piece", "m3"), ("m3", "piece"), ("piece", "m2"), ("piece", "pallet")),
    "gypsum_board_moisture_resistant": (("sheet", "m2"), ("m2", "sheet"), ("sheet", "package")),
    "ready_mix_concrete": (("m3", "m3"),),
    "gypsum_plaster": (("kg", "m2"), ("m2", "kg"), ("kg", "bag")),
    "deep_penetration_primer": (("liter", "m2"), ("m2", "liter"), ("liter", "package")),
    "porcelain_tile": (("m2", "piece"), ("m2", "package"), ("piece", "package")),
    "metal_tile": (("sheet", "m2"), ("m2", "sheet"), ("linear_meter", "m2")),
    "board": (("piece", "m3"), ("m3", "piece"), ("linear_meter", "m3")),
    "mineral_wool_slab": (("package", "m2"), ("package", "m3"), ("m2", "package")),
}


@dataclass(frozen=True)
class MaterialConversionCapability:
    from_unit: str
    to_unit: str
    supported: bool
    requires_material_profile: bool
    required_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    alternative_field_sets: tuple[tuple[str, ...], ...]
    formula: str | None
    message: str


@dataclass(frozen=True)
class MaterialPackagingProfile:
    material_id: str | None
    material_name: str
    group_code: str | None
    package_unit: str | None
    package_weight: Any | None
    package_volume: Any | None
    package_area: Any | None
    pieces_per_package: Any | None
    pieces_per_pallet: Any | None
    roll_width: Any | None
    roll_length: Any | None
    roll_area: Any | None
    sheet_length: Any | None
    sheet_width: Any | None
    sheet_area: Any | None
    bag_weight: Any | None
    pallet_quantity: Any | None
    fields: Mapping[str, Any]
    missing_fields: tuple[str, ...]
    conversion_hints: tuple[str, ...]


@dataclass(frozen=True)
class MaterialCalculationReadiness:
    material_id: str | None
    status: str
    ready_for_module2: bool
    ready_for_estimate_selection: bool
    missing_required_fields: tuple[str, ...]
    missing_module2_fields: tuple[str, ...]
    missing_packaging_fields: tuple[str, ...]
    quality_warnings: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class TechnicalProfileValidationReport:
    material_id: str | None
    group_code: str | None
    is_valid: bool
    required_fields: tuple[str, ...]
    module2_required_fields: tuple[str, ...]
    packaging_fields: tuple[str, ...]
    provided_fields: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    missing_module2_fields: tuple[str, ...]
    missing_packaging_fields: tuple[str, ...]
    conversion_warnings: tuple[str, ...]
    quality_warnings: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class MaterialTechnicalProfile:
    material_id: str | None
    material_name: str
    group_code: str | None
    category: Mapping[str, Any] | None
    base_unit: str | None
    technical_characteristics: Mapping[str, Any]
    module2_required_fields: tuple[str, ...]
    missing_module2_fields: tuple[str, ...]
    packaging_profile: MaterialPackagingProfile
    unit_conversion_capabilities: tuple[MaterialConversionCapability, ...]
    usage_hints: Mapping[str, Any]
    readiness: MaterialCalculationReadiness
    quality_status: str
    warnings: tuple[str, ...]


def build_material_technical_profile(canonical_material_view: MaterialCanonicalView) -> MaterialTechnicalProfile:
    group_code = _group_code(canonical_material_view)
    characteristics = _characteristics_map(canonical_material_view)
    packaging_profile = build_packaging_profile(canonical_material_view)
    capabilities = build_conversion_capabilities(canonical_material_view)
    readiness = build_calculation_readiness_report(canonical_material_view)
    blueprint = ExtractionBlueprintRegistry().get_blueprint(group_code) if group_code else None
    warnings = tuple(
        dict.fromkeys(
            canonical_material_view.warnings
            + readiness.warnings
            + tuple(capability.message for capability in capabilities if capability.supported and capability.missing_fields)
        )
    )
    return MaterialTechnicalProfile(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        group_code=group_code,
        category=canonical_material_view.category,
        base_unit=_base_unit(canonical_material_view),
        technical_characteristics=characteristics,
        module2_required_fields=list_module2_required_fields(group_code),
        missing_module2_fields=readiness.missing_module2_fields,
        packaging_profile=packaging_profile,
        unit_conversion_capabilities=capabilities,
        usage_hints={
            "documentHints": blueprint.document_hints if blueprint else tuple(),
            "unitHints": blueprint.unit_hints if blueprint else tuple(),
            "module1Only": True,
            "module2Calculations": "not_performed_by_module1",
            "module5Costing": "not_performed_by_module1",
        },
        readiness=readiness,
        quality_status=canonical_material_view.quality.status,
        warnings=warnings,
    )


def build_packaging_profile(canonical_material_view: MaterialCanonicalView) -> MaterialPackagingProfile:
    group_code = _group_code(canonical_material_view)
    characteristics = _characteristics_map(canonical_material_view)
    expected_fields = list_packaging_fields(group_code)
    fields = {canonical: _first_present(characteristics, aliases) for canonical, aliases in PACKAGING_FIELD_ALIASES.items()}
    fields = {key: value for key, value in fields.items() if value not in (None, "")}
    missing = tuple(field for field in expected_fields if _lookup_packaging_value(field, fields, characteristics) in (None, ""))
    return MaterialPackagingProfile(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        group_code=group_code,
        package_unit=_as_string(fields.get("package_unit")),
        package_weight=fields.get("package_weight_kg"),
        package_volume=fields.get("package_volume_m3") or fields.get("package_volume_l"),
        package_area=fields.get("package_area_m2"),
        pieces_per_package=fields.get("pieces_per_package"),
        pieces_per_pallet=fields.get("pieces_per_pallet"),
        roll_width=fields.get("roll_width_m"),
        roll_length=fields.get("roll_length_m"),
        roll_area=fields.get("roll_area_m2"),
        sheet_length=fields.get("sheet_length_mm"),
        sheet_width=fields.get("sheet_width_mm"),
        sheet_area=fields.get("sheet_area_m2"),
        bag_weight=fields.get("bag_weight_kg"),
        pallet_quantity=fields.get("pallet_quantity"),
        fields=fields,
        missing_fields=missing,
        conversion_hints=_packaging_conversion_hints(group_code),
    )


def build_calculation_readiness_report(canonical_material_view: MaterialCanonicalView) -> MaterialCalculationReadiness:
    profile = _profile_snapshot(canonical_material_view)
    missing_report = build_missing_technical_fields_report(profile)
    quality_warnings = tuple(canonical_material_view.quality.warnings)
    warnings: list[str] = []
    if not profile.get("group_code"):
        warnings.append("Material group code is missing.")
    warnings.extend(quality_warnings)
    warnings.extend(missing_report.conversion_warnings)
    if canonical_material_view.quality.open_issues or canonical_material_view.moderation_status == "needs_review":
        status = "needs_moderation"
    elif missing_report.missing_required_fields:
        status = "insufficient_data"
    elif missing_report.missing_module2_fields:
        status = "missing_module2_fields"
    elif not missing_report.missing_packaging_fields:
        status = "ready_for_module2"
    else:
        status = "ready_for_estimate_selection"
    return MaterialCalculationReadiness(
        material_id=canonical_material_view.material_id,
        status=status,
        ready_for_module2=status == "ready_for_module2",
        ready_for_estimate_selection=status in {"ready_for_module2", "ready_for_estimate_selection"},
        missing_required_fields=missing_report.missing_required_fields,
        missing_module2_fields=missing_report.missing_module2_fields,
        missing_packaging_fields=missing_report.missing_packaging_fields,
        quality_warnings=quality_warnings,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def list_required_technical_fields(group_code: str | None) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    return CharacteristicSchemaRegistry().get_required_characteristics(group_code)


def list_module2_required_fields(group_code: str | None) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    return CharacteristicSchemaRegistry().get_module2_required_characteristics(group_code)


def list_packaging_fields(group_code: str | None) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    return ExtractionBlueprintRegistry().get_packaging_fields(group_code)


def build_conversion_capabilities(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialConversionCapability, ...]:
    group_code = _group_code(canonical_material_view)
    if not group_code:
        return tuple()
    unit_registry = UnitConversionRegistry()
    profile = _characteristics_map(canonical_material_view)
    pairs = _conversion_pairs(group_code, canonical_material_view)
    capabilities: list[MaterialConversionCapability] = []
    seen: set[tuple[str, str]] = set()
    for from_unit, to_unit in pairs:
        canonical_from = unit_registry.normalize_unit(from_unit) or from_unit
        canonical_to = unit_registry.normalize_unit(to_unit) or to_unit
        key = (canonical_from, canonical_to)
        if key in seen:
            continue
        seen |= {key}
        requirements = unit_registry.build_conversion_requirements(from_unit, to_unit, group_code)
        missing = _missing_conversion_fields(requirements.alternative_field_sets, profile)
        capabilities.append(
            MaterialConversionCapability(
                from_unit=canonical_from,
                to_unit=canonical_to,
                supported=requirements.supported,
                requires_material_profile=requirements.requires_material_profile,
                required_fields=requirements.required_fields,
                missing_fields=missing,
                alternative_field_sets=requirements.alternative_field_sets,
                formula=requirements.formula,
                message=requirements.message,
            )
        )
    return tuple(capabilities)


def validate_technical_profile(profile: MaterialTechnicalProfile) -> TechnicalProfileValidationReport:
    return _build_validation_report(
        material_id=profile.material_id,
        group_code=profile.group_code,
        characteristics=profile.technical_characteristics,
        packaging_profile=profile.packaging_profile,
        capabilities=profile.unit_conversion_capabilities,
        quality_warnings=profile.readiness.quality_warnings,
    )


def build_missing_technical_fields_report(
    profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> TechnicalProfileValidationReport:
    if isinstance(profile, MaterialTechnicalProfile):
        return validate_technical_profile(profile)
    group_code = _as_string(profile.get("group_code"))
    characteristics = dict(profile.get("technical_characteristics") or {})
    packaging_profile = profile.get("packaging_profile")
    if not isinstance(packaging_profile, MaterialPackagingProfile):
        packaging_profile = _packaging_profile_from_snapshot(profile)
    capabilities = tuple(profile.get("unit_conversion_capabilities") or ())
    quality_warnings = tuple(profile.get("quality_warnings") or ())
    return _build_validation_report(
        material_id=_as_string(profile.get("material_id")),
        group_code=group_code,
        characteristics=characteristics,
        packaging_profile=packaging_profile,
        capabilities=capabilities,
        quality_warnings=quality_warnings,
    )


def _build_validation_report(
    *,
    material_id: str | None,
    group_code: str | None,
    characteristics: Mapping[str, Any],
    packaging_profile: MaterialPackagingProfile,
    capabilities: tuple[Any, ...],
    quality_warnings: tuple[str, ...],
) -> TechnicalProfileValidationReport:
    required = list_required_technical_fields(group_code)
    module2_required = list_module2_required_fields(group_code)
    packaging_fields = list_packaging_fields(group_code)
    provided = tuple(sorted(characteristics))
    missing_required = tuple(field for field in required if _is_missing(characteristics.get(field)))
    missing_module2 = tuple(field for field in module2_required if _is_missing(characteristics.get(field)))
    missing_packaging = packaging_profile.missing_fields
    conversion_warnings = tuple(
        capability.message
        for capability in capabilities
        if getattr(capability, "supported", False) and getattr(capability, "missing_fields", tuple())
    )
    is_valid = bool(group_code) and not missing_required
    return TechnicalProfileValidationReport(
        material_id=material_id,
        group_code=group_code,
        is_valid=is_valid,
        required_fields=required,
        module2_required_fields=module2_required,
        packaging_fields=packaging_fields,
        provided_fields=provided,
        missing_required_fields=missing_required,
        missing_module2_fields=missing_module2,
        missing_packaging_fields=missing_packaging,
        conversion_warnings=tuple(dict.fromkeys(conversion_warnings)),
        quality_warnings=quality_warnings,
        message="Technical profile validated without writing data.",
    )


def _profile_snapshot(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    return {
        "material_id": canonical_material_view.material_id,
        "group_code": _group_code(canonical_material_view),
        "technical_characteristics": _characteristics_map(canonical_material_view),
        "packaging_profile": build_packaging_profile(canonical_material_view),
        "unit_conversion_capabilities": build_conversion_capabilities(canonical_material_view),
        "quality_warnings": tuple(canonical_material_view.quality.warnings),
    }


def _characteristics_map(canonical_material_view: MaterialCanonicalView) -> Mapping[str, Any]:
    result: dict[str, Any] = {}
    for characteristic in canonical_material_view.characteristics:
        if characteristic.name:
            result[characteristic.name] = _plain_value(characteristic.value)
    return result


def _group_code(canonical_material_view: MaterialCanonicalView) -> str | None:
    group = canonical_material_view.group or {}
    category = canonical_material_view.category or {}
    return _as_string(group.get("code") or group.get("slug") or category.get("slug"))


def _base_unit(canonical_material_view: MaterialCanonicalView) -> str | None:
    base_unit = canonical_material_view.technical_profile_hints.get("baseUnit") or {}
    if isinstance(base_unit, Mapping):
        return _as_string(base_unit.get("abbreviation") or base_unit.get("name"))
    return None


def _conversion_pairs(group_code: str, canonical_material_view: MaterialCanonicalView) -> tuple[tuple[str, str], ...]:
    base_unit = _base_unit(canonical_material_view)
    registry = ExtractionBlueprintRegistry()
    blueprint = registry.get_blueprint(group_code)
    hinted = tuple(blueprint.unit_hints if blueprint else tuple())
    pairs = list(GROUP_CONVERSION_PAIRS.get(group_code, tuple()))
    if base_unit:
        for unit in hinted:
            if unit != base_unit:
                pairs.append((base_unit, unit))
                pairs.append((unit, base_unit))
    return tuple(pairs)


def _missing_conversion_fields(
    alternative_field_sets: tuple[tuple[str, ...], ...],
    characteristics: Mapping[str, Any],
) -> tuple[str, ...]:
    if not alternative_field_sets:
        return tuple()
    for field_set in alternative_field_sets:
        if all(not _is_missing(characteristics.get(field)) for field in field_set):
            return tuple()
    return tuple(field for field in alternative_field_sets[0] if _is_missing(characteristics.get(field)))


def _packaging_profile_from_snapshot(snapshot: Mapping[str, Any]) -> MaterialPackagingProfile:
    group_code = _as_string(snapshot.get("group_code"))
    characteristics = dict(snapshot.get("technical_characteristics") or {})
    fields = {canonical: _first_present(characteristics, aliases) for canonical, aliases in PACKAGING_FIELD_ALIASES.items()}
    fields = {key: value for key, value in fields.items() if value not in (None, "")}
    missing = tuple(field for field in list_packaging_fields(group_code) if _lookup_packaging_value(field, fields, characteristics) in (None, ""))
    return MaterialPackagingProfile(
        material_id=_as_string(snapshot.get("material_id")),
        material_name=_as_string(snapshot.get("material_name")) or "",
        group_code=group_code,
        package_unit=_as_string(fields.get("package_unit")),
        package_weight=fields.get("package_weight_kg"),
        package_volume=fields.get("package_volume_m3") or fields.get("package_volume_l"),
        package_area=fields.get("package_area_m2"),
        pieces_per_package=fields.get("pieces_per_package"),
        pieces_per_pallet=fields.get("pieces_per_pallet"),
        roll_width=fields.get("roll_width_m"),
        roll_length=fields.get("roll_length_m"),
        roll_area=fields.get("roll_area_m2"),
        sheet_length=fields.get("sheet_length_mm"),
        sheet_width=fields.get("sheet_width_mm"),
        sheet_area=fields.get("sheet_area_m2"),
        bag_weight=fields.get("bag_weight_kg"),
        pallet_quantity=fields.get("pallet_quantity"),
        fields=fields,
        missing_fields=missing,
        conversion_hints=_packaging_conversion_hints(group_code),
    )


def _lookup_packaging_value(field: str, fields: Mapping[str, Any], characteristics: Mapping[str, Any]) -> Any:
    if field in characteristics:
        return characteristics[field]
    for canonical, aliases in PACKAGING_FIELD_ALIASES.items():
        if field in aliases or field == canonical:
            return fields.get(canonical)
    return None


def _first_present(characteristics: Mapping[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        if alias in characteristics and characteristics[alias] not in (None, ""):
            return characteristics[alias]
    return None


def _packaging_conversion_hints(group_code: str | None) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    return tuple(f"{from_unit}->{to_unit}" for from_unit, to_unit in GROUP_CONVERSION_PAIRS.get(group_code, tuple()))


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (tuple, list, set, dict)):
        return not value
    return False


def _as_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
