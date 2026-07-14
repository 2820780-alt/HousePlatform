from __future__ import annotations

from pathlib import Path

from app.services.module1_export_packages import MaterialExportBundle
from app.services.module1_golden_materials import (
    GoldenMaterialRecord,
    build_golden_canonical_view,
    build_golden_material_export_preview,
    build_golden_material_like_object,
    build_golden_material_quality_snapshot,
    build_golden_material_test_matrix,
    get_golden_material,
    list_golden_materials,
    list_golden_materials_by_group,
    validate_all_golden_materials,
    validate_golden_material,
)
from app.services.module1_technical_profile_packaging import build_material_technical_profile


REQUIRED_GROUPS = {
    "aerated_concrete_block",
    "rebar",
    "ready_mix_concrete",
    "gypsum_board_moisture_resistant",
    "board",
    "metal_tile",
    "mineral_wool_slab",
    "gypsum_plaster",
    "deep_penetration_primer",
    "porcelain_tile",
    "flexible_shingle",
}


def test_golden_materials_seed_loads_minimum_fixture_set() -> None:
    records = list_golden_materials()
    groups = {record.group_code for record in records}

    assert len(records) >= 11
    assert REQUIRED_GROUPS.issubset(groups)
    assert all(isinstance(record, GoldenMaterialRecord) for record in records)
    assert get_golden_material("golden_aerated_concrete_block_d500").display_name == "Газоблок D500 600x300x200"


def test_golden_materials_can_be_filtered_by_group() -> None:
    rebar = list_golden_materials_by_group("rebar")

    assert len(rebar) == 1
    assert rebar[0].golden_material_code == "golden_rebar_a500c_12"
    assert rebar[0].characteristics.values["kg_per_meter"] == "0.888"


def test_golden_material_like_object_is_fixture_only_and_not_canonical_write_model() -> None:
    material_like = build_golden_material_like_object("golden_ready_mix_concrete_b25_p4")

    assert material_like["fixtureOnly"] is True
    assert material_like["rawDataIsCanonical"] is False
    assert material_like["id"] == "golden_ready_mix_concrete_b25_p4"
    assert material_like["characteristics"]["concrete_class"] == "B25"


def test_golden_canonical_view_builds_in_memory_material_view() -> None:
    view = build_golden_canonical_view("golden_aerated_concrete_block_d500")
    technical_profile = build_material_technical_profile(view)

    assert view.material_id == "golden_aerated_concrete_block_d500"
    assert view.source_provenance["canonicalBase"] == "GoldenMaterialFixture"
    assert view.source_provenance["fixtureOnly"] is True
    assert technical_profile.group_code == "aerated_concrete_block"
    assert technical_profile.readiness.ready_for_module2 is True


def test_validate_all_golden_materials_reports_export_preview_ready() -> None:
    reports = validate_all_golden_materials()

    assert len(reports) >= 11
    assert all(report.is_valid for report in reports)
    assert all(report.export_preview_available for report in reports)
    assert all(report.json_serializable for report in reports)
    assert all(report.no_side_effects for report in reports)


def test_regular_gypsum_board_fixture_is_explicit_schema_compatibility_variant() -> None:
    record = get_golden_material("golden_gypsum_board_regular")
    report = validate_golden_material(record)

    assert record.group_code == "gypsum_board_moisture_resistant"
    assert any("gypsum_board_regular schema is not present" in warning for warning in report.warnings)
    assert report.is_valid is True


def test_golden_material_export_preview_uses_m1_21_bundle_without_side_effects() -> None:
    preview = build_golden_material_export_preview("golden_rebar_a500c_12")

    assert preview.no_side_effects is True
    assert preview.validation_report.is_valid is True
    assert isinstance(preview.export_bundle, MaterialExportBundle)
    assert preview.export_bundle.no_side_effects is True
    assert preview.export_bundle.clean_material.material_id == "golden_rebar_a500c_12"
    assert preview.export_bundle.module2_package.no_calculation_result is True
    assert preview.export_bundle.module5_package.no_estimate_total is True
    assert preview.export_bundle.module11_signals.no_charts is True


def test_golden_quality_snapshot_and_test_matrix_are_read_only() -> None:
    snapshot = build_golden_material_quality_snapshot("golden_metal_tile_classic")
    matrix = build_golden_material_test_matrix()

    assert snapshot.material_id == "golden_metal_tile_classic"
    assert snapshot.overall_quality_score > 0
    assert matrix["totalGoldenMaterials"] >= 11
    assert matrix["validRecords"] == matrix["totalGoldenMaterials"]
    assert matrix["exportPreviewReady"] == matrix["totalGoldenMaterials"]
    assert matrix["databaseWrites"] is False
    assert matrix["no_side_effects"] is True


def test_golden_materials_layer_is_read_only_and_does_not_import_orm_or_generate_files() -> None:
    source = Path("app/services/module1_golden_materials.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "Material(" not in source
    assert "CanonicalMaterial(" not in source
    assert "requests" not in source
    assert "httpx" not in source
    assert ".to_csv(" not in source
    assert ".to_excel(" not in source
