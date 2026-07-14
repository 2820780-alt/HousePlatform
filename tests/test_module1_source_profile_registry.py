from __future__ import annotations

from pathlib import Path

from app.services.module1_source_profile_registry import (
    build_profile_readiness_report,
    get_allowed_objects,
    get_category_mapping,
    get_extraction_profile,
    get_field_mapping,
    get_source_profile,
    get_target_material_groups,
    get_unit_mapping,
    list_extraction_profiles,
    list_source_profiles,
    validate_extraction_profile,
    validate_source_profile,
)


def test_source_profile_registry_returns_read_only_profile() -> None:
    profile = get_source_profile("YUFO_VKBLOCK")

    assert profile is not None
    assert profile.source_code == "YUFO_VKBLOCK"
    assert profile.source_type == "manufacturer_site"
    assert profile.base_url == "https://vkblock.ru/"
    assert profile.status == "test"
    assert profile.allowed_objects == ("materials", "prices", "documents", "availability")
    assert "does not run parsing" in profile.notes[0]


def test_registry_lists_source_and_extraction_profiles() -> None:
    source_codes = {profile.source_code for profile in list_source_profiles()}
    extraction_codes = {profile.source_code for profile in list_extraction_profiles()}

    assert "BAUCENTER" in source_codes
    assert "YUFO_VKBLOCK" in extraction_codes
    assert "SUPPLIER_FILE_UPLOAD" in source_codes


def test_extraction_profile_links_source_to_blueprints() -> None:
    profile = get_extraction_profile("YUFO_VKBLOCK")

    assert profile is not None
    assert profile.target_material_groups == ("aerated_concrete_block",)
    assert profile.blueprint_refs == ("aerated_concrete_block",)
    assert "aerated_concrete_block" in profile.field_mapping_rules
    assert "length_mm" in profile.field_mapping_rules["aerated_concrete_block"]
    assert "piece" in profile.unit_mapping_rules["aerated_concrete_block"]
    assert "certificate" in profile.document_extraction_hints["aerated_concrete_block"]
    assert "Do not create canonical Material" in profile.adapter_compatibility_notes[0]


def test_extraction_profile_can_be_filtered_by_material_group_alias() -> None:
    profile = get_extraction_profile("BAUCENTER", material_group="gas_block")

    assert profile is not None
    assert profile.target_material_groups == ("aerated_concrete_block",)
    assert profile.blueprint_refs == ("aerated_concrete_block",)


def test_mapping_helpers_return_field_unit_and_category_rules() -> None:
    field_mapping = get_field_mapping("YUFO_DOSKA_BRUS", "board")
    unit_mapping = get_unit_mapping("YUFO_DOSKA_BRUS", "board")
    category_mapping = get_category_mapping("YUFO_DOSKA_BRUS", "board")

    assert "thickness_mm" in field_mapping
    assert "thickness" in field_mapping["thickness_mm"]
    assert "m3" in unit_mapping
    assert "piece" in unit_mapping
    assert "lumber" in category_mapping


def test_allowed_objects_and_target_groups_are_exposed() -> None:
    assert get_allowed_objects("BAUCENTER") == ("materials", "prices", "documents", "availability")
    assert "metal_tile" in get_target_material_groups("YUFO_SPK_KRASNODAR")
    assert get_target_material_groups("UNKNOWN_SOURCE") == ()


def test_profile_validation_reports_missing_and_invalid_fields() -> None:
    valid = validate_source_profile(get_source_profile("YUFO_VKBLOCK"))
    invalid = validate_source_profile({"source_code": "X", "source_type": "crawler", "allowed_objects": ("materials",), "status": "test"})

    assert valid.is_valid is True
    assert invalid.is_valid is False
    assert invalid.invalid_fields == ("source_type",)


def test_extraction_profile_validation_checks_blueprint_coverage() -> None:
    ready_profile = get_extraction_profile("YUFO_VKBLOCK")
    cable_profile = get_extraction_profile("YUFO_YUGKABEL")

    ready = validate_extraction_profile(ready_profile)
    cable = validate_extraction_profile(cable_profile)

    assert ready.is_valid is True
    assert cable.is_valid is False
    assert cable.invalid_fields == ("blueprint:cable",)


def test_readiness_report_shows_ready_and_missing_configuration() -> None:
    ready = build_profile_readiness_report("YUFO_VKBLOCK")
    missing = build_profile_readiness_report("YUFO_YUGKABEL")
    unknown = build_profile_readiness_report("UNKNOWN_SOURCE")

    assert ready.ready is True
    assert ready.has_source_profile is True
    assert ready.has_extraction_profile is True
    assert ready.missing_blueprints == ()

    assert missing.ready is False
    assert missing.missing_blueprints == ("cable",)
    assert "extraction_blueprints" in missing.not_configured

    assert unknown.ready is False
    assert unknown.not_configured == ("source_profile", "extraction_profile")


def test_source_profile_registry_does_not_import_orm_runner_or_adapters() -> None:
    source = Path("app/services/module1_source_profile_registry.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "source_task_runner" not in source
    assert "source_integrations" not in source
    assert "app.services.source_profiles" not in source
    assert "import json" not in source
    assert "read_text" not in source
