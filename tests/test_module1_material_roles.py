from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_material_roles import (
    MaterialRole,
    MaterialRoleReadinessReport,
    build_material_role_readiness_report,
    evaluate_material_roles,
    get_conditional_roles,
    get_module2_role_hints,
    get_primary_roles,
    get_roles_for_group,
    get_usage_contexts_for_group,
    list_material_roles,
)
from app.services.module1_technical_profile_packaging import build_material_technical_profile


def _view(
    group_code: str,
    characteristics: dict,
    *,
    material_id: str = "mat-role-001",
    material_name: str = "Role material",
    base_unit: str = "piece",
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
        moderation_status="approved",
        quality=MaterialQualitySummary(
            status="good",
            open_issues=0,
            critical_issues=0,
            warning_issues=0,
            issues=(),
            warnings=(),
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


def test_material_roles_are_loaded_from_seed_role_mappings() -> None:
    roles = list_material_roles()
    board_roles = get_roles_for_group("board")
    concrete_roles = get_roles_for_group("ready_mix_concrete")
    rebar_roles = get_roles_for_group("rebar")
    gas_block_roles = get_roles_for_group("gas_block")
    insulation_roles = get_roles_for_group("mineral_wool_slab")
    metal_tile_roles = get_roles_for_group("metal_tile")

    assert roles
    assert all(isinstance(role, MaterialRole) for role in roles)
    assert {role.role_code for role in board_roles} >= {
        "formwork_board",
        "roof_batten",
        "temporary_flooring",
        "auxiliary_lumber",
        "fence_structure",
    }
    assert {role.role_code for role in concrete_roles} >= {"strip_foundation_concrete", "pile_concrete"}
    assert {role.role_code for role in rebar_roles} >= {"foundation_reinforcement", "slab_reinforcement"}
    assert {role.role_code for role in gas_block_roles} == {"outer_wall_block", "inner_wall_block", "partition_block"}
    assert {role.role_code for role in insulation_roles} >= {"facade_insulation", "roof_insulation"}
    assert {role.role_code for role in metal_tile_roles} == {"roof_covering", "mansard_roof_covering"}


def test_role_contexts_primary_and_conditional_roles_are_available() -> None:
    board_contexts = get_usage_contexts_for_group("board")
    gypsum_conditionals = get_conditional_roles("gypsum_board")
    metal_primary = get_primary_roles("metal_tile")

    assert {context.context_code for context in board_contexts} >= {"formwork", "roof"}
    assert any(role.role_code == "wet_room_sheathing" for role in gypsum_conditionals)
    assert any(role.role_code == "roof_covering" for role in metal_primary)


def test_rebar_role_readiness_uses_technical_profile_without_calculating_technology() -> None:
    profile = build_material_technical_profile(
        _view(
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
    )

    evaluations = evaluate_material_roles(profile)
    report = build_material_role_readiness_report(profile)
    hints = get_module2_role_hints(profile)

    assert isinstance(report, MaterialRoleReadinessReport)
    assert report.status == "roles_ready"
    assert "foundation_reinforcement" in report.applicable_role_codes
    assert not report.missing_fields_by_role
    assert all(item.applicable for item in evaluations)
    assert hints[0]["roleCode"] == "foundation_reinforcement"
    assert hints[0]["technologyCalculated"] is False
    assert hints[0]["estimateCalculated"] is False
    assert hints[0]["module2Calculations"] == "not_performed_by_module1"


def test_role_readiness_reports_missing_fields_per_role() -> None:
    profile = build_material_technical_profile(
        _view(
            "board",
            {
                "length_mm": Decimal("6000"),
                "width_mm": Decimal("150"),
            },
            material_name="Board 25x150x6000",
        )
    )

    report = build_material_role_readiness_report(profile)
    roof_batten = next(item for item in report.evaluations if item.role.role_code == "roof_batten")

    assert report.status == "missing_role_fields"
    assert "roof_batten" in report.blocked_role_codes
    assert roof_batten.missing_fields == ("thickness_mm",)
    assert report.missing_fields_by_role["roof_batten"] == ("thickness_mm",)
    assert "thickness_mm" in roof_batten.module2_hints["requiredTechnicalFields"]


def test_gas_block_gypsum_insulation_and_metal_tile_roles_have_expected_readiness() -> None:
    gas_profile = build_material_technical_profile(
        _view(
            "aerated_concrete_block",
            {
                "length_mm": Decimal("600"),
                "width_mm": Decimal("300"),
                "height_mm": Decimal("200"),
                "density_class": "D500",
                "strength_class": "B2.5",
            },
        )
    )
    gypsum_profile = build_material_technical_profile(
        _view(
            "gypsum_board_moisture_resistant",
            {
                "length_mm": Decimal("2500"),
                "width_mm": Decimal("1200"),
                "thickness_mm": Decimal("12.5"),
                "board_type": "moisture_resistant",
                "sheet_area_m2": Decimal("3.0"),
            },
            base_unit="sheet",
        )
    )
    insulation_profile = build_material_technical_profile(
        _view(
            "mineral_wool_slab",
            {
                "length_mm": Decimal("1000"),
                "width_mm": Decimal("600"),
                "thickness_mm": Decimal("50"),
                "area_per_pack_m2": Decimal("6.0"),
                "application": "facade",
            },
            base_unit="package",
        )
    )
    metal_profile = build_material_technical_profile(
        _view(
            "metal_tile",
            {
                "profile_name": "Monterrey",
                "effective_width_mm": Decimal("1100"),
                "metal_thickness_mm": Decimal("0.5"),
            },
            base_unit="sheet",
        )
    )

    gas_report = build_material_role_readiness_report(gas_profile)
    gypsum_report = build_material_role_readiness_report(gypsum_profile)
    insulation_report = build_material_role_readiness_report(insulation_profile)
    metal_report = build_material_role_readiness_report(metal_profile)

    assert gas_report.applicable_role_codes == ("outer_wall_block", "inner_wall_block", "partition_block")
    assert "wet_room_sheathing" in gypsum_report.applicable_role_codes
    assert "facade_insulation" in insulation_report.applicable_role_codes
    assert metal_report.status == "missing_role_fields"
    assert metal_report.missing_fields_by_role["roof_covering"] == ("coating",)


def test_material_roles_service_does_not_import_orm_or_costing_layers() -> None:
    source = Path("app/services/module1_material_roles.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
    assert "calculate_cost" not in source.lower()
    assert "supplierprice" not in source.lower()
