from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app.services.module1_characteristic_schema_registry import GROUP_CODE_ALIASES
from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    UnitConversionRuleSeed,
    get_material_knowledge_seed_registry,
)


UnitProfile = Mapping[str, Any] | None


@dataclass(frozen=True)
class UnitConversionRuleView:
    from_unit: str
    to_unit: str
    material_group: str | None = None
    factor: Decimal | None = None
    formula: str | None = None
    fallback: str | None = None
    source: str = "builtin"
    requires_material_profile: bool = False


@dataclass(frozen=True)
class UnitConversionRequirementsReport:
    requested_from_unit: str
    requested_to_unit: str
    canonical_from_unit: str | None
    canonical_to_unit: str | None
    material_group: str | None
    supported: bool
    requires_material_profile: bool
    required_fields: tuple[str, ...]
    alternative_field_sets: tuple[tuple[str, ...], ...] = ()
    formula: str | None = None
    fallback: str | None = None
    message: str = ""


@dataclass(frozen=True)
class UnitConversionResult:
    success: bool
    value: Decimal | None = None
    unit: str | None = None
    requested_from_unit: str | None = None
    requested_to_unit: str | None = None
    canonical_from_unit: str | None = None
    canonical_to_unit: str | None = None
    material_group: str | None = None
    missing_fields: tuple[str, ...] = ()
    alternative_field_sets: tuple[tuple[str, ...], ...] = ()
    message: str = ""
    error_code: str | None = None


UNIT_ALIASES: Mapping[str, tuple[str, ...]] = {
    "mm": ("mm", "мм", "миллиметр", "миллиметры"),
    "cm": ("cm", "см", "сантиметр", "сантиметры"),
    "m": ("m", "м", "метр", "метры"),
    "linear_meter": (
        "linear_meter",
        "running_meter",
        "lm",
        "l.m.",
        "м.п.",
        "пог.м",
        "пог. м",
        "погонный метр",
    ),
    "m2": ("m2", "m^2", "sqm", "м2", "м²", "кв.м", "кв. м"),
    "m2_mm": ("m2_mm", "m2*mm", "м2*мм", "м²*мм"),
    "m3": ("m3", "m^3", "cbm", "м3", "м³", "куб.м", "куб. м"),
    "kg": ("kg", "кг", "килограмм", "килограммы"),
    "ton": ("ton", "t", "т", "тонна", "тонны"),
    "liter": ("liter", "l", "л", "литр", "литры"),
    "piece": ("piece", "pieces", "pc", "pcs", "шт", "штука", "штуки"),
    "sheet": ("sheet", "sheets", "лист", "листы"),
    "bag": ("bag", "bags", "мешок", "мешки"),
    "package": ("package", "pack", "упаковка", "упак", "упаковки"),
    "roll": ("roll", "rolls", "рулон", "рулоны"),
    "pallet": ("pallet", "pallets", "поддон", "паллет", "паллеты"),
}

UNIT_ALIAS_INDEX: Mapping[str, str] = {
    alias: canonical
    for canonical, aliases in UNIT_ALIASES.items()
    for alias in aliases
}

SIMPLE_CONVERSION_FACTORS: Mapping[tuple[str, str], Decimal] = {
    ("mm", "cm"): Decimal("0.1"),
    ("cm", "mm"): Decimal("10"),
    ("mm", "m"): Decimal("0.001"),
    ("m", "mm"): Decimal("1000"),
    ("cm", "m"): Decimal("0.01"),
    ("m", "cm"): Decimal("100"),
    ("m", "linear_meter"): Decimal("1"),
    ("linear_meter", "m"): Decimal("1"),
    ("kg", "ton"): Decimal("0.001"),
    ("ton", "kg"): Decimal("1000"),
    ("liter", "m3"): Decimal("0.001"),
    ("m3", "liter"): Decimal("1000"),
}

