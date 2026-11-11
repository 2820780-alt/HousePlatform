from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.module1_material_ui_prices import comparable_rule_price, comparable_unit_price


def test_tonnes_to_kilograms():
    assert comparable_unit_price("58000", "т", "кг") == Decimal("58")


def test_piece_abbreviation_with_dot():
    assert comparable_unit_price("258", "шт.", "piece") == Decimal("258")


def test_block_volume_to_piece_uses_existing_registry():
    price = comparable_unit_price(
        "4300", "m3", "piece", material_group="aerated_concrete_block",
        material_profile={"length_mm": 600, "height_mm": 250, "width_mm": 400},
    )
    assert price is not None and abs(price - Decimal("258")) < Decimal("0.000000000001")


def test_rebar_metres_to_kg_uses_known_mass():
    price = comparable_unit_price(
        "88.8", "m", "kg", material_group="rebar", material_profile={"kg_per_meter": "0.888"},
    )
    assert price == Decimal("100")


def test_rebar_diameter_alone_does_not_substitute_for_known_mass():
    assert comparable_unit_price("88.8", "m", "kg", material_group="rebar",
                                 material_profile={"diameter_mm": 12}) is None


def test_rebar_meter_alias_does_not_require_a_weight():
    assert comparable_unit_price("88.8", "m", "linear_meter", material_group="rebar") == Decimal("88.8")


def test_invalid_geometry_cannot_produce_a_price():
    assert comparable_unit_price("4300", "m3", "piece", material_group="aerated_concrete_block",
                                 material_profile={"length_mm": -600, "height_mm": -250, "width_mm": 400}) is None


def test_only_unambiguous_active_sourced_rule_can_convert_packaging():
    rule = SimpleNamespace(status="ACTIVE", formula_type="LINEAR_COEFFICIENT", source="Паспорт товара",
                           from_unit="pallet", to_unit="piece", coefficient=Decimal("40"))
    assert comparable_rule_price("8000", "pallet", "piece", [rule]) == Decimal("200")
    pending = SimpleNamespace(**{**vars(rule), "status": "NEEDS_REVIEW"})
    assert comparable_rule_price("8000", "pallet", "piece", [pending]) is None
    conflicting = SimpleNamespace(**{**vars(rule), "coefficient": Decimal("50")})
    assert comparable_rule_price("8000", "pallet", "piece", [rule, conflicting]) is None


@pytest.mark.parametrize("price,sale,base,currency", [
    ("8300", "pallet", "piece", "RUB"),
    ("0", "kg", "kg", "RUB"),
    ("-1", "kg", "kg", "RUB"),
    ("NaN", "kg", "kg", "RUB"),
    ("10", None, "kg", "RUB"),
    ("10", "kg", "kg", "USD"),
])
def test_noncomparable_offer_is_not_priced(price, sale, base, currency):
    assert comparable_unit_price(price, sale, base, currency=currency) is None
