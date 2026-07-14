from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.module1_characteristic_schema_registry import (
    CharacteristicSchemaRegistry,
    GROUP_CODE_ALIASES,
)
from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


KEY_BLUEPRINT_GROUPS = (
    "aerated_concrete_block",
    "gypsum_board_moisture_resistant",
    "rebar",
    "ready_mix_concrete",
    "gypsum_plaster",
    "deep_penetration_primer",
    "porcelain_tile",
    "metal_tile",
    "board",
    "mineral_wool_slab",
)

DEFAULT_DOCUMENT_HINTS = (
    "certificate",
    "declaration",
    "technical_sheet",
)

PACKAGING_FIELDS: Mapping[str, tuple[str, ...]] = {
    "aerated_concrete_block": ("pieces_per_m3", "pieces_per_pallet", "weight_per_piece_kg"),
    "gypsum_board_moisture_resistant": ("sheet_area_m2", "sheets_per_pack", "weight_kg"),
    "rebar": ("standard_bar_length_m", "kg_per_meter"),
    "ready_mix_concrete": ("min_order_m3",),
    "gypsum_plaster": ("bag_weight_kg",),
    "deep_penetration_primer": ("canister_volume_l",),
    "porcelain_tile": ("area_per_box_m2", "tile_length_mm", "tile_width_mm"),
    "metal_tile": ("sheet_length_mm", "effective_width_mm", "full_width_mm"),
    "board": ("volume_per_piece_m3", "length_mm", "width_mm", "thickness_mm"),
    "mineral_wool_slab": ("area_per_pack_m2", "length_mm", "width_mm", "thickness_mm"),
}

QUALITY_FIELDS: Mapping[str, tuple[str, ...]] = {
    "aerated_concrete_block": ("density_class", "strength_class", "frost_resistance", "thermal_conductivity"),
    "gypsum_board_moisture_resistant": ("board_type", "edge_type", "application"),
    "rebar": ("diameter_mm", "steel_class", "certificate"),
    "ready_mix_concrete": ("concrete_class", "mobility_class", "frost_resistance", "water_resistance"),
    "gypsum_plaster": ("wet_room_allowed", "substrates"),
    "deep_penetration_primer": ("primer_type", "compatible_substrates", "drying_time"),
    "porcelain_tile": ("frost_resistant", "rectified", "application"),
    "metal_tile": ("profile_name", "coating", "metal_thickness_mm"),
    "board": ("wood_species", "grade", "moisture_percent"),
    "mineral_wool_slab": ("density_kg_m3", "thermal_conductivity", "fire_class"),
}

DOCUMENT_HINTS: Mapping[str, tuple[str, ...]] = {
    "aerated_concrete_block": DEFAULT_DOCUMENT_HINTS,
    "gypsum_board_moisture_resistant": DEFAULT_DOCUMENT_HINTS,
    "rebar": ("certificate", "declaration", "mill_certificate", "technical_sheet"),
    "ready_mix_concrete": ("passport", "certificate", "declaration", "technical_sheet"),
    "gypsum_plaster": ("certificate", "declaration", "technical_sheet", "safety_sheet"),
    "deep_penetration_primer": ("certificate", "declaration", "technical_sheet", "safety_sheet"),
    "porcelain_tile": ("certificate", "declaration", "technical_sheet"),
    "metal_tile": ("certificate", "declaration", "technical_sheet", "coating_warranty"),
    "board": ("certificate", "declaration", "technical_sheet"),
    "mineral_wool_slab": ("certificate", "declaration", "technical_sheet", "fire_certificate"),
}

