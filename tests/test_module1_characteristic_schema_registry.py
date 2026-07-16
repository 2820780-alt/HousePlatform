from pathlib import Path

from app.services.module1_characteristic_schema_registry import (
    CharacteristicSchemaRegistry,
    build_missing_required_report,
    get_required_characteristics,
    get_schema,
    has_schema,
    list_schema_groups,
    validate_characteristics,
)


def test_schema_registry_uses_seed_registry_groups():
    groups = list_schema_groups()

    assert groups == tuple(sorted(groups))
    assert "aerated_concrete_block" in groups
    assert "gypsum_board_regular" in groups
    assert "gypsum_board_moisture_resistant" in groups
    assert "rebar" in groups
    assert "ready_mix_concrete" in groups
    assert "gypsum_plaster" in groups
    assert "deep_penetration_primer" in groups
    assert "porcelain_tile" in groups
    assert "metal_tile" in groups
    assert "board" in groups
    assert "mineral_wool_slab" in groups


def test_get_schema_by_fact_seed_code_and_aliases():
    registry = CharacteristicSchemaRegistry()

    assert registry.has_schema("aerated_concrete_block") is True
    assert registry.has_schema("gas_block") is True
    assert registry.has_schema("газоблок") is True
    assert registry.has_schema("gypsum_board") is True
    assert registry.has_schema("gypsum_board_regular") is True
    assert registry.has_schema("concrete") is True
    assert registry.has_schema("dry_mix") is True
    assert registry.has_schema("primer") is True
    assert registry.has_schema("tile") is True
    assert registry.has_schema("roofing") is True
    assert registry.has_schema("lumber_board") is True
    assert registry.has_schema("insulation") is True
    assert registry.has_schema("unknown_group") is False

    schema = registry.get_schema("gas_block")

    assert schema is not None
    assert schema.group_code == "aerated_concrete_block"


def test_required_and_recommended_characteristics_are_returned():
    gas_block_required = get_required_characteristics("gas_block")
    schema_registry = CharacteristicSchemaRegistry()
    gypsum_recommended = schema_registry.get_recommended_characteristics("gypsum_board")
    regular_required = schema_registry.get_required_characteristics("gypsum_board_regular")
    regular_module2_required = schema_registry.get_module2_required_characteristics("gypsum_board_regular")
    regular_recommended = schema_registry.get_recommended_characteristics("gypsum_board_regular")

    assert gas_block_required == (
        "length_mm",
        "width_mm",
        "height_mm",
        "density_class",
        "strength_class",
    )
    assert "sheet_area_m2" in CharacteristicSchemaRegistry().get_module2_required_characteristics("gypsum_board")
    assert "edge_type" in gypsum_recommended
    assert "application" in gypsum_recommended


def test_validation_report_detects_missing_required_characteristics():
    report = build_missing_required_report(
        "aerated_concrete_block",
        {
            "length_mm": 600,
            "height_mm": 200,
            "density_class": "D500",
        },
    )

    assert report.schema_found is True
    assert report.resolved_group_code == "aerated_concrete_block"
    assert report.is_valid is False
    assert report.missing_required == ("width_mm", "strength_class")
    assert "volume_per_piece_m3" in report.missing_module2_required
    assert report.type_errors == tuple()
    assert report.unit_errors == tuple()


def test_validation_accepts_complete_required_characteristics_and_reports_module2_gaps():
    report = validate_characteristics(
        "rebar",
        {
            "diameter_mm": 12,
            "steel_class": "A500C",
        },
    )

    assert report.is_valid is True
    assert report.missing_required == tuple()
    assert report.missing_module2_required == ("kg_per_meter",)
    assert report.missing_recommended == ("standard_bar_length_m", "profile_type", "certificate")


def test_validation_accepts_full_technical_profile_for_key_groups():
    registry = CharacteristicSchemaRegistry()

    samples = {
        "gypsum_board_regular": {
            "length_mm": 2500,
            "width_mm": 1200,
            "thickness_mm": 12.5,
            "board_type": "regular",
            "sheet_area_m2": 3.0,
        },
        "ready_mix_concrete": {
            "concrete_class": "B25",
            "unit": "m3",
        },
        "gypsum_plaster": {
            "consumption_kg_m2_mm": 0.9,
            "min_layer_mm": 5,
            "max_layer_mm": 50,
        },
        "deep_penetration_primer": {
            "consumption_l_m2": 0.12,
            "primer_type": "deep_penetration",
        },
        "porcelain_tile": {
            "tile_length_mm": 600,
            "tile_width_mm": 600,
            "area_per_box_m2": 1.44,
        },
        "metal_tile": {
            "profile_name": "Монтерей",
            "metal_thickness_mm": 0.45,
            "effective_width_mm": 1100,
        },
        "board": {
            "thickness_mm": 25,
            "width_mm": 150,
            "length_mm": 6000,
            "wood_type": "pine",
        },
        "mineral_wool_slab": {
            "length_mm": 1200,
            "width_mm": 600,
            "thickness_mm": 100,
            "area_per_pack_m2": 4.32,
        },
    }

    for group_code, characteristics in samples.items():
        report = registry.validate_characteristics(group_code, characteristics)
        assert report.is_valid is True, (group_code, report)


def test_unknown_group_report_is_explicit_and_non_throwing():
    report = validate_characteristics("made_up_group", {"foo": "bar"})

    assert report.schema_found is False
    assert report.resolved_group_code is None
    assert report.is_valid is False
    assert report.provided_fields == ("foo",)


def test_function_level_api_matches_registry_api():
    assert has_schema("gas_block") is True
    assert get_schema("gas_block") == CharacteristicSchemaRegistry().get_schema("gas_block")


def test_registry_does_not_import_orm_or_read_seed_directly():
    source = Path("app/services/module1_characteristic_schema_registry.py").read_text(encoding="utf-8")

    assert "from app.models" not in source
    assert "import json" not in source
    assert "read_text" not in source
    assert "get_material_knowledge_seed_registry" in source
    assert "reference_data" not in source
    assert "ATOM_REF2" not in source
