from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_unit_conversion_registry import (
    UnitConversionRegistry,
    build_conversion_requirements,
    can_convert,
    convert_quantity,
    get_conversion_rule,
    get_unit_aliases,
    list_units,
    normalize_unit,
)


def test_normalize_unit_supports_required_aliases() -> None:
    assert normalize_unit("мм") == "mm"
    assert normalize_unit("mm") == "mm"
    assert normalize_unit("см") == "cm"
    assert normalize_unit("м") == "m"
    assert normalize_unit("м.п.") == "linear_meter"
    assert normalize_unit("пог.м") == "linear_meter"
    assert normalize_unit("м²") == "m2"
    assert normalize_unit("m2") == "m2"
    assert normalize_unit("м³") == "m3"
    assert normalize_unit("kg") == "kg"
    assert normalize_unit("кг") == "kg"
    assert normalize_unit("т") == "ton"
    assert normalize_unit("л") == "liter"
    assert normalize_unit("шт") == "piece"
    assert normalize_unit("мешок") == "bag"
    assert normalize_unit("упаковка") == "package"
    assert normalize_unit("рулон") == "roll"
    assert normalize_unit("поддон") == "pallet"


def test_list_units_and_aliases_include_seed_units() -> None:
    units = list_units()
    aliases = get_unit_aliases()

    assert "m2_mm" in units
    assert "sheet" in units
    assert "m2*mm" in aliases["m2_mm"]
    assert "лист" in aliases["sheet"]


def test_registry_reads_unit_conversions_from_seed_registry() -> None:
    registry = UnitConversionRegistry()

    rebar_rule = registry.get_conversion_rule("м.п.", "кг", material_group="rebar")
    paint_rule = registry.get_conversion_rule("m2", "l", material_group="paint")

    assert rebar_rule is not None
    assert rebar_rule.source == "seed"
    assert rebar_rule.material_group == "rebar"
    assert rebar_rule.formula == "length_m * kg_per_meter"
    assert rebar_rule.requires_material_profile is True

    assert paint_rule is not None
    assert paint_rule.source == "seed"
    assert paint_rule.formula == "area_m2 * coats / coverage_m2_per_l"


def test_simple_direct_conversions_do_not_require_material_profile() -> None:
    assert convert_quantity(1000, "мм", "м").value == Decimal("1")
    assert convert_quantity(2, "т", "кг").value == Decimal("2000")
    assert convert_quantity("3.5", "л", "м3").value == Decimal("0.0035")
    assert can_convert("cm", "mm") is True

    requirements = build_conversion_requirements("кг", "т")
    assert requirements.supported is True
    assert requirements.requires_material_profile is False
    assert requirements.required_fields == ()


def test_rebar_conversion_reports_missing_profile_fields_without_guessing() -> None:
    result = convert_quantity(3, "м.п.", "кг", material_group="rebar")

    assert result.success is False
    assert result.error_code == "MISSING_MATERIAL_PROFILE_FIELDS"
    assert result.missing_fields == ("kg_per_meter",)
    assert ("diameter_mm",) in result.alternative_field_sets
    assert can_convert("м.п.", "кг", material_group="rebar") is False


def test_rebar_conversion_uses_technical_profile_when_present() -> None:
    result = convert_quantity(
        3,
        "м.п.",
        "кг",
        material_group="rebar",
        material_profile={"kg_per_meter": "0.888"},
    )

    assert result.success is True
    assert result.unit == "kg"
    assert result.value == Decimal("2.664")
    assert can_convert("м.п.", "кг", {"diameter_mm": 12}, material_group="rebar") is True


def test_board_piece_to_volume_uses_compatibility_group_alias() -> None:
    result = convert_quantity(
        10,
        "шт",
        "м3",
        material_group="lumber_board",
        material_profile={"length_mm": 3000, "width_mm": 150, "thickness_mm": 50},
    )

    assert result.success is True
    assert result.material_group == "board"
    assert result.value == Decimal("0.225")


def test_technical_requirements_are_reported_for_non_seed_material_pairs() -> None:
    report = build_conversion_requirements("упаковка", "м2", material_group="insulation")

    assert report.supported is True
    assert report.material_group == "mineral_wool_slab"
    assert report.requires_material_profile is True
    assert report.required_fields == ("package_area_m2",)


def test_unknown_conversion_returns_controlled_report() -> None:
    result = convert_quantity(1, "мешок", "рулон", material_group="dry_mix")

    assert result.success is False
    assert result.error_code == "UNSUPPORTED_CONVERSION"
    assert "not known" in result.message


def test_module1_unit_registry_does_not_import_orm_or_read_seed_json_directly() -> None:
    source = Path("app/services/module1_unit_conversion_registry.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "import json" not in source
    assert "read_text" not in source