UNIT_HINTS: Mapping[str, tuple[str, ...]] = {
    "aerated_concrete_block": ("piece", "m3", "m2", "pallet"),
    "gypsum_board_moisture_resistant": ("sheet", "m2", "package"),
    "rebar": ("linear_meter", "m", "kg", "ton"),
    "ready_mix_concrete": ("m3",),
    "gypsum_plaster": ("kg", "bag", "m2", "m2_mm"),
    "deep_penetration_primer": ("liter", "m2", "package"),
    "porcelain_tile": ("m2", "piece", "package", "pallet"),
    "metal_tile": ("m2", "sheet", "linear_meter"),
    "board": ("piece", "m3", "m", "linear_meter"),
    "mineral_wool_slab": ("package", "m2", "m3", "piece"),
}

FIELD_ALIASES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "aerated_concrete_block": {
        "length_mm": ("length", "длина", "размер_длина", "длина_мм"),
        "width_mm": ("width", "ширина", "ширина_мм"),
        "height_mm": ("height", "высота", "толщина", "высота_мм"),
        "density_class": ("density", "марка_плотности", "плотность"),
        "strength_class": ("strength", "класс_прочности", "прочность"),
        "pieces_per_m3": ("шт_в_м3", "pieces_m3", "количество_в_кубе"),
        "pieces_per_pallet": ("шт_на_поддоне", "pallet_qty", "количество_на_поддоне"),
    },
    "gypsum_board_moisture_resistant": {
        "length_mm": ("length", "длина", "длина_листа"),
        "width_mm": ("width", "ширина", "ширина_листа"),
        "thickness_mm": ("thickness", "толщина", "толщина_листа"),
        "board_type": ("sheet_type", "тип_листа", "тип_гкл"),
        "edge_type": ("edge", "кромка", "тип_кромки"),
        "sheet_area_m2": ("sheet_area", "area", "площадь_листа"),
        "sheets_per_pack": ("sheets_pack", "листов_в_пачке", "листов_в_упаковке"),
    },
    "rebar": {
        "diameter_mm": ("diameter", "диаметр", "диаметр_мм"),
        "steel_class": ("class", "класс", "класс_арматуры", "марка_стали"),
        "kg_per_meter": ("weight_per_meter", "масса_пог_м", "вес_метра"),
        "standard_bar_length_m": ("bar_length", "длина_хлыста", "длина_стержня"),
    },
    "ready_mix_concrete": {
        "concrete_class": ("class", "класс_бетона", "марка_бетона"),
        "mobility_class": ("mobility", "подвижность", "п"),
        "frost_resistance": ("frost", "морозостойкость"),
        "water_resistance": ("waterproof", "водонепроницаемость"),
        "application": ("use", "назначение", "применение"),
        "unit": ("единица", "unit_code", "price_unit"),
    },
    "gypsum_plaster": {
        "consumption_kg_m2_mm": ("consumption", "расход", "расход_кг_м2_мм"),
        "min_layer_mm": ("min_layer", "минимальный_слой"),
        "max_layer_mm": ("max_layer", "максимальный_слой"),
        "bag_weight_kg": ("bag_weight", "вес_мешка", "масса_мешка"),
    },
    "deep_penetration_primer": {
        "consumption_l_m2": ("consumption", "расход", "расход_л_м2"),
        "primer_type": ("type", "тип", "тип_грунтовки"),
        "compatible_substrates": ("substrates", "основания", "совместимые_основания"),
        "canister_volume_l": ("canister_volume", "объем_канистры", "фасовка"),
    },
    "porcelain_tile": {
        "tile_length_mm": ("length", "длина", "длина_плитки"),
        "tile_width_mm": ("width", "ширина", "ширина_плитки"),
        "area_per_box_m2": ("area_per_box", "площадь_коробки", "м2_в_коробке"),
        "thickness_mm": ("thickness", "толщина"),
    },
    "metal_tile": {
        "profile_name": ("profile", "профиль", "название_профиля"),
        "effective_width_mm": ("effective_width", "полезная_ширина", "рабочая_ширина"),
        "full_width_mm": ("full_width", "полная_ширина", "общая_ширина"),
        "sheet_length_mm": ("sheet_length", "длина_листа", "длина"),
        "coating": ("покрытие", "coating_type"),
        "metal_thickness_mm": ("metal_thickness", "толщина_металла"),
        "fastening_pattern_code": ("fastening_pattern", "схема_крепления", "код_крепления"),
    },
    "board": {
        "thickness_mm": ("thickness", "толщина", "толщина_мм"),
        "width_mm": ("width", "ширина", "ширина_мм"),
        "length_mm": ("length", "длина", "длина_мм"),
        "volume_per_piece_m3": ("piece_volume", "объем_штуки", "объем_доски"),
        "wood_species": ("species", "порода", "порода_древесины"),
        "grade": ("сорт", "grade_class"),
    },
    "mineral_wool_slab": {
        "length_mm": ("length", "длина"),
        "width_mm": ("width", "ширина"),
        "thickness_mm": ("thickness", "толщина"),
        "area_per_pack_m2": ("package_area", "площадь_упаковки", "м2_в_упаковке"),
        "density_kg_m3": ("density", "плотность"),
        "thermal_conductivity": ("lambda", "теплопроводность"),
    },
}