TECHNICAL_REQUIREMENT_SETS: Mapping[tuple[str, str, str], tuple[tuple[str, ...], ...]] = {
    ("rebar", "m", "kg"): (("kg_per_meter",), ("diameter_mm",)),
    ("rebar", "linear_meter", "kg"): (("kg_per_meter",), ("diameter_mm",)),
    ("rebar", "kg", "m"): (("kg_per_meter",), ("diameter_mm",)),
    ("rebar", "kg", "linear_meter"): (("kg_per_meter",), ("diameter_mm",)),
    ("board", "piece", "m3"): (("length_m", "width_m", "thickness_m"), ("length_mm", "width_mm", "thickness_mm")),
    ("board", "m3", "piece"): (("length_m", "width_m", "thickness_m"), ("length_mm", "width_mm", "thickness_mm")),
    ("aerated_concrete_block", "piece", "m3"): (
        ("length_m", "width_m", "height_m"),
        ("length_mm", "width_mm", "height_mm"),
    ),
    ("aerated_concrete_block", "m3", "piece"): (
        ("length_m", "width_m", "height_m"),
        ("length_mm", "width_mm", "height_mm"),
    ),
    ("gypsum_board", "sheet", "m2"): (("sheet_area_m2",), ("length_m", "width_m"), ("length_mm", "width_mm")),
    ("gypsum_board", "m2", "sheet"): (("sheet_area_m2",), ("length_m", "width_m"), ("length_mm", "width_mm")),
    ("gypsum_board_moisture_resistant", "sheet", "m2"): (
        ("sheet_area_m2",),
        ("length_m", "width_m"),
        ("length_mm", "width_mm"),
    ),
    ("gypsum_board_moisture_resistant", "m2", "sheet"): (
        ("sheet_area_m2",),
        ("length_m", "width_m"),
        ("length_mm", "width_mm"),
    ),
    ("mineral_wool_slab", "package", "m2"): (("package_area_m2",),),
    ("mineral_wool_slab", "m2", "package"): (("package_area_m2",),),
    ("mineral_wool_slab", "package", "m3"): (
        ("package_volume_m3",),
        ("package_area_m2", "thickness_mm"),
    ),
    ("mineral_wool_slab", "m3", "package"): (
        ("package_volume_m3",),
        ("package_area_m2", "thickness_mm"),
    ),
    ("membrane", "roll", "m2"): (("roll_area_m2",), ("roll_width_m", "roll_length_m")),
    ("membrane", "m2", "roll"): (("roll_area_m2",), ("roll_width_m", "roll_length_m")),
    ("paint", "m2", "liter"): (("coverage_m2_per_l",),),
    ("paint", "liter", "m2"): (("coverage_m2_per_l",),),
    ("deep_penetration_primer", "m2", "liter"): (("coverage_m2_per_l",), ("consumption_l_m2",)),
    ("deep_penetration_primer", "liter", "m2"): (("coverage_m2_per_l",), ("consumption_l_m2",)),
    ("dry_mix", "m2", "kg"): (("consumption_kg_m2_mm", "layer_thickness_mm"),),
    ("dry_mix", "kg", "m2"): (("consumption_kg_m2_mm", "layer_thickness_mm"),),
    ("dry_mix", "m2_mm", "kg"): (("consumption_kg_m2_mm",),),
    ("dry_mix", "kg", "m2_mm"): (("consumption_kg_m2_mm",),),
    ("gypsum_plaster", "m2", "kg"): (("consumption_kg_m2_mm", "layer_thickness_mm"),),
    ("gypsum_plaster", "kg", "m2"): (("consumption_kg_m2_mm", "layer_thickness_mm"),),
}


