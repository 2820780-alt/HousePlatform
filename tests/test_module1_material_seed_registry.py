import json
from pathlib import Path

import pytest

from app.services.module1_material_seed_registry import (
    KEY_MATERIAL_GROUPS,
    MaterialKnowledgeSeedError,
    get_material_knowledge_seed_registry,
    load_material_knowledge_seed,
    validate_material_knowledge_seed,
)


SEED_PATH = Path("src/modules/module1/seeds/material_knowledge_seed.json")


def test_material_knowledge_seed_loads_from_repository():
    registry = load_material_knowledge_seed(SEED_PATH)

    assert registry.version
    assert registry.module == "Module 1 Material Knowledge Core"
    assert len(registry.taxonomy) == 19
    assert len(registry.characteristic_schemas) == 12
    assert len(registry.role_mappings) == 10
    assert len(registry.compatibility_rules) == 15
    assert len(registry.alternative_rules) == 13
    assert len(registry.unit_conversions) == 7


def test_cached_registry_uses_default_seed_path():
    registry = get_material_knowledge_seed_registry()

    assert registry.has_material_group("aerated_concrete_block")
    assert registry.has_material_group("rebar")
    assert registry.has_material_group("board")
    assert registry.has_material_group("metal_tile")


def test_registry_returns_taxonomy_groups_and_children():
    registry = load_material_knowledge_seed(SEED_PATH)

    blocks = registry.get_taxonomy_group("blocks_and_bricks")

    assert blocks is not None
    assert blocks.name == "Блоки, кирпич, кладочные материалы"
    assert "aerated_concrete_block" in blocks.children
    assert "ceramic_block" in blocks.children
    assert "blocks_and_bricks" in registry.material_group_codes()


def test_key_material_groups_have_required_characteristics():
    registry = load_material_knowledge_seed(SEED_PATH)

    for group_code in KEY_MATERIAL_GROUPS:
        required = registry.required_characteristics(group_code)
        assert required, group_code

    assert registry.required_characteristics("aerated_concrete_block") == (
        "length_mm",
        "width_mm",
        "height_mm",
        "density_class",
        "strength_class",
    )
    assert "kg_per_meter" in registry.module2_required_characteristics("rebar")
    assert "volume_per_piece_m3" in registry.module2_required_characteristics("aerated_concrete_block")


def test_registry_returns_role_mappings_and_rules():
    registry = load_material_knowledge_seed(SEED_PATH)

    board_roles = registry.role_mapping("board")
    gypsum_rules = registry.compatibility_for_material("gypsum_plaster")
    gkl_alternatives = registry.alternatives_from("gypsum_board_regular")

    assert board_roles is not None
    assert "formwork_board" in board_roles.roles
    assert "roof_batten" in board_roles.roles
    assert "foundation_reinforcement" in registry.role_mapping("rebar").roles
    assert "outer_wall_block" in registry.role_mapping("aerated_concrete_block").roles
    assert "facade_insulation" in registry.role_mapping("mineral_wool_slab").roles
    assert any(rule.status == "warning" for rule in gypsum_rules)
    assert any(rule.material == "gypsum_board_moisture_resistant" and rule.context == "wet_zone" for rule in registry.compatibility_rules)
    assert any(rule.material == "mineral_wool_slab" and rule.context == "facade_insulation" for rule in registry.compatibility_rules)
    assert any(rule.material == "board" and rule.context == "roof_batten" for rule in registry.compatibility_rules)
    assert any(rule.material == "ready_mix_concrete" and rule.context == "foundation" for rule in registry.compatibility_rules)
    assert any(rule.to_material == "gypsum_board_moisture_resistant" for rule in gkl_alternatives)
    assert any(rule.alternative_type == "full_analog" for rule in registry.alternative_rules)
    assert any(rule.alternative_type == "conditional_replacement" for rule in registry.alternative_rules)
    assert all(rule.alternative_type != "conditional_alternative" for rule in registry.alternative_rules)


def test_registry_returns_unit_conversions():
    registry = load_material_knowledge_seed(SEED_PATH)

    rebar_conversions = registry.unit_conversions_for_group("rebar")
    board_conversions = registry.unit_conversions_for_group("board")

    assert len(rebar_conversions) == 1
    assert rebar_conversions[0].from_unit == "m"
    assert rebar_conversions[0].to_unit == "kg"
    assert rebar_conversions[0].fallback == "diameter_mm^2 / 162"
    assert board_conversions[0].formula == "thickness_m * width_m * length_m * pieces"


def test_seed_validation_reports_missing_sections():
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    raw.pop("taxonomy")

    assert validate_material_knowledge_seed(raw) == ("missing required section: taxonomy",)


def test_seed_validation_reports_invalid_schema_shape():
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    raw["characteristicSchemas"]["rebar"]["required"] = []

    errors = validate_material_knowledge_seed(raw)

    assert "characteristicSchemas[rebar].required must not be empty" in errors
    assert "key material group has no required characteristics: rebar" in errors


def test_seed_validation_rejects_legacy_alternative_type():
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    raw["alternativeRules"][0]["type"] = "conditional_alternative"

    errors = validate_material_knowledge_seed(raw)

    assert any("alternativeRules[0].type must be one of" in error for error in errors)


def test_invalid_seed_file_raises_without_side_effects(tmp_path):
    invalid_seed = tmp_path / "material_knowledge_seed.json"
    invalid_seed.write_text("{not-json", encoding="utf-8")

    with pytest.raises(MaterialKnowledgeSeedError, match="not valid JSON"):
        load_material_knowledge_seed(invalid_seed)


def test_seed_registry_does_not_create_orm_materials_or_catalog_products():
    source = Path("app/services/module1_material_seed_registry.py").read_text(encoding="utf-8")

    assert "from app.models" not in source
    assert "Material(" not in source
    assert "CatalogProduct(" not in source
    assert "SupplierPrice(" not in source
