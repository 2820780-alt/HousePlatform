from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_alternatives_analogs import (
    MaterialAlternativeEvaluation,
    MaterialAlternativeReadinessReport,
    build_alternative_readiness_report,
    evaluate_material_alternative,
    get_allowed_alternative_groups,
    get_forbidden_replacements,
    get_module2_alternative_hints,
    get_module5_selection_hints,
    get_alternative_rules_for_group,
    list_alternative_rules,
)
from app.services.module1_canonical_material_store import (
    MaterialCanonicalView,
    MaterialCharacteristicView,
    MaterialEvidenceSummary,
    MaterialQualitySummary,
)
from app.services.module1_technical_profile_packaging import build_material_technical_profile


def _profile(
    group_code: str,
    characteristics: dict,
    *,
    material_id: str = "mat-alt-001",
    material_name: str = "Alternative material",
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


def test_alternative_rules_are_loaded_from_seed_and_cover_required_types() -> None:
    rules = list_alternative_rules()
    types = {rule.alternative_type for rule in rules}
    concrete_rules = get_alternative_rules_for_group("ready_mix_concrete")
    forbidden_gkl = get_forbidden_replacements("gypsum_board")

    assert types >= {
        "full_analog",
        "technical_alternative",
        "functional_alternative",
        "conditional_replacement",
        "forbidden_replacement",
    }
    assert concrete_rules[0].target_group == "ready_mix_concrete"
    assert concrete_rules[0].alternative_type == "full_analog"
    assert forbidden_gkl[0].target_group == "gypsum_board_regular"
    assert "ready_mix_concrete" in get_allowed_alternative_groups("ready_mix_concrete")


def test_full_analog_evaluation_allows_matching_concrete_without_calculating() -> None:
    source = _profile(
        "ready_mix_concrete",
        {
            "concrete_class": "B25",
            "unit": "m3",
            "application": "foundation",
            "mobility_class": "P4",
            "frost_resistance": "F150",
            "water_resistance": "W6",
        },
        material_id="concrete-source",
    )
    target = _profile(
        "ready_mix_concrete",
        {
            "concrete_class": "B25",
            "unit": "m3",
            "application": "foundation",
            "mobility_class": "P4",
            "frost_resistance": "F150",
            "water_resistance": "W6",
        },
        material_id="concrete-target",
    )

    evaluation = evaluate_material_alternative(source, target)

    assert isinstance(evaluation, MaterialAlternativeEvaluation)
    assert evaluation.alternative_type == "full_analog"
    assert evaluation.allowed is True
    assert evaluation.confidence == Decimal("0.95")
    assert not evaluation.missing_fields
    assert not evaluation.conflicting_fields
    assert evaluation.module2_hints["technologyCalculated"] is False
    assert evaluation.module5_hints["automaticSelection"] is False
    assert evaluation.module5_hints["priceCalculated"] is False


def test_concrete_alternative_reports_conflicting_class() -> None:
    source = _profile(
        "ready_mix_concrete",
        {
            "concrete_class": "B25",
            "unit": "m3",
            "application": "foundation",
            "mobility_class": "P4",
            "frost_resistance": "F150",
            "water_resistance": "W6",
        },
    )
    target = _profile(
        "ready_mix_concrete",
        {
            "concrete_class": "B20",
            "unit": "m3",
            "application": "foundation",
            "mobility_class": "P4",
            "frost_resistance": "F150",
            "water_resistance": "W6",
        },
    )

    evaluation = evaluate_material_alternative(source, target)

    assert evaluation.allowed is False
    assert "concrete_class" in evaluation.conflicting_fields
    assert "manual review" in evaluation.explanation


def test_forbidden_gkl_replacement_is_blocked_by_seed_rule() -> None:
    moisture = _profile(
        "gypsum_board_moisture_resistant",
        {
            "length_mm": Decimal("2500"),
            "width_mm": Decimal("1200"),
            "thickness_mm": Decimal("12.5"),
            "board_type": "moisture_resistant",
            "sheet_area_m2": Decimal("3.0"),
            "application": "wet_room",
        },
        base_unit="sheet",
    )
    regular = _profile(
        "gypsum_board_regular",
        {
            "length_mm": Decimal("2500"),
            "width_mm": Decimal("1200"),
            "thickness_mm": Decimal("12.5"),
            "board_type": "regular",
            "application": "wet_room",
        },
        base_unit="sheet",
    )

    evaluation = evaluate_material_alternative(moisture, regular)

    assert evaluation.alternative_type == "forbidden_replacement"
    assert evaluation.allowed is False
    assert evaluation.confidence == Decimal("0")
    assert "forbidden" in evaluation.explanation.lower()
    assert any("forbidden" in warning.lower() for warning in evaluation.warnings)


def test_board_conditional_replacement_reports_missing_role_dimension_fields() -> None:
    source = _profile(
        "board",
        {
            "length_mm": Decimal("6000"),
            "width_mm": Decimal("150"),
        },
    )
    target = _profile(
        "board",
        {
            "length_mm": Decimal("6000"),
            "width_mm": Decimal("150"),
            "thickness_mm": Decimal("25"),
        },
    )

    report = build_alternative_readiness_report(source)
    evaluation = evaluate_material_alternative(source, target)

    assert isinstance(report, MaterialAlternativeReadinessReport)
    assert report.status == "missing_alternative_fields"
    assert "thickness_mm" in report.missing_fields
    assert "source.thickness_mm" in evaluation.missing_fields
    assert evaluation.allowed is False
    assert evaluation.alternative_type == "conditional_replacement"


def test_metal_tile_hints_include_profile_fields_without_fastener_selection() -> None:
    source = _profile(
        "metal_tile",
        {
            "profile_name": "Monterrey",
            "effective_width_mm": Decimal("1100"),
            "metal_thickness_mm": Decimal("0.5"),
            "coating": "polyester",
        },
        base_unit="sheet",
    )

    module2_hints = get_module2_alternative_hints(source)
    module5_hints = get_module5_selection_hints(source)
    report = build_alternative_readiness_report(source)

    assert report.status == "ready_for_alternative_evaluation"
    assert "effective_width_mm" in module2_hints[0]["requiredMatchingFields"]
    assert module2_hints[0]["technologyCalculated"] is False
    assert module5_hints[0]["automaticSelection"] is False
    assert module5_hints[0]["priceCalculated"] is False
    assert "fastener" not in str(module2_hints[0]).lower()


def test_unknown_pair_is_not_auto_selected() -> None:
    source = _profile("rebar", {"diameter_mm": Decimal("12"), "steel_class": "A500C", "kg_per_meter": Decimal("0.888")})
    target = _profile("metal_tile", {"profile_name": "Monterrey", "effective_width_mm": Decimal("1100")})

    evaluation = evaluate_material_alternative(source, target)

    assert evaluation.allowed is False
    assert evaluation.alternative_type == "unknown"
    assert evaluation.confidence == Decimal("0")
    assert evaluation.module5_hints["automaticSelection"] is False


def test_alternatives_service_does_not_import_orm_or_costing_layers() -> None:
    source = Path("app/services/module1_alternatives_analogs.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "__tablename__" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
    assert "calculate_cost" not in source.lower()
    assert "supplierprice" not in source.lower()