class UnitConversionRegistry:
    def __init__(self, seed_registry: MaterialKnowledgeSeedRegistry | None = None) -> None:
        self._seed_registry = seed_registry or get_material_knowledge_seed_registry()
        self._conversion_groups = frozenset(rule.material_group for rule in self._seed_registry.unit_conversions)

    def normalize_unit(self, unit: str | None) -> str | None:
        if unit is None:
            return None
        cleaned = str(unit).strip().lower().replace("²", "2").replace("³", "3")
        cleaned = cleaned.replace("кв. м", "кв.м").replace("куб. м", "куб.м")
        return UNIT_ALIAS_INDEX.get(cleaned)

    def list_units(self) -> tuple[str, ...]:
        return tuple(sorted(UNIT_ALIASES.keys()))

    def get_unit_aliases(self) -> Mapping[str, tuple[str, ...]]:
        return UNIT_ALIASES

    def get_conversion_rule(
        self,
        from_unit: str,
        to_unit: str,
        material_group: str | None = None,
    ) -> UnitConversionRuleView | None:
        canonical_from = self.normalize_unit(from_unit)
        canonical_to = self.normalize_unit(to_unit)
        if canonical_from is None or canonical_to is None:
            return None
        if canonical_from == canonical_to:
            return UnitConversionRuleView(
                from_unit=canonical_from,
                to_unit=canonical_to,
                factor=Decimal("1"),
                source="identity",
            )
        factor = SIMPLE_CONVERSION_FACTORS.get((canonical_from, canonical_to))
        if factor is not None:
            return UnitConversionRuleView(
                from_unit=canonical_from,
                to_unit=canonical_to,
                factor=factor,
                source="builtin",
            )

        resolved_group = self.resolve_material_group(material_group) if material_group else None
        if resolved_group is None:
            return None

        seed_rule = self._find_seed_rule(resolved_group, canonical_from, canonical_to)
        if seed_rule is not None:
            return UnitConversionRuleView(
                from_unit=canonical_from,
                to_unit=canonical_to,
                material_group=resolved_group,
                formula=seed_rule.formula,
                fallback=seed_rule.fallback,
                source="seed",
                requires_material_profile=True,
            )

        requirement_sets = self._requirement_sets(resolved_group, canonical_from, canonical_to)
        if requirement_sets:
            return UnitConversionRuleView(
                from_unit=canonical_from,
                to_unit=canonical_to,
                material_group=resolved_group,
                source="technical-requirements",
                requires_material_profile=True,
            )
        return None

    def can_convert(
        self,
        from_unit: str,
        to_unit: str,
        material_profile: UnitProfile = None,
        material_group: str | None = None,
    ) -> bool:
        report = self.convert_quantity(
            1,
            from_unit,
            to_unit,
            material_profile=material_profile,
            material_group=material_group,
        )
        return report.success

    def convert_quantity(
        self,
        value: Decimal | int | float | str,
        from_unit: str,
        to_unit: str,
        material_profile: UnitProfile = None,
        material_group: str | None = None,
    ) -> UnitConversionResult:
        canonical_from = self.normalize_unit(from_unit)
        canonical_to = self.normalize_unit(to_unit)
        value_decimal = _to_decimal(value)
        if value_decimal is None:
            return UnitConversionResult(
                success=False,
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                message="Quantity must be a number.",
                error_code="INVALID_QUANTITY",
            )
        if canonical_from is None or canonical_to is None:
            return UnitConversionResult(
                success=False,
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                message="Unit is not supported by Module 1 unit dictionary.",
                error_code="UNKNOWN_UNIT",
            )
        if canonical_from == canonical_to:
            return _success_result(value_decimal, canonical_to, from_unit, to_unit, canonical_from, canonical_to, material_group)

        factor = SIMPLE_CONVERSION_FACTORS.get((canonical_from, canonical_to))
        if factor is not None:
            return _success_result(value_decimal * factor, canonical_to, from_unit, to_unit, canonical_from, canonical_to, material_group)

        requirements = self.build_conversion_requirements(from_unit, to_unit, material_group)
        if not requirements.supported:
            return UnitConversionResult(
                success=False,
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=requirements.material_group,
                message=requirements.message,
                error_code="UNSUPPORTED_CONVERSION",
            )

        missing = self._missing_fields(requirements.alternative_field_sets, material_profile)
        if missing:
            return UnitConversionResult(
                success=False,
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=requirements.material_group,
                missing_fields=missing,
                alternative_field_sets=requirements.alternative_field_sets,
                message="Conversion requires material technical profile fields.",
                error_code="MISSING_MATERIAL_PROFILE_FIELDS",
            )

        calculated = self._calculate_technical_conversion(
            value_decimal,
            canonical_from,
            canonical_to,
            requirements.material_group,
            material_profile or {},
        )
        if calculated is None:
            return UnitConversionResult(
                success=False,
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=requirements.material_group,
                alternative_field_sets=requirements.alternative_field_sets,
                message="Conversion is known, but Module 1 only reports required fields for this pair.",
                error_code="TECHNICAL_FORMULA_NOT_EXECUTED",
            )
        return _success_result(
            calculated,
            canonical_to,
            from_unit,
            to_unit,
            canonical_from,
            canonical_to,
            requirements.material_group,
        )

    def build_conversion_requirements(
        self,
        from_unit: str,
        to_unit: str,
        material_group: str | None = None,
    ) -> UnitConversionRequirementsReport:
        canonical_from = self.normalize_unit(from_unit)
        canonical_to = self.normalize_unit(to_unit)
        resolved_group = self.resolve_material_group(material_group) if material_group else None
        if canonical_from is None or canonical_to is None:
            return UnitConversionRequirementsReport(
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=resolved_group,
                supported=False,
                requires_material_profile=False,
                required_fields=tuple(),
                message="Unit is not supported by Module 1 unit dictionary.",
            )
        if canonical_from == canonical_to or (canonical_from, canonical_to) in SIMPLE_CONVERSION_FACTORS:
            return UnitConversionRequirementsReport(
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=resolved_group,
                supported=True,
                requires_material_profile=False,
                required_fields=tuple(),
                message="Direct conversion does not require material profile.",
            )
        if resolved_group is None:
            return UnitConversionRequirementsReport(
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=None,
                supported=False,
                requires_material_profile=False,
                required_fields=tuple(),
                message="Material group is required for technical unit conversion.",
            )

        seed_rule = self._find_seed_rule(resolved_group, canonical_from, canonical_to)
        requirement_sets = self._requirement_sets(resolved_group, canonical_from, canonical_to)
        if not requirement_sets and seed_rule is None:
            return UnitConversionRequirementsReport(
                requested_from_unit=from_unit,
                requested_to_unit=to_unit,
                canonical_from_unit=canonical_from,
                canonical_to_unit=canonical_to,
                material_group=resolved_group,
                supported=False,
                requires_material_profile=False,
                required_fields=tuple(),
                message="Conversion rule is not known for this material group.",
            )

        requirement_sets = requirement_sets or _requirements_from_seed_formula(seed_rule)
        required_fields = requirement_sets[0] if requirement_sets else tuple()
        return UnitConversionRequirementsReport(
            requested_from_unit=from_unit,
            requested_to_unit=to_unit,
            canonical_from_unit=canonical_from,
            canonical_to_unit=canonical_to,
            material_group=resolved_group,
            supported=True,
            requires_material_profile=True,
            required_fields=required_fields,
            alternative_field_sets=requirement_sets,
            formula=seed_rule.formula if seed_rule else None,
            fallback=seed_rule.fallback if seed_rule else None,
            message="Conversion requires material technical profile fields.",
        )

    def resolve_material_group(self, material_group: str | None) -> str | None:
        if material_group is None:
            return None
        cleaned = str(material_group).strip()
        if not cleaned:
            return None
        if cleaned in self._conversion_groups:
            return cleaned
        aliased = GROUP_CODE_ALIASES.get(cleaned, cleaned)
        if aliased in self._conversion_groups or self._seed_registry.has_material_group(aliased):
            return aliased
        return cleaned

    def _find_seed_rule(
        self,
        material_group: str,
        from_unit: str,
        to_unit: str,
    ) -> UnitConversionRuleSeed | None:
        for rule in self._seed_registry.unit_conversions_for_group(material_group):
            rule_from = self.normalize_unit(rule.from_unit)
            rule_to = self.normalize_unit(rule.to_unit)
            if _units_match(from_unit, rule_from) and _units_match(to_unit, rule_to):
                return rule
            if _units_match(from_unit, rule_to) and _units_match(to_unit, rule_from):
                return rule
        return None

    def _requirement_sets(
        self,
        material_group: str,
        from_unit: str,
        to_unit: str,
    ) -> tuple[tuple[str, ...], ...]:
        direct = TECHNICAL_REQUIREMENT_SETS.get((material_group, from_unit, to_unit))
        if direct:
            return direct
        if from_unit == "linear_meter":
            direct = TECHNICAL_REQUIREMENT_SETS.get((material_group, "m", to_unit))
            if direct:
                return direct
        if to_unit == "linear_meter":
            direct = TECHNICAL_REQUIREMENT_SETS.get((material_group, from_unit, "m"))
            if direct:
                return direct
        return tuple()

    def _missing_fields(
        self,
        alternative_field_sets: tuple[tuple[str, ...], ...],
        material_profile: UnitProfile,
    ) -> tuple[str, ...]:
        if not alternative_field_sets:
            return tuple()
        profile = material_profile or {}
        for field_set in alternative_field_sets:
            if all(_profile_has_value(profile, field) for field in field_set):
                return tuple()
        return alternative_field_sets[0]

    def _calculate_technical_conversion(
        self,
        value: Decimal,
        from_unit: str,
        to_unit: str,
        material_group: str | None,
        profile: Mapping[str, Any],
    ) -> Decimal | None:
        if material_group == "rebar" and {from_unit, to_unit} <= {"m", "linear_meter", "kg"}:
            kg_per_meter = _decimal_from_profile(profile, "kg_per_meter")
            if kg_per_meter is None:
                diameter_mm = _decimal_from_profile(profile, "diameter_mm")
                kg_per_meter = (diameter_mm * diameter_mm / Decimal("162")) if diameter_mm is not None else None
            if kg_per_meter is None or kg_per_meter == 0:
                return None
            return value * kg_per_meter if to_unit == "kg" else value / kg_per_meter

        if material_group in {"board", "aerated_concrete_block"} and {from_unit, to_unit} <= {"piece", "m3"}:
            dimensions = ("length", "width", "thickness") if material_group == "board" else ("length", "width", "height")
            volume = _volume_per_piece_m3(profile, dimensions)
            if volume is None or volume == 0:
                return None
            return value * volume if to_unit == "m3" else value / volume

        if material_group in {"gypsum_board", "gypsum_board_moisture_resistant"} and {from_unit, to_unit} <= {"sheet", "m2"}:
            area = _decimal_from_profile(profile, "sheet_area_m2") or _area_m2(profile, "length", "width")
            if area is None or area == 0:
                return None
            return value * area if to_unit == "m2" else value / area

        if material_group == "membrane" and {from_unit, to_unit} <= {"roll", "m2"}:
            area = _decimal_from_profile(profile, "roll_area_m2")
            if area is None:
                width = _dimension_m(profile, "roll_width")
                length = _dimension_m(profile, "roll_length")
                area = width * length if width is not None and length is not None else None
            if area is None or area == 0:
                return None
            return value * area if to_unit == "m2" else value / area

        if material_group in {"paint", "deep_penetration_primer"} and {from_unit, to_unit} <= {"m2", "liter"}:
            coverage = _decimal_from_profile(profile, "coverage_m2_per_l")
            coats = _decimal_from_profile(profile, "coats") or Decimal("1")
            if coverage is not None and coverage != 0:
                return value * coats / coverage if to_unit == "liter" else value * coverage / coats
            consumption = _decimal_from_profile(profile, "consumption_l_m2")
            if consumption is not None and consumption != 0:
                return value * consumption * coats if to_unit == "liter" else value / (consumption * coats)
            return None

        if material_group in {"dry_mix", "gypsum_plaster"} and {from_unit, to_unit} <= {"m2", "m2_mm", "kg"}:
            consumption = _decimal_from_profile(profile, "consumption_kg_m2_mm")
            if consumption is None or consumption == 0:
                return None
            if from_unit == "m2_mm" or to_unit == "m2_mm":
                return value * consumption if to_unit == "kg" else value / consumption
            thickness = _decimal_from_profile(profile, "layer_thickness_mm")
            if thickness is None or thickness == 0:
                return None
            return value * consumption * thickness if to_unit == "kg" else value / (consumption * thickness)

        if material_group == "mineral_wool_slab" and {from_unit, to_unit} <= {"package", "m2", "m3"}:
            if to_unit == "m2" or from_unit == "m2":
                area = _decimal_from_profile(profile, "package_area_m2")
                if area is None or area == 0:
                    return None
                return value * area if to_unit == "m2" else value / area
            volume = _decimal_from_profile(profile, "package_volume_m3")
            if volume is None:
                area = _decimal_from_profile(profile, "package_area_m2")
                thickness = _dimension_m(profile, "thickness")
                volume = area * thickness if area is not None and thickness is not None else None
            if volume is None or volume == 0:
                return None
            return value * volume if to_unit == "m3" else value / volume

        return None