@dataclass(frozen=True)
class ExtractionField:
    code: str
    requirement: str


@dataclass(frozen=True)
class ExtractionUnitWarning:
    field: str
    unit: str
    message: str


@dataclass(frozen=True)
class ExtractionBlueprint:
    group_code: str
    required_fields: tuple[str, ...]
    module2_required_fields: tuple[str, ...]
    recommended_fields: tuple[str, ...]
    packaging_fields: tuple[str, ...]
    quality_fields: tuple[str, ...]
    document_hints: tuple[str, ...]
    unit_hints: tuple[str, ...]
    field_aliases: Mapping[str, tuple[str, ...]]
    raw_fields: tuple[str, ...]

    def fields(self) -> tuple[ExtractionField, ...]:
        return tuple(
            ExtractionField(code=field, requirement="required")
            for field in self.required_fields
        ) + tuple(
            ExtractionField(code=field, requirement="module2")
            for field in self.module2_required_fields
            if field not in self.required_fields
        ) + tuple(
            ExtractionField(code=field, requirement="recommended")
            for field in self.recommended_fields
            if field not in self.required_fields and field not in self.module2_required_fields
        )


@dataclass(frozen=True)
class ExtractionValidationReport:
    requested_group_code: str
    resolved_group_code: str | None
    blueprint_found: bool
    provided_fields: tuple[str, ...]
    normalized_fields: tuple[str, ...]
    missing_required: tuple[str, ...]
    missing_module2_required: tuple[str, ...]
    missing_packaging: tuple[str, ...]
    unit_warnings: tuple[ExtractionUnitWarning, ...]
    message: str

    @property
    def is_valid(self) -> bool:
        return self.blueprint_found and not self.missing_required and not self.unit_warnings


