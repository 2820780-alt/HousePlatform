from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_compatibility_matrix import (
    CompatibilityReadinessReport,
    MaterialCompatibilityContext,
    MaterialCompatibilityEvaluation,
    build_compatibility_readiness_report,
    evaluate_material_compatibility,
    get_compatibility_rules_for_group,
    get_forbidden_contexts,
    get_module2_compatibility_hints,
    get_module5_selection_hints,
    get_required_preparation_actions,
    list_compatibility_rules,
)
from app.services.module1_technical_profile_packaging import build_material_technical_profile


def _profile(
    group_code: str,
    characteristics: dict,
    *,
    material_id: str = "mat-compat-001",
    material_name: str = "Compatibility material",
    base_unit: str = "piece",
):
    return build_material_technical_profile(
        MaterialCanonicalView(
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
    )


def test_compatibility_rules_are_loaded_from_seed() -> None:
    rules = list_compatibility_rules()
    gypsum_rules = get_compatibility_rules_for_group("gypsum_plaster")
    board_rules = get_compatibility_rules_for_group("board")

    assert len(rules) >= 15
    assert {rule.context for rule in gypsum_rules} == {"plaster"}
    assert {rule.context for rule in board_rules} == {"roof_batten", "formwork_board"}
    assert any(rule.context == "wet_zone" and rule.result_type == "forbidden" for rule in get_compatibility_rules_for_group("gypsum_board_regular"))
    assert "wet_zone" in get_forbidden_contexts("gypsum_board_moisture_resistant")


def test_gas_block_plaster_requires_deep_primer_preparation() -> None:
    profile = _profile(
        "gypsum_plaster",
        {
            "consumption_kg_m2_mm": Decimal("0.9"),
            "min_layer_mm": Decimal("5"),
            "max_layer_mm": Decimal("50"),
        },
        base_unit="kg",
    )
    context = MaterialCompatibilityContext(
        substrate_type="gas_block",
        usage_context="plaster",
        environment="dry_room",
    )

    evaluation = evaluate_material_compatibility(profile, context)
    required_actions = get_required_preparation_actions(profile, context)
    module2_hints = get_module2_compatibility_hints(profile, context)
    module5_hints = get_module5_selection_hints(profile, context)

    assert isinstance(evaluation, MaterialCompatibilityEvaluation)
    assert evaluation.result_type == "allowed_with_preparation"
    assert evaluation.allowed is True
    assert required_actions[0].resource_code == "deep_penetration_primer"
    assert required_actions[0].status == "missing"
    assert module2_hints["technologyCalculated"] is False
    assert module5_hints["automaticSelection"] is False
    assert module5_hints["priceCalculated"] is False


def test_prepared_gas_block_plaster_becomes_allowed() -> None:
    profile = _profile(
        "gypsum_plaster",
        {
            "consumption_kg_m2_mm": Decimal("0.9"),
            "min_layer_mm": Decimal("5"),
            "max_layer_mm": Decimal("50"),
        },
        base_unit="kg",
    )
    context = MaterialCompatibilityContext(
        substrate_type="aerated_concrete_block",
        usage_context="plaster",
        provided_preparation_resources=("deep_penetration_primer",),
    )

    evaluation = evaluate_material_compatibility(profile, context)

    assert evaluation.result_type == "allowed"
    assert not get_required_preparation_actions(profile, context)
    assert evaluation.required_preparation[0].status == "provided"


def test_smooth_concrete_plaster_is_conditional_without_adhesion_preparation() -> None:
    profile = _profile(
        "gypsum_plaster",
        {
            "consumption_kg_m2_mm": Decimal("0.9"),
            "min_layer_mm": Decimal("5"),
            "max_layer_mm": Decimal("50"),
        },
        base_unit="kg",
    )
    context = MaterialCompatibilityContext(
        substrate_type="smooth_concrete",
        usage_context="plaster",
    )

    evaluation = evaluate_material_compatibility(profile, context)

    assert evaluation.result_type == "conditional"
    assert evaluation.allowed is True
    assert {item.resource_code for item in evaluation.required_preparation} == {"adhesion_primer", "concrete_contact"}


def test_regular_gypsum_board_is_forbidden_in_wet_zone() -> None:
    profile = _profile(
        "gypsum_board_regular",
        {
            "length_mm": Decimal("2500"),
            "width_mm": Decimal("1200"),
            "thickness_mm": Decimal("12.5"),
            "board_type": "regular",
        },
        base_unit="sheet",
    )
    context = MaterialCompatibilityContext(
        environment="wet_room",
        moisture_exposure="wet",
    )

    evaluation = evaluate_material_compatibility(profile, context)

    assert evaluation.result_type == "forbidden"
    assert evaluation.allowed is False
    assert evaluation.forbidden_reasons
    assert evaluation.confidence == Decimal("0")


def test_moisture_resistant_gypsum_board_in_wet_zone_needs_waterproofing() -> None:
    profile = _profile(
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
    context = MaterialCompatibilityContext(
        environment="wet_room",
        moisture_exposure="wet",
    )

    evaluation = evaluate_material_compatibility(profile, context)

    assert evaluation.result_type == "allowed_with_preparation"
    assert {item.resource_code for item in evaluation.required_preparation} == {
        "liquid_waterproofing",
        "waterproofing_tape",
    }


def test_metal_tile_roof_reports_missing_coating_as_insufficient_data() -> None:
    profile = _profile(
        "metal_tile",
        {
            "profile_name": "Monterrey",
            "effective_width_mm": Decimal("1100"),
            "metal_thickness_mm": Decimal("0.5"),
        },
        base_unit="sheet",
    )
    context = MaterialCompatibilityContext(
        usage_context="metal_tile_roof",
        environment="roof",
    )

    evaluation = evaluate_material_compatibility(profile, context)

    assert evaluation.result_type == "insufficient_data"
    assert "coating" in evaluation.missing_fields
    assert "roof_covering" in evaluation.required_material_roles
    assert evaluation.module2_hints["technologyCalculated"] is False


def test_board_roof_batten_uses_role_fields_and_does_not_calculate_quantity() -> None:
    profile = _profile(
        "board",
        {
            "length_mm": Decimal("6000"),
            "width_mm": Decimal("150"),
        },
    )
    context = MaterialCompatibilityContext(
        usage_context="roof_batten",
        environment="roof",
    )

    evaluation = evaluate_material_compatibility(profile, context)

    assert evaluation.result_type == "insufficient_data"
    assert "thickness_mm" in evaluation.missing_fields
    assert "roof_batten" in evaluation.required_material_roles
    assert "quantity" not in str(evaluation.module2_hints).lower()


def test_compatibility_readiness_report_lists_contexts_and_preparation() -> None:
    profile = _profile(
        "metal_tile",
        {
            "profile_name": "Monterrey",
            "effective_width_mm": Decimal("1100"),
            "metal_thickness_mm": Decimal("0.5"),
            "coating": "polyester",
        },
        base_unit="sheet",
    )

    report = build_compatibility_readiness_report(profile)

    assert isinstance(report, CompatibilityReadinessReport)
    assert report.status == "ready_for_compatibility_evaluation"
    assert report.allowed_contexts == ("metal_tile_roof",)
    assert {item.resource_code for item in report.preparation_actions} >= {
        "batten",
        "counter_batten",
        "windproof_membrane",
        "roofing_fastener",
    }
    assert report.module2_hints[0]["technologyCalculated"] is False
    assert report.module5_hints[0]["priceCalculated"] is False


def test_compatibility_matrix_service_does_not_import_orm_or_costing_layers() -> None:
    source = Path("app/services/module1_compatibility_matrix.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert "db.add(" not in source
    assert "calculate_cost" not in source.lower()
    assert "supplierprice" not in source.lower()
