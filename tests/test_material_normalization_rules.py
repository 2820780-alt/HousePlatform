from decimal import Decimal

from app.services.material_normalization_rules import (
    DIRECTION_RULES,
    detect_direction,
    get_normalization_profile_snapshot,
    normalize_material_title,
    normalize_price,
    normalize_unit,
)


def test_title_normalization_removes_noise_but_preserves_identity_tokens():
    result = normalize_material_title(
        "Акция! Газоблок D500 600х300х200 Bonolit купить доставка",
        brand="Bonolit",
        category="Газобетон",
        unit="шт",
        region="Краснодарский край",
        city="Краснодар",
    )

    assert "акция" not in result.search_title
    assert "купить" not in result.search_title
    assert "доставка" not in result.search_title
    assert "bonolit" not in result.search_title
    assert "газобетонный блок" in result.search_title
    assert "d500" in result.search_title
    assert "600x300x200" in result.search_title
    assert result.direction_code == "WALL_MATERIALS"
    assert result.ignored_candidate_status is None


def test_search_title_keeps_color_coating_size_and_article():
    result = normalize_material_title(
        "Новинка Саморез кровельный RAL 8017 с EPDM 4,8х35 арт. KR-35",
        category="Крепеж",
        unit="шт",
        region="Краснодарский край",
    )

    assert "новинка" not in result.search_title
    assert "саморез с epdm шайбой" in result.search_title
    assert "ral 8017" in result.search_title
    assert "epdm" in result.search_title
    assert "4,8x35" in result.search_title
    assert "арт. kr-35" in result.search_title
    assert result.direction_code == "FASTENERS_HARDWARE"


def test_services_and_tools_are_ignored_candidates():
    result = normalize_material_title(
        "Аренда дрели с доставкой",
        category="Инструмент",
        unit="шт",
        region="Краснодарский край",
    )

    assert result.ignored_candidate_status == "ignored_candidate"
    assert "service_or_delivery_only" in result.ignored_candidate_reasons
    assert "tool_product_not_material" in result.ignored_candidate_reasons


def test_first_wave_direction_rules_are_available():
    assert set(DIRECTION_RULES) == {
        "WALL_MATERIALS",
        "ROOFING_DRAINAGE",
        "LUMBER_SHEET",
        "METAL_ROLLING",
        "DRY_MIXES_CHEMISTRY",
        "INSULATION_MEMBRANES",
        "ELECTRICAL_LIGHTING",
        "FASTENERS_HARDWARE",
        "ENGINEERING_PLUMBING_HVAC",
    }
    for rule in DIRECTION_RULES.values():
        assert rule.key_characteristics
        assert rule.required_fields
        assert rule.units
        assert rule.synonyms
        assert rule.auto_checks
        assert rule.needs_review_conditions
        assert rule.ignored_candidate_conditions


def test_unit_price_and_direction_helpers():
    assert normalize_unit("м2") == "м²"
    assert normalize_unit("пог.м") == "пог. м"
    assert normalize_unit("уп") == "упаковка"
    assert normalize_price("1 250,75 руб") == Decimal("1250.75")
    assert detect_direction("Кабель ВВГнг 3х2,5") == "ELECTRICAL_LIGHTING"


def test_normalization_profile_snapshot_explains_pipeline_boundary():
    snapshot = get_normalization_profile_snapshot()

    assert snapshot["version"] == "MODULE_01_NORMALIZATION_RULES_V1"
    assert "do not create ACTIVE Material" in snapshot["pipeline_boundary"]
    assert "size" in snapshot["search_title_preserves"]
    assert len(snapshot["direction_rules"]) == 9