class ExtractionBlueprintRegistry:
    def __init__(
        self,
        seed_registry: MaterialKnowledgeSeedRegistry | None = None,
        schema_registry: CharacteristicSchemaRegistry | None = None,
        unit_registry: UnitConversionRegistry | None = None,
    ) -> None:
        self._seed_registry = seed_registry or get_material_knowledge_seed_registry()
        self._schema_registry = schema_registry or CharacteristicSchemaRegistry(self._seed_registry)
        self._unit_registry = unit_registry or UnitConversionRegistry(self._seed_registry)

    def get_blueprint(self, group_code: str) -> ExtractionBlueprint | None:
        resolved_group_code = self.resolve_group_code(group_code)
        schema = self._schema_registry.get_schema(resolved_group_code)
        if schema is None or resolved_group_code not in KEY_BLUEPRINT_GROUPS:
            return None

        required = tuple(field.code for field in schema.required)
        module2_required = tuple(field.code for field in schema.module2_required)
        recommended = tuple(field.code for field in schema.recommended)
        packaging = _known_fields(PACKAGING_FIELDS.get(resolved_group_code, tuple()), required, module2_required, recommended)
        quality = _known_fields(QUALITY_FIELDS.get(resolved_group_code, tuple()), required, module2_required, recommended)
        aliases = FIELD_ALIASES.get(resolved_group_code, {})
        raw_fields = tuple(
            dict.fromkeys(
                required
                + module2_required
                + recommended
                + packaging
                + quality
                + tuple(aliases.keys())
                + ("title", "name", "brand", "manufacturer", "price", "currency", "unit")
            )
        )
        return ExtractionBlueprint(
            group_code=resolved_group_code,
            required_fields=required,
            module2_required_fields=module2_required,
            recommended_fields=recommended,
            packaging_fields=packaging,
            quality_fields=quality,
            document_hints=DOCUMENT_HINTS.get(resolved_group_code, DEFAULT_DOCUMENT_HINTS),
            unit_hints=UNIT_HINTS.get(resolved_group_code, tuple()),
            field_aliases=aliases,
            raw_fields=raw_fields,
        )

    def has_blueprint(self, group_code: str) -> bool:
        return self.get_blueprint(group_code) is not None

    def list_blueprints(self) -> tuple[str, ...]:
        return tuple(group for group in KEY_BLUEPRINT_GROUPS if self.has_blueprint(group))

    def get_required_extraction_fields(self, group_code: str) -> tuple[str, ...]:
        blueprint = self.get_blueprint(group_code)
        return blueprint.required_fields if blueprint else tuple()

    def get_module2_extraction_fields(self, group_code: str) -> tuple[str, ...]:
        blueprint = self.get_blueprint(group_code)
        return blueprint.module2_required_fields if blueprint else tuple()

    def get_packaging_fields(self, group_code: str) -> tuple[str, ...]:
        blueprint = self.get_blueprint(group_code)
        return blueprint.packaging_fields if blueprint else tuple()

    def get_document_hints(self, group_code: str) -> tuple[str, ...]:
        blueprint = self.get_blueprint(group_code)
        return blueprint.document_hints if blueprint else tuple()

    def get_field_aliases(self, group_code: str) -> Mapping[str, tuple[str, ...]]:
        blueprint = self.get_blueprint(group_code)
        return blueprint.field_aliases if blueprint else {}

    def validate_extracted_payload(
        self,
        group_code: str,
        raw_payload: Mapping[str, Any] | None,
    ) -> ExtractionValidationReport:
        return self.build_extraction_missing_fields_report(group_code, raw_payload)

    def build_extraction_missing_fields_report(
        self,
        group_code: str,
        raw_payload: Mapping[str, Any] | None,
    ) -> ExtractionValidationReport:
        payload = dict(raw_payload or {})
        provided_fields = tuple(sorted(str(key) for key in payload.keys()))
        blueprint = self.get_blueprint(group_code)
        resolved_group_code = self.resolve_group_code(group_code)
        if blueprint is None:
            return ExtractionValidationReport(
                requested_group_code=group_code,
                resolved_group_code=None,
                blueprint_found=False,
                provided_fields=provided_fields,
                normalized_fields=tuple(),
                missing_required=tuple(),
                missing_module2_required=tuple(),
                missing_packaging=tuple(),
                unit_warnings=tuple(),
                message="Extraction blueprint is not defined for this material group.",
            )

        normalized_fields = _normalize_payload_fields(payload, blueprint.field_aliases)
        missing_required = _missing_fields(blueprint.required_fields, normalized_fields)
        missing_module2 = _missing_fields(blueprint.module2_required_fields, normalized_fields)
        missing_packaging = _missing_fields(blueprint.packaging_fields, normalized_fields)
        unit_warnings = self._unit_warnings(payload)
        return ExtractionValidationReport(
            requested_group_code=group_code,
            resolved_group_code=resolved_group_code,
            blueprint_found=True,
            provided_fields=provided_fields,
            normalized_fields=tuple(sorted(normalized_fields)),
            missing_required=missing_required,
            missing_module2_required=missing_module2,
            missing_packaging=missing_packaging,
            unit_warnings=unit_warnings,
            message="Extraction payload validated against Module 1 blueprint.",
        )

    def resolve_group_code(self, group_code: str) -> str:
        return GROUP_CODE_ALIASES.get(group_code, group_code)

    def _unit_warnings(self, payload: Mapping[str, Any]) -> tuple[ExtractionUnitWarning, ...]:
        warnings: list[ExtractionUnitWarning] = []
        for field, value in payload.items():
            if isinstance(value, Mapping) and "unit" in value:
                unit = str(value.get("unit") or "")
                if unit and self._unit_registry.normalize_unit(unit) is None:
                    warnings.append(
                        ExtractionUnitWarning(
                            field=str(field),
                            unit=unit,
                            message="Unit is not recognized by Module 1 unit dictionary.",
                        )
                    )
            if str(field).endswith("_unit") or str(field) in {"unit", "price_unit", "measurement_unit"}:
                unit = str(value or "")
                if unit and self._unit_registry.normalize_unit(unit) is None:
                    warnings.append(
                        ExtractionUnitWarning(
                            field=str(field),
                            unit=unit,
                            message="Unit is not recognized by Module 1 unit dictionary.",
                        )
                    )
        return tuple(warnings)


