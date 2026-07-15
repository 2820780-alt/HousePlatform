from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.services.module1_matching_dedup import (
    MaterialMatchCandidateDTO,
    build_dedup_report,
    build_match_candidate,
    classify_match_confidence,
    compare_characteristics,
    compare_dimensions,
    detect_duplicate_candidates,
    score_material_match,
)
from app.services.module1_material_normalizer import NormalizedMaterialCandidate


def _candidate(
    title: str,
    *,
    group_code: str,
    characteristics: dict,
    unit: str = "piece",
    manufacturer: str | None = None,
    brand: str | None = None,
    confidence: str = "0.95",
    missing_required_fields: tuple[str, ...] = (),
    price_hint: object = Decimal("100.00"),
) -> NormalizedMaterialCandidate:
    return NormalizedMaterialCandidate(
        normalized_title=title,
        source_title=title,
        suggested_group_code=group_code,
        suggested_category=None,
        manufacturer=manufacturer,
        brand=brand,
        normalized_characteristics=characteristics,
        normalized_unit=unit,
        price_hint=price_hint,
        source_metadata={
            "source_code": "TEST_SOURCE",
            "source_type": "supplier_site",
            "source_url": "https://example.test/item",
        },
        confidence=Decimal(confidence),
        warnings=(),
        missing_required_fields=missing_required_fields,
        module2_missing_fields=(),
        evidence={
            "raw_title": title,
            "raw_category": group_code,
            "raw_documents": (),
            "raw_images": (),
        },
    )


def test_gas_block_exact_match_candidate_is_explained_without_auto_merge() -> None:
    candidate = _candidate(
        "Газоблок D500 600x300x200",
        group_code="aerated_concrete_block",
        characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
    )
    existing = {
        "id": "mat-gas-001",
        "canonical_name": "Газобетонный блок D500 600×300×200",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        "unit": "piece",
    }

    match = build_match_candidate(candidate, [existing])

    assert isinstance(match, MaterialMatchCandidateDTO)
    assert match.decision_hint in {"exact_match", "strong_match"}
    assert match.confidence >= Decimal("90")
    assert match.matched_material_reference == {
        "id": "mat-gas-001",
        "title": "Газобетонный блок D500 600×300×200",
        "group_code": "aerated_concrete_block",
    }
    assert match.conflicting_fields == ()
    assert any("No automatic merge" in item for item in match.explanation)
    assert match.source_refs["source_code"] == "TEST_SOURCE"
    assert match.evidence_refs["raw_title"] == "Газоблок D500 600x300x200"


def test_gas_block_with_different_height_is_possible_duplicate_not_exact() -> None:
    candidate = _candidate(
        "Газоблок D500 600x300x200",
        group_code="aerated_concrete_block",
        characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
    )
    existing = {
        "id": "mat-gas-002",
        "canonical_name": "Газобетонный блок D500 600×300×300",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": {
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("300"),
            "density_class": "D500",
        },
        "unit": "piece",
    }

    match = build_match_candidate(candidate, [existing])

    assert match.decision_hint == "possible_duplicate"
    assert "height_mm" in match.conflicting_fields
    assert match.confidence < Decimal("90")


def test_rebar_class_and_diameter_build_strong_or_moderation_candidate() -> None:
    candidate = _candidate(
        "Арматура А500С 12 мм",
        group_code="rebar",
        characteristics={"diameter_mm": Decimal("12"), "steel_class": "A500C"},
        unit="linear_meter",
    )
    existing = {
        "id": "mat-rebar-012",
        "canonical_name": "Арматура А500 Ø12",
        "group_code": "rebar",
        "normalized_characteristics": {"diameter_mm": Decimal("12"), "steel_class": "А500С"},
        "unit": "linear_meter",
    }

    match = build_match_candidate(candidate, [existing])

    assert match.decision_hint in {"strong_match", "needs_moderation", "exact_match"}
    assert match.confidence >= Decimal("70")
    assert match.conflicting_fields == ()


def test_concrete_partial_fields_match_but_missing_fields_are_reported() -> None:
    candidate = _candidate(
        "Бетон B25 П4 F200 W6",
        group_code="ready_mix_concrete",
        characteristics={
            "concrete_class": "B25",
            "mobility_class": "P4",
            "frost_resistance": "F200",
            "water_resistance": "W6",
        },
        unit="m3",
    )
    existing = {
        "id": "mat-concrete-b25",
        "canonical_name": "Бетон В25 П4",
        "group_code": "ready_mix_concrete",
        "normalized_characteristics": {
            "concrete_class": "В25",
            "mobility_class": "П4",
        },
        "unit": "m3",
    }

    score = score_material_match(candidate, existing)
    match = build_match_candidate(candidate, [existing])

    assert score.score >= Decimal("70")
    assert match.decision_hint in {"needs_moderation", "strong_match"}
    assert "frost_resistance" in match.missing_fields
    assert "water_resistance" in match.missing_fields
    assert match.conflicting_fields == ()


