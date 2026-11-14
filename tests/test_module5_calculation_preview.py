from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.module1_calculation_price import CalculationPrice, CalculationPriceContext, PriceCandidate, calculate_price
from app.services.module2_calculation_graph import CalculationBlock, CalculationNode
from app.services.module5_calculation_preview import StatementBinding, calculate_statement_preview


def block():
    return CalculationBlock("concrete", "Бетон", (
        CalculationNode("length", "INPUT", "m", input_key="length"),
        CalculationNode("width", "INPUT", "m", input_key="width"),
        CalculationNode("height", "INPUT", "m", input_key="height"),
        CalculationNode("volume", "PRISM_VOLUME", "m3", inputs=("length", "width", "height")),
    ), ("volume",))


def quote(values):
    context = CalculationPriceContext("m3", "RUB", "Краснодарский край", "без доставки", date(2026, 11, 13))
    offers = [PriceCandidate(str(i), Decimal(str(value)), "m3", "RUB", "Краснодарский край", "без доставки",
                             "active", True) for i, value in enumerate(values)]
    return calculate_price(context, offers)


def bindings():
    return (
        StatementBinding("material-line", "concrete", "MATERIAL", "material-id", "volume", "strip-concrete-material"),
        StatementBinding("work-line", "concrete", "WORK", "work-code", "volume", "strip-concrete-work"),
    )


def test_separate_material_and_work_lines_recalculate_on_geometry_change():
    prices = {("MATERIAL", "material-id"): quote([7500, 8500]), ("WORK", "work-code"): quote([1000, 1200])}
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    first = calculate_statement_preview((block(),), bindings(), geometry, prices)
    assert first.complete and first.materials[0].quantity == first.works[0].quantity == Decimal("2.4")
    assert (first.material_subtotal, first.work_subtotal, first.known_total) == (
        Decimal("19200.00"), Decimal("2640.00"), Decimal("21840.00"))
    second = calculate_statement_preview((block(),), bindings(), {**geometry, "width": ("0.5", "m")}, prices)
    assert second.materials[0].quantity == second.works[0].quantity == Decimal("3")
    assert second.known_total == Decimal("27300.00")
    assert first.materials[0].trace[-1][1].value == Decimal("2.4")


def test_missing_price_is_null_and_zero_only_for_subtotal():
    prices = {("MATERIAL", "material-id"): quote([]), ("WORK", "work-code"): quote([1000])}
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    result = calculate_statement_preview((block(),), bindings(), geometry, prices)
    assert not result.complete and result.materials[0].unit_price is None
    assert result.materials[0].line_amount is None and result.materials[0].amount_for_total == 0
    assert "NO_PRICE" in result.materials[0].issues and result.works[0].line_amount == Decimal("2400")


def test_unresolved_material_does_not_stop_independent_work():
    material, work = bindings()
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    result = calculate_statement_preview((block(),), (replace(material, resource_id=None), work), geometry,
                                         {("WORK", "work-code"): quote([1000])})
    assert result.materials[0].issues == ("MATERIAL_UNRESOLVED",)
    assert result.works[0].line_amount == Decimal("2400")


def test_incomplete_geometry_cannot_be_mistaken_for_zero_quantity():
    result = calculate_statement_preview((block(),), bindings(), {}, {})
    assert result.materials[0].quantity is None and result.materials[0].line_amount is None
    assert any(item.startswith("MISSING_INPUT:") for item in result.materials[0].issues)
    assert not result.complete


def test_duplicate_accounting_key_cannot_double_count_same_role():
    material, work = bindings()
    with pytest.raises(ValueError, match="duplicate accounting key"):
        calculate_statement_preview((block(),), (material, replace(material, id="duplicate"), work), {}, {})


def test_same_resource_under_different_keys_is_not_silently_counted_twice():
    material, work = bindings()
    another = replace(material, id="other", accounting_key="another-role")
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    prices = {("MATERIAL", "material-id"): quote([8000]), ("WORK", "work-code"): quote([1000])}
    result = calculate_statement_preview((block(),), (material, another, work), geometry, prices)
    assert not result.complete
    assert all("POTENTIAL_DOUBLE_COUNT" in line.issues for line in result.materials)
    assert all(line.line_amount == Decimal("19200") for line in result.materials)
    assert result.material_subtotal == 0
    assert result.work_subtotal == result.known_total == Decimal("2400")


def test_invalid_technology_role_excludes_affected_block_from_subtotals():
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    prices = {("MATERIAL", "material-id"): quote([8000]), ("WORK", "work-code"): quote([1000])}
    result = calculate_statement_preview((block(),), bindings(), geometry, prices,
                                         block_issues={"concrete": ("TECHNOLOGY_ROLE_INVALID",)})
    assert not result.complete and result.known_total == 0
    assert all("TECHNOLOGY_ROLE_INVALID" in line.issues for line in (*result.materials, *result.works))


def test_invalid_quote_does_not_become_a_negative_cost():
    material, work = bindings()
    bad = CalculationPrice(Decimal("-1"), "MANUAL", quote([]).context)
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    result = calculate_statement_preview((block(),), (material, work), geometry,
                                         {("MATERIAL", "material-id"): bad, ("WORK", "work-code"): quote([1000])})
    assert result.materials[0].unit_price is None
    assert result.materials[0].issues == ("INVALID_PRICE",)
    assert result.works[0].line_amount == Decimal("2400")