def get_unit_conversion_registry() -> UnitConversionRegistry:
    return UnitConversionRegistry()


def normalize_unit(unit: str | None) -> str | None:
    return get_unit_conversion_registry().normalize_unit(unit)


def list_units() -> tuple[str, ...]:
    return get_unit_conversion_registry().list_units()


def get_unit_aliases() -> Mapping[str, tuple[str, ...]]:
    return get_unit_conversion_registry().get_unit_aliases()


def get_conversion_rule(
    from_unit: str,
    to_unit: str,
    material_group: str | None = None,
) -> UnitConversionRuleView | None:
    return get_unit_conversion_registry().get_conversion_rule(from_unit, to_unit, material_group)


def can_convert(
    from_unit: str,
    to_unit: str,
    material_profile: UnitProfile = None,
    material_group: str | None = None,
) -> bool:
    return get_unit_conversion_registry().can_convert(from_unit, to_unit, material_profile, material_group)


def convert_quantity(
    value: Decimal | int | float | str,
    from_unit: str,
    to_unit: str,
    material_profile: UnitProfile = None,
    material_group: str | None = None,
) -> UnitConversionResult:
    return get_unit_conversion_registry().convert_quantity(value, from_unit, to_unit, material_profile, material_group)


def build_conversion_requirements(
    from_unit: str,
    to_unit: str,
    material_group: str | None = None,
) -> UnitConversionRequirementsReport:
    return get_unit_conversion_registry().build_conversion_requirements(from_unit, to_unit, material_group)