def get_extraction_blueprint_registry() -> ExtractionBlueprintRegistry:
    return ExtractionBlueprintRegistry()


def get_blueprint(group_code: str) -> ExtractionBlueprint | None:
    return get_extraction_blueprint_registry().get_blueprint(group_code)


def has_blueprint(group_code: str) -> bool:
    return get_extraction_blueprint_registry().has_blueprint(group_code)


def list_blueprints() -> tuple[str, ...]:
    return get_extraction_blueprint_registry().list_blueprints()


def get_required_extraction_fields(group_code: str) -> tuple[str, ...]:
    return get_extraction_blueprint_registry().get_required_extraction_fields(group_code)


def get_module2_extraction_fields(group_code: str) -> tuple[str, ...]:
    return get_extraction_blueprint_registry().get_module2_extraction_fields(group_code)


def get_packaging_fields(group_code: str) -> tuple[str, ...]:
    return get_extraction_blueprint_registry().get_packaging_fields(group_code)


def get_document_hints(group_code: str) -> tuple[str, ...]:
    return get_extraction_blueprint_registry().get_document_hints(group_code)


def get_field_aliases(group_code: str) -> Mapping[str, tuple[str, ...]]:
    return get_extraction_blueprint_registry().get_field_aliases(group_code)


def validate_extracted_payload(
    group_code: str,
    raw_payload: Mapping[str, Any] | None,
) -> ExtractionValidationReport:
    return get_extraction_blueprint_registry().validate_extracted_payload(group_code, raw_payload)


def build_extraction_missing_fields_report(
    group_code: str,
    raw_payload: Mapping[str, Any] | None,
) -> ExtractionValidationReport:
    return get_extraction_blueprint_registry().build_extraction_missing_fields_report(group_code, raw_payload)


def _known_fields(
    fields: tuple[str, ...],
    required: tuple[str, ...],
    module2_required: tuple[str, ...],
    recommended: tuple[str, ...],
) -> tuple[str, ...]:
    known = set(required) | set(module2_required) | set(recommended)
    return tuple(field for field in fields if field in known)


def _normalize_payload_fields(payload: Mapping[str, Any], aliases: Mapping[str, tuple[str, ...]]) -> frozenset[str]:
    normalized: set[str] = set()
    alias_index = {
        alias: canonical
        for canonical, field_aliases in aliases.items()
        for alias in field_aliases
    }
    for key, value in payload.items():
        if value in (None, ""):
            continue
        field = str(key)
        normalized.add(alias_index.get(field, field))
    return frozenset(normalized)


def _missing_fields(required_fields: tuple[str, ...], normalized_fields: frozenset[str]) -> tuple[str, ...]:
    return tuple(field for field in required_fields if field not in normalized_fields)
