from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_material_normalizer import (
    NormalizedMaterialCandidate,
    build_normalization_report,
    extract_dimensions,
    infer_material_group,
    normalize_characteristics,
    normalize_raw_ingestion_item,
    normalize_title,
)
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem


def _raw(
    title: str,
    *,
    unit: str = "шт",
    category: str | None = None,
    characteristics: dict | None = None,
    price: object = Decimal("100.00"),
) -> Module1RawIngestionItem:
    return Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="BAUCENTER",
        raw_title=title,
        raw_category=category,
        raw_unit=unit,
        raw_price=price,
        raw_characteristics=characteristics or {},
        raw_manufacturer="Test manufacturer",
        source_url="https://example.test/material",
    )


def test_gas_block_normalization_extracts_dimensions_and_density_without_final_material() -> None:
    candidate = normalize_raw_ingestion_item(_raw("Газоблок D500 600x300x200"))

    assert isinstance(candidate, NormalizedMaterialCandidate)
    assert candidate.suggested_group_code == "aerated_concrete_block"
    assert candidate.normalized_characteristics["length_mm"] == Decimal("600")
    assert candidate.normalized_characteristics["width_mm"] == Decimal("300")
    assert candidate.normalized_characteristics["height_mm"] == Decimal("200")
    assert candidate.normalized_characteristics["density_class"] == "D500"
    assert "strength_class" in candidate.missing_required_fields
    assert any("pieces_per_m3" in warning for warning in candidate.warnings)
    assert candidate.normalized_unit == "piece"


def test_gypsum_board_normalization_extracts_moisture_resistant_sheet_profile() -> None:
    candidate = normalize_raw_ingestion_item(_raw("ГКЛВ 2500х1200х12.5", unit="лист"))

    assert candidate.suggested_group_code == "gypsum_board_moisture_resistant"
    assert candidate.normalized_characteristics["length_mm"] == Decimal("2500")
    assert candidate.normalized_characteristics["width_mm"] == Decimal("1200")
    assert candidate.normalized_characteristics["thickness_mm"] == Decimal("12.5")
    assert candidate.normalized_characteristics["board_type"] == "moisture_resistant"
    assert candidate.normalized_unit == "sheet"


def test_rebar_normalization_extracts_diameter_class_and_unit() -> None:
    candidate = normalize_raw_ingestion_item(_raw("Арматура А500С 12 мм", unit="м.п."))

    assert candidate.suggested_group_code == "rebar"
    assert candidate.normalized_characteristics["diameter_mm"] == Decimal("12")
    assert candidate.normalized_characteristics["steel_class"] == "A500C"
    assert candidate.normalized_unit == "linear_meter"
    assert "kg_per_meter" in candidate.module2_missing_fields


def test_ready_mix_concrete_normalization_extracts_classes() -> None:
    candidate = normalize_raw_ingestion_item(_raw("Бетон B25 П4 F200 W6", unit="м3"))

    assert candidate.suggested_group_code == "ready_mix_concrete"
    assert candidate.normalized_characteristics["concrete_class"] == "B25"
    assert candidate.normalized_characteristics["mobility_class"] == "P4"
    assert candidate.normalized_characteristics["frost_resistance"] == "F200"
    assert candidate.normalized_characteristics["water_resistance"] == "W6"
    assert candidate.normalized_characteristics["unit"] == "m3"
    assert candidate.normalized_unit == "m3"


def test_board_normalization_maps_dimensions_as_thickness_width_length() -> None:
    candidate = normalize_raw_ingestion_item(_raw("Доска 25х150х6000"))

    assert candidate.suggested_group_code == "board"
    assert candidate.normalized_characteristics["thickness_mm"] == Decimal("25")
    assert candidate.normalized_characteristics["width_mm"] == Decimal("150")
    assert candidate.normalized_characteristics["length_mm"] == Decimal("6000")
    assert candidate.suggested_category == "lumber"
    assert "volume_per_piece_m3" in candidate.module2_missing_fields


def test_metal_tile_normalization_extracts_thickness_and_coating_without_fastener_consumption() -> None:
    candidate = normalize_raw_ingestion_item(_raw("Металлочерепица 0.5 мм покрытие Satin", unit="м2"))

    assert candidate.suggested_group_code == "metal_tile"
    assert candidate.normalized_characteristics["metal_thickness_mm"] == Decimal("0.5")
    assert candidate.normalized_characteristics["coating"] == "Satin"
    assert "screw_consumption" not in candidate.normalized_characteristics
    assert "screws_per_m2" not in candidate.normalized_characteristics


def test_normalizer_helpers_return_candidate_hints_and_report() -> None:
    raw = _raw("Газоблок D500 600x300x200")

    assert "600x300x200" in normalize_title(raw.raw_title)
    assert extract_dimensions(raw.raw_title)["dimensions_mm"] == (Decimal("600"), Decimal("300"), Decimal("200"))
    assert infer_material_group(raw) == "aerated_concrete_block"
    assert normalize_characteristics("rebar", {}, "Арматура А500С 12 мм")["steel_class"] == "A500C"

    report = build_normalization_report(raw)
    assert report.is_ready_for_matching is False
    assert "strength_class" in report.missing_required_fields
    assert report.candidate.price_hint == Decimal("100.00")



def test_normalization_without_positive_price_is_diagnostic_not_ready() -> None:
    for price in (None, Decimal("0"), Decimal("-1"), "not-a-price"):
        report = build_normalization_report(_raw("Бетон B25 П4 F200 W6", unit="м3", price=price))

        assert report.candidate.suggested_group_code == "ready_mix_concrete"
        assert report.candidate.price_hint == price
        assert report.is_ready_for_matching is False
        assert "missing positive price" in report.warnings


def test_normalization_with_positive_price_remains_ready_for_matching() -> None:
    report = build_normalization_report(_raw("Бетон B25 П4 F200 W6", unit="м3", price=Decimal("4200.50")))

    assert report.is_ready_for_matching is True
    assert "missing positive price" not in report.warnings


def test_confidence_and_source_metadata_are_present() -> None:
    candidate = normalize_raw_ingestion_item(
        _raw(
            "Бетон B25 П4 F200 W6",
            unit="м3",
            characteristics={"application": "foundation"},
        )
    )

    assert candidate.confidence > Decimal("0.70")
    assert candidate.source_metadata["source_code"] == "BAUCENTER"
    assert candidate.evidence["raw_title"] == "Бетон B25 П4 F200 W6"


def test_material_normalizer_does_not_import_orm_or_create_canonical_entities() -> None:
    source = Path("app/services/module1_material_normalizer.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "source_integrations" not in source
    assert "source_task_runner" not in source
    assert "Material(" not in source
    assert "CanonicalMaterial" not in source
    assert "add_alias" not in source
