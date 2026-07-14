from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_technical_profile_packaging import (
    MaterialPackagingProfile,
    MaterialTechnicalProfile,
    build_calculation_readiness_report,
    build_conversion_capabilities,
    build_material_technical_profile,
    build_missing_technical_fields_report,
    build_packaging_profile,
    list_module2_required_fields,
    list_packaging_fields,
    list_required_technical_fields,
    validate_technical_profile,
)


def _view(
    group_code: str,
    characteristics: dict,
    *,
    material_id: str = "mat-technical-001",
    material_name: str = "Technical material",
    base_unit: str = "piece",
    quality_status: str = "good",
    open_issues: int = 0,
) -> MaterialCanonicalView:
    return MaterialCanonicalView(
        material_id=material_id,
        canonical_name=material_name,
        category={"id": "cat-1", "name": "Category", "slug": group_code},
        subcategory=None,
        group={"id": "group-1", "name": group_code, "code": group_code},
        characteristics=tuple(
            MaterialCharacteristicView(name=key, value=value, unit=None)
            for key, value in characteristics.items()
        ),
        technical_profile_hints={
            "baseUnit": {
                "abbreviation": base_unit,
                "name": base_unit,
            },
            "module2Calculations": "not_performed_by_module1",
        },
        evidence=MaterialEvidenceSummary(
            document_count=1,
            source_ref_count=1,
            documents=({"title": "Certificate"},),
            source_refs=({"sourceName": "Source"},),
            moderation_preview_refs=(),
            warnings=(),
        ),
        supplier_price_refs=(),
        moderation_status="approved" if quality_status == "good" else "needs_review",
        quality=MaterialQualitySummary(
            status=quality_status,
            open_issues=open_issues,
            critical_issues=open_issues,
            warning_issues=0,
            issues=(),
            warnings=("Material has critical quality issues.",) if open_issues else (),
        ),
        source_provenance={
            "canonicalBase": "Material",
            "rawDataIsCanonical": False,
        },
        status="ACTIVE",
        warnings=(),
        created_at=None,
        updated_at=None,
    )


def test_rebar_profile_is_ready_for_module2_and_has_meter_kg_conversion() -> None:
    view = _view(
        "rebar",
        {
            "diameter_mm": Decimal("12"),
            "steel_class": "A500C",
            "kg_per_meter": Decimal("0.888"),
            "standard_bar_length_m": Decimal("11.7"),
        },
        material_name="Rebar A500C 12 mm",
        base_unit="kg",
    )

    profile = build_material_technical_profile(view)
    capability = next(item for item in profile.unit_conversion_capabilities if item.from_unit == "linear_meter" and item.to_unit == "kg")

    assert isinstance(profile, MaterialTechnicalProfile)
    assert profile.group_code == "rebar"
    assert "diameter_mm" in list_required_technical_fields("rebar")
    assert "kg_per_meter" in profile.module2_required_fields
    assert profile.missing_module2_fields == ()
    assert profile.readiness.status == "ready_for_module2"
    assert capability.supported is True
    assert capability.requires_material_profile is True
    assert capability.missing_fields == ()
    assert profile.usage_hints["module2Calculations"] == "not_performed_by_module1"
    assert profile.usage_hints["module5Costing"] == "not_performed_by_module1"


def test_gas_block_profile_reports_missing_module2_and_packaging_fields() -> None:
    view = _view(
        "aerated_concrete_block",
        {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
            "strength_class": "B2.5",
        },
    )

    profile = build_material_technical_profile(view)
    packaging = build_packaging_profile(view)
    report = build_missing_technical_fields_report(profile)

    assert "volume_per_piece_m3" in list_module2_required_fields("aerated_concrete_block")
    assert "pieces_per_m3" in packaging.missing_fields
    assert "volume_per_piece_m3" in profile.missing_module2_fields
    assert profile.readiness.status == "missing_module2_fields"
    assert report.missing_module2_fields == profile.missing_module2_fields
    assert "pieces_per_pallet" in list_packaging_fields("aerated_concrete_block")


def test_gypsum_board_packaging_and_sheet_to_m2_conversion_are_available() -> None:
    view = _view(
        "gypsum_board_moisture_resistant",
        {
            "length_mm": Decimal("2500"),
            "width_mm": Decimal("1200"),
            "thickness_mm": Decimal("12.5"),
            "board_type": "moisture_resistant",
            "sheet_area_m2": Decimal("3.0"),
            "sheets_per_pack": 50,
        },
        material_name="Moisture-resistant gypsum board",
        base_unit="sheet",
    )

    packaging = build_packaging_profile(view)
    capabilities = build_conversion_capabilities(view)
    sheet_to_m2 = next(item for item in capabilities if item.from_unit == "sheet" and item.to_unit == "m2")

    assert isinstance(packaging, MaterialPackagingProfile)
    assert packaging.sheet_area == Decimal("3.0")
    assert packaging.pieces_per_package == 50
    assert sheet_to_m2.supported is True
    assert sheet_to_m2.missing_fields == ()


def test_primer_profile_reports_conversion_requirements_without_calculating_technology() -> None:
    view = _view(
        "deep_penetration_primer",
        {
            "primer_type": "deep",
            "compatible_substrates": ("concrete", "plaster"),
            "package_volume_l": Decimal("10"),
        },
        material_name="Deep penetration primer",
        base_unit="liter",
    )

    readiness = build_calculation_readiness_report(view)
    capabilities = build_conversion_capabilities(view)
    liter_to_m2 = next(item for item in capabilities if item.from_unit == "liter" and item.to_unit == "m2")

    assert readiness.status in {"missing_module2_fields", "insufficient_data"}
    assert liter_to_m2.supported is True
    assert liter_to_m2.requires_material_profile is True
    assert liter_to_m2.missing_fields
    assert "technology" not in " ".join(readiness.warnings).lower()


def test_quality_issue_forces_needs_moderation_readiness() -> None:
    view = _view(
        "board",
        {
            "length_mm": Decimal("6000"),
            "width_mm": Decimal("150"),
            "thickness_mm": Decimal("25"),
            "volume_per_piece_m3": Decimal("0.0225"),
        },
        quality_status="needs_review",
        open_issues=1,
    )

    readiness = build_calculation_readiness_report(view)
    profile = build_material_technical_profile(view)

    assert readiness.status == "needs_moderation"
    assert profile.quality_status == "needs_review"
    assert "Material has critical quality issues." in readiness.quality_warnings


def test_validation_report_lists_required_module2_packaging_and_conversion_warnings() -> None:
    view = _view(
        "mineral_wool_slab",
        {
            "length_mm": Decimal("1000"),
            "width_mm": Decimal("600"),
            "thickness_mm": Decimal("50"),
            "density_kg_m3": Decimal("45"),
        },
        base_unit="package",
    )

    profile = build_material_technical_profile(view)
    report = validate_technical_profile(profile)

    assert report.group_code == "mineral_wool_slab"
    assert "area_per_pack_m2" in report.module2_required_fields
    assert "area_per_pack_m2" in report.missing_module2_fields
    assert report.packaging_fields
    assert report.provided_fields == tuple(sorted(profile.technical_characteristics))
    assert report.message == "Technical profile validated without writing data."


def test_technical_profile_packaging_service_does_not_import_orm_or_costing_layers() -> None:
    source = Path("app/services/module1_technical_profile_packaging.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
    assert "source_task_runner" not in source
    assert "calculate_cost" not in source.lower()
    assert "supplierprice" not in source.lower()
