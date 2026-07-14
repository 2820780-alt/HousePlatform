from __future__ import annotations

from pathlib import Path

from app.services.module1_extraction_blueprint_registry import (
    KEY_BLUEPRINT_GROUPS,
    build_extraction_missing_fields_report,
    get_blueprint,
    get_document_hints,
    get_field_aliases,
    get_module2_extraction_fields,
    get_packaging_fields,
    get_required_extraction_fields,
    has_blueprint,
    list_blueprints,
    validate_extracted_payload,
)


def test_blueprints_cover_required_seed_groups() -> None:
    groups = list_blueprints()

    assert set(KEY_BLUEPRINT_GROUPS).issubset(set(groups))
    for group_code in KEY_BLUEPRINT_GROUPS:
        assert has_blueprint(group_code)
        assert get_blueprint(group_code) is not None


def test_gas_block_blueprint_returns_seed_schema_fields_and_hints() -> None:
    blueprint = get_blueprint("aerated_concrete_block")

    assert blueprint is not None
    assert blueprint.required_fields == (
        "length_mm",
        "width_mm",
        "height_mm",
        "density_class",
        "strength_class",
    )
    assert "volume_per_piece_m3" in blueprint.module2_required_fields
    assert "pieces_per_pallet" in blueprint.packaging_fields
    assert "certificate" in blueprint.document_hints
    assert "m3" in blueprint.unit_hints
    assert "pieces_per_m3" in blueprint.raw_fields


def test_rebar_blueprint_includes_module2_unit_conversion_fields() -> None:
    assert get_required_extraction_fields("rebar") == ("diameter_mm", "steel_class")
    assert "kg_per_meter" in get_module2_extraction_fields("rebar")
    assert "standard_bar_length_m" in get_packaging_fields("rebar")
    assert "mill_certificate" in get_document_hints("rebar")


def test_metal_tile_blueprint_keeps_fastening_pattern_as_material_profile_hint() -> None:
    blueprint = get_blueprint("metal_tile")

    assert blueprint is not None
    assert "fastening_pattern_code" in blueprint.module2_required_fields
    assert "fastening_pattern_code" in blueprint.raw_fields
    assert "screw_consumption" not in blueprint.raw_fields
    assert "screws_per_m2" not in blueprint.raw_fields


def test_field_aliases_map_raw_site_names_to_canonical_fields() -> None:
    aliases = get_field_aliases("gypsum_board_moisture_resistant")

    assert "sheet_type" in aliases["board_type"]
    assert "площадь_листа" in aliases["sheet_area_m2"]

    report = validate_extracted_payload(
        "gypsum_board_moisture_resistant",
        {
            "length": 2500,
            "width": 1200,
            "thickness": 12.5,
            "sheet_type": "Влагостойкий",
            "площадь_листа": {"value": 3, "unit": "м2"},
        },
    )

    assert report.is_valid
    assert report.missing_required == ()
    assert "length_mm" in report.normalized_fields
    assert "sheet_area_m2" in report.normalized_fields


def test_missing_fields_report_is_controlled_and_readable() -> None:
    report = build_extraction_missing_fields_report(
        "ready_mix_concrete",
        {"concrete_class": "B25", "unit": "м3"},
    )

    assert report.blueprint_found is True
    assert report.is_valid is True
    assert report.missing_required == ()
    assert "application" in report.missing_module2_required
    assert report.message == "Extraction payload validated against Module 1 blueprint."


def test_validation_reports_missing_required_fields() -> None:
    report = validate_extracted_payload("rebar", {"diameter": {"value": 12, "unit": "мм"}})

    assert report.is_valid is False
    assert report.missing_required == ("steel_class",)
    assert report.missing_module2_required == ("kg_per_meter",)
    assert report.unit_warnings == ()


def test_validation_reports_unknown_units_without_raw_exception() -> None:
    report = validate_extracted_payload(
        "porcelain_tile",
        {
            "tile_length_mm": {"value": 600, "unit": "мм"},
            "tile_width_mm": {"value": 600, "unit": "parsec"},
            "area_per_box_m2": {"value": 1.44, "unit": "м2"},
        },
    )

    assert report.is_valid is False
    assert report.missing_required == ()
    assert len(report.unit_warnings) == 1
    assert report.unit_warnings[0].field == "tile_width_mm"
    assert report.unit_warnings[0].unit == "parsec"


def test_unknown_group_returns_empty_controlled_report() -> None:
    report = validate_extracted_payload("unknown_material", {"name": "test"})

    assert report.blueprint_found is False
    assert report.resolved_group_code is None
    assert report.is_valid is False
    assert report.message == "Extraction blueprint is not defined for this material group."


def test_blueprint_registry_does_not_import_orm_or_read_seed_json_directly() -> None:
    source = Path("app/services/module1_extraction_blueprint_registry.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "import json" not in source
    assert "read_text" not in source
    assert "source_task_runner" not in source
    assert "source_adapters" not in source
