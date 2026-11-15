from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.module1_calculation_price import CalculationPrice, CalculationPriceContext, PriceCandidate, calculate_price
from app.services.module2_calculation_graph import CalculationBlock, CalculationNode
from app.services.module5_calculation_preview import (
    StatementBinding, ambiguous_foundation_work_codes, calculate_statement_preview,
)


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


def test_explicit_zero_quantity_does_not_require_a_price_but_missing_quantity_does():
    item = CalculationBlock("optional", "Вариант", (
        CalculationNode("count", "INPUT", "piece", input_key="selected.count"),), ("count",))
    binding = StatementBinding("optional-line", "optional", "MATERIAL", "material-id", "count", "optional")
    unused = calculate_statement_preview((item,), (binding,), {"selected.count": ("0", "piece")}, {})
    assert not unused.complete and unused.materials[0].quantity == 0
    assert unused.materials[0].unit_price is None and unused.materials[0].line_amount == Decimal("0.00")
    assert "NO_PRICE" not in unused.materials[0].issues
    active = bindings()[0]
    combined = calculate_statement_preview(
        (item, block()), (replace(binding, resource_id="optional-id"), active),
        {"selected.count": ("0", "piece"), "length": ("10", "m"),
         "width": ("0.4", "m"), "height": ("0.6", "m")},
        {("MATERIAL", "material-id"): quote([1000])},
    )
    assert combined.complete and combined.materials[0].unit_price is None
    assert combined.known_total == Decimal("2400.00")
    missing = calculate_statement_preview((item,), (binding,), {}, {})
    assert not missing.complete and missing.materials[0].quantity is None
    assert "NO_PRICE" in missing.materials[0].issues
    used = calculate_statement_preview((item,), (binding,), {"selected.count": ("1", "piece")}, {})
    assert not used.complete and used.materials[0].unit_price is None and "NO_PRICE" in used.materials[0].issues
    unresolved = calculate_statement_preview((item,), (replace(binding, resource_id=None),),
                                            {"selected.count": ("0", "piece")}, {})
    assert not unresolved.complete and "MATERIAL_UNRESOLVED" in unresolved.materials[0].issues


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


@pytest.mark.parametrize("technology,bundle", [
    ("FND_PILE_GRILLAGE", "foundations_concrete_ustroystvo_svayno_rostverkovogo_fundamenta"),
    ("FND_SUBSTRUCTURE_INSULATION_XPS", "foundations_concrete_uteplenie_fundamenta"),
    ("FND_SUBSTRUCTURE_WATERPROOFING_COATING", "foundations_concrete_gidroizolyaciya_fundamenta"),
    ("FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE", "foundations_concrete_gidroizolyaciya_fundamenta"),
])
def test_unresolved_bundle_and_detailed_work_never_both_enter_total(technology, bundle):
    material, work = bindings()
    bundled = replace(work, id="bundle", resource_id=bundle, accounting_key="bundle")
    detailed = replace(work, id="detailed", accounting_key="detailed")
    lines = (material, bundled, detailed)
    conflicts = ambiguous_foundation_work_codes(technology, lines)
    assert conflicts == {bundle, "work-code"}
    geometry = {"length": ("10", "m"), "width": ("0.4", "m"), "height": ("0.6", "m")}
    prices = {("MATERIAL", "material-id"): quote([8000]), ("WORK", bundle): quote([1000]),
              ("WORK", "work-code"): quote([1000])}
    result = calculate_statement_preview((block(),), lines, geometry, prices, ambiguous_work_codes=conflicts)
    assert result.material_subtotal == Decimal("19200") and result.work_subtotal == 0
    assert not result.complete
    assert all("POTENTIAL_DOUBLE_COUNT" in item.issues for item in result.works)
    assert not ambiguous_foundation_work_codes(technology, (material, bundled))
    assert ambiguous_foundation_work_codes(technology, (work, replace(work, resource_id="other"))) == {
        "work-code", "other"}
    assert not ambiguous_foundation_work_codes("FND_SLAB_MONOLITHIC_RC", lines)


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