def _success_result(
    value: Decimal,
    unit: str,
    requested_from_unit: str,
    requested_to_unit: str,
    canonical_from_unit: str,
    canonical_to_unit: str,
    material_group: str | None,
) -> UnitConversionResult:
    return UnitConversionResult(
        success=True,
        value=value,
        unit=unit,
        requested_from_unit=requested_from_unit,
        requested_to_unit=requested_to_unit,
        canonical_from_unit=canonical_from_unit,
        canonical_to_unit=canonical_to_unit,
        material_group=material_group,
        message="Conversion completed.",
    )


def _units_match(requested: str, rule_unit: str | None) -> bool:
    if rule_unit is None:
        return False
    if requested == rule_unit:
        return True
    return requested in {"m", "linear_meter"} and rule_unit in {"m", "linear_meter"}


def _requirements_from_seed_formula(rule: UnitConversionRuleSeed | None) -> tuple[tuple[str, ...], ...]:
    if rule is None:
        return tuple()
    tokens = (
        rule.formula.replace("*", " ")
        .replace("/", " ")
        .replace("+", " ")
        .replace("-", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("^", " ")
        .split()
    )
    ignored = {"length_m", "area_m2", "pieces", "sheets", "rolls", "coats"}
    fields = tuple(token for token in tokens if token.isidentifier() and token not in ignored)
    if rule.fallback:
        fallback_tokens = rule.fallback.replace("^", " ").replace("/", " ").split()
        fallback_fields = tuple(token for token in fallback_tokens if token.isidentifier())
        if fallback_fields:
            return (fields, fallback_fields) if fields else (fallback_fields,)
    return (fields,) if fields else tuple()


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _profile_has_value(profile: Mapping[str, Any], field: str) -> bool:
    return _decimal_from_profile(profile, field) is not None or _raw_profile_value(profile, field) not in (None, "")


def _raw_profile_value(profile: Mapping[str, Any], field: str) -> Any:
    if field in profile:
        return profile[field]
    return None


def _decimal_from_profile(profile: Mapping[str, Any], field: str) -> Decimal | None:
    value = _raw_profile_value(profile, field)
    if isinstance(value, Mapping):
        value = value.get("value")
    return _to_decimal(value)


def _dimension_m(profile: Mapping[str, Any], name: str) -> Decimal | None:
    meter_value = _decimal_from_profile(profile, f"{name}_m")
    if meter_value is not None:
        return meter_value
    millimeter_value = _decimal_from_profile(profile, f"{name}_mm")
    if millimeter_value is not None:
        return millimeter_value / Decimal("1000")
    raw_value = _raw_profile_value(profile, name)
    if isinstance(raw_value, Mapping):
        amount = _to_decimal(raw_value.get("value"))
        unit = str(raw_value.get("unit") or "mm")
        canonical_unit = UnitConversionRegistry().normalize_unit(unit)
        if amount is None:
            return None
        if canonical_unit == "m":
            return amount
        if canonical_unit == "cm":
            return amount / Decimal("100")
        if canonical_unit == "mm":
            return amount / Decimal("1000")
    raw_decimal = _to_decimal(raw_value)
    return raw_decimal / Decimal("1000") if raw_decimal is not None else None


def _area_m2(profile: Mapping[str, Any], length_name: str, width_name: str) -> Decimal | None:
    length = _dimension_m(profile, length_name)
    width = _dimension_m(profile, width_name)
    return length * width if length is not None and width is not None else None


def _volume_per_piece_m3(profile: Mapping[str, Any], dimension_names: tuple[str, str, str]) -> Decimal | None:
    values = tuple(_dimension_m(profile, name) for name in dimension_names)
    if any(value is None for value in values):
        return None
    length, width, height = values
    return length * width * height  # type: ignore[operator]