def test_board_dimensions_match_strongly() -> None:
    candidate = _candidate(
        "Доска 25х150х6000",
        group_code="board",
        characteristics={
            "thickness_mm": Decimal("25"),
            "width_mm": Decimal("150"),
            "length_mm": Decimal("6000"),
            "wood_type": "edged",
        },
    )
    existing = {
        "id": "mat-board-25-150-6000",
        "canonical_name": "Доска обрезная 25×150×6000",
        "group_code": "board",
        "normalized_characteristics": {
            "thickness_mm": Decimal("25"),
            "width_mm": Decimal("150"),
            "length_mm": Decimal("6000"),
            "wood_type": "edged",
        },
        "unit": "piece",
    }

    match = build_match_candidate(candidate, [existing])

    assert match.decision_hint in {"exact_match", "strong_match"}
    assert match.confidence >= Decimal("90")
    assert match.conflicting_fields == ()


def test_metal_tile_matches_same_profile_and_flags_conflicting_coating() -> None:
    candidate = _candidate(
        "Металлочерепица Classic 0.5 мм покрытие Satin",
        group_code="metal_tile",
        characteristics={
            "profile_name": "Classic",
            "metal_thickness_mm": Decimal("0.5"),
            "coating": "Satin",
        },
        unit="m2",
        brand="Grand Line",
    )
    exact = {
        "id": "mat-metal-tile-01",
        "canonical_name": "Металлочерепица Classic 0.5 мм Satin",
        "group_code": "metal_tile",
        "normalized_characteristics": {
            "profile_name": "Classic",
            "metal_thickness_mm": Decimal("0.5"),
            "coating": "Satin",
        },
        "unit": "m2",
        "brand": "Grand Line",
    }
    conflict = {
        "id": "mat-metal-tile-02",
        "canonical_name": "Металлочерепица Classic 0.45 мм Polyester",
        "group_code": "metal_tile",
        "normalized_characteristics": {
            "profile_name": "Classic",
            "metal_thickness_mm": Decimal("0.45"),
            "coating": "Polyester",
        },
        "unit": "m2",
        "brand": "Grand Line",
    }

    exact_match = build_match_candidate(candidate, [exact])
    conflict_match = build_match_candidate(candidate, [conflict])

    assert exact_match.decision_hint in {"exact_match", "strong_match"}
    assert exact_match.conflicting_fields == ()
    assert conflict_match.decision_hint == "possible_duplicate"
    assert "metal_thickness_mm" in conflict_match.conflicting_fields
    assert "coating" in conflict_match.conflicting_fields



def test_no_price_candidate_without_existing_material_is_not_new_material_decision() -> None:
    candidate = _candidate(
        "Газоблок D500 600x300x200",
        group_code="aerated_concrete_block",
        characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        price_hint=None,
    )

    match = build_match_candidate(candidate, [])

    assert match.decision_hint == "price_required_review"
    assert match.decision_hint != "new_material_candidate"
    assert match.matched_material_reference is None


def test_no_price_candidate_can_still_match_existing_material_for_enrichment() -> None:
    candidate = _candidate(
        "Газоблок D500 600x300x200",
        group_code="aerated_concrete_block",
        characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
        price_hint=None,
    )
    existing = {
        "id": "mat-gas-001",
        "canonical_name": "Газоблок D500 600x300x200",
        "group_code": "aerated_concrete_block",
        "normalized_characteristics": candidate.normalized_characteristics,
        "unit": "piece",
    }

    match = build_match_candidate(candidate, [existing])

    assert match.matched_material_reference is not None
    assert match.matched_material_reference["id"] == "mat-gas-001"
    assert match.matched_material_reference["title"] == "Газоблок D500 600x300x200"
    assert match.decision_hint in {"exact_match", "strong_match"}

def test_dedup_report_detects_candidates_and_never_auto_applies() -> None:
    left = _candidate(
        "Газоблок D500 600x300x200",
        group_code="aerated_concrete_block",
        characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
    )
    right = _candidate(
        "Газобетонный блок D500 600×300×200",
        group_code="aerated_concrete_block",
        characteristics={
            "length_mm": Decimal("600"),
            "width_mm": Decimal("300"),
            "height_mm": Decimal("200"),
            "density_class": "D500",
        },
    )
    unrelated = _candidate(
        "Бетон B25 П4",
        group_code="ready_mix_concrete",
        characteristics={"concrete_class": "B25", "mobility_class": "P4"},
        unit="m3",
    )

    duplicates = detect_duplicate_candidates([left, right, unrelated])
    report = build_dedup_report([left, right, unrelated])

    assert len(duplicates) == 1
    assert duplicates[0].decision_hint in {"exact_match", "strong_match"}
    assert report.checked_candidates == 3
    assert report.summary["duplicate_count"] == 1
    assert report.summary["auto_merge_allowed"] is False


def test_comparison_helpers_and_thresholds_are_stable() -> None:
    assert classify_match_confidence(Decimal("95")) == "exact_match"
    assert classify_match_confidence(Decimal("90")) == "strong_match"
    assert classify_match_confidence(Decimal("70")) == "needs_moderation"
    assert classify_match_confidence(Decimal("69.99")) == "new_material_candidate"

    characteristics = compare_characteristics({"steel_class": "A500C"}, {"steel_class": "А500С"})
    dimensions = compare_dimensions({"diameter_mm": Decimal("12")}, {"diameter_mm": 12})

    assert characteristics.score == Decimal("1.00")
    assert dimensions.score == Decimal("1.00")


def test_matching_dedup_service_does_not_import_orm_or_mutate_business_entities() -> None:
    source = Path("app/services/module1_matching_dedup.py").read_text(encoding="utf-8")

    assert "app.models" not in source
    assert "source_task_runner" not in source
    assert "Material(" not in source
    assert "CanonicalMaterial" not in source
    assert "add_alias" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
