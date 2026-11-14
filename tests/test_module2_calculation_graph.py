from dataclasses import replace
from decimal import Decimal

import pytest

from app.services.module2_calculation_graph import (
    BlockParameter,
    CalculationBlock,
    CalculationNode,
    Threshold,
    copy_block,
    evaluate_block,
    validate_block,
)


def concrete_block():
    return CalculationBlock("block-1", "Concrete", (
        CalculationNode("length", "INPUT", "m", input_key="strip.length"),
        CalculationNode("width", "INPUT", "mm", input_key="strip.width"),
        CalculationNode("height", "INPUT", "m", input_key="strip.height"),
        CalculationNode("volume", "PRISM_VOLUME", "m3", inputs=("length", "width", "height")),
    ), ("volume",), material_id="material-1", work_code="work-1")


def test_prism_calculation_converts_units_and_recalculates_geometry():
    block = concrete_block()
    inputs = {"strip.length": ("10", "m"), "strip.width": ("400", "mm"), "strip.height": ("0.6", "m")}
    assert evaluate_block(block, inputs)["volume"].value == Decimal("2.4")
    assert evaluate_block(block, {**inputs, "strip.width": ("500", "mm")})["volume"].value == Decimal("3")


def test_missing_input_blocks_only_its_dependent_branch():
    block = CalculationBlock("1", "partial", (
        CalculationNode("missing", "INPUT", "m", input_key="missing"),
        CalculationNode("fixed", "CONSTANT", "m", constant=Decimal("2")),
        CalculationNode("total", "ADD", "m", inputs=("missing", "fixed")),
    ), ("total", "fixed"))
    result = evaluate_block(block, {})
    assert result["total"].value is None
    assert result["total"].errors == ("MISSING_INPUT:missing",)
    assert result["fixed"].value == Decimal("2")


def test_threshold_fixture_has_explicit_domain_and_discrete_result():
    block = CalculationBlock("1", "fixture only", (
        CalculationNode("width", "INPUT", "mm", input_key="width"),
        CalculationNode("bars", "PIECEWISE", "piece", inputs=("width",), thresholds=(
            Threshold(Decimal("350"), Decimal("500"), Decimal("3")),
            Threshold(Decimal("500"), Decimal("500"), Decimal("4"), upper_inclusive=True),
        )),
    ), ("bars",))
    for width, expected in ((350, 3), (400, 3), (450, 3), (500, 4)):
        assert evaluate_block(block, {"width": (str(width), "mm")})["bars"].value == expected
    outside = evaluate_block(block, {"width": ("501", "mm")})["bars"]
    assert outside.value is None and outside.errors == ("OUT_OF_DOMAIN",)


def test_overlapping_thresholds_are_rejected():
    block = CalculationBlock("1", "bad", (
        CalculationNode("width", "INPUT", "mm", input_key="width"),
        CalculationNode("bars", "PIECEWISE", "piece", inputs=("width",), thresholds=(
            Threshold(Decimal("0"), Decimal("500"), Decimal("3"), True),
            Threshold(Decimal("500"), Decimal("600"), Decimal("4")),
        )),
    ), ("bars",))
    with pytest.raises(ValueError, match="overlap"):
        validate_block(block)


@pytest.mark.parametrize("node", [
    CalculationNode("volume", "EVAL", "m3", inputs=("length", "width", "height")),
    CalculationNode("volume", "ADD", "m3", inputs=("length", "width")),
    CalculationNode("volume", "PRISM_VOLUME", "m3", inputs=("volume", "width", "height")),
])
def test_unsafe_operations_wrong_dimensions_and_cycles_are_rejected(node):
    block = concrete_block()
    block = replace(block, nodes=(*block.nodes[:3], node))
    with pytest.raises(ValueError):
        validate_block(block)


def test_template_copy_remaps_ids_and_requires_explicit_input_mapping():
    original = replace(concrete_block(), material_output_id="volume", work_output_id="volume")
    with pytest.raises(ValueError, match="explicitly mapped"):
        copy_block(original, input_mapping={"strip.length": "slab.length"})
    mapping = {"strip.length": "slab.length", "strip.width": "slab.width", "strip.height": "slab.height"}
    slab = copy_block(original, input_mapping=mapping, material_id="material-2", work_code="work-2")
    assert slab.id != original.id
    assert {node.id for node in slab.nodes}.isdisjoint({node.id for node in original.nodes})
    assert slab.material_id == "material-2" and original.material_id == "material-1"
    assert slab.material_output_id == slab.work_output_id == slab.outputs[0]
    assert slab.material_output_id != original.material_output_id
    result = evaluate_block(slab, {"slab.length": ("4", "m"), "slab.width": ("3000", "mm"),
                                   "slab.height": ("0.2", "m")})
    assert result[slab.outputs[0]].value == Decimal("2.4")
    assert original.nodes[1].input_key == "strip.width"


def test_missing_confirmed_geometry_does_not_default_to_zero():
    result = evaluate_block(concrete_block(), {})
    assert result["volume"].value is None
    assert set(result["volume"].errors) == {
        "MISSING_INPUT:strip.length", "MISSING_INPUT:strip.width", "MISSING_INPUT:strip.height",
    }


def test_decimal_float_and_incompatible_input_units_are_rejected_locally():
    inputs = {"strip.length": (1.5, "m"), "strip.width": ("400", "mm"), "strip.height": ("3", "kg")}
    result = evaluate_block(concrete_block(), inputs)
    assert result["volume"].value is None
    assert set(result["volume"].errors) == {"INVALID_INPUT:length", "INVALID_INPUT:height"}


def test_conditional_does_not_require_inputs_from_the_unselected_branch():
    block = CalculationBlock("1", "conditional", (
        CalculationNode("choice", "INPUT", "1", input_key="include"),
        CalculationNode("selected", "CONSTANT", "m2", constant=Decimal("10")),
        CalculationNode("unselected", "INPUT", "m2", input_key="other_area"),
        CalculationNode("result", "IF", "m2", inputs=("choice", "selected", "unselected")),
    ), ("result",))
    assert evaluate_block(block, {"include": ("1", "1")})["result"].value == Decimal("10")
    missing = evaluate_block(block, {"include": ("0", "1")})["result"]
    assert missing.value is None and missing.errors == ("MISSING_INPUT:other_area",)


def test_preliminary_defaults_require_explicit_preview_and_are_traced():
    original = concrete_block()
    block = replace(original, parameters=(BlockParameter(
        "strip.width", "Width", "mm", default=Decimal("400"), minimum=Decimal("300"),
        maximum=Decimal("500"), source="test fixture", status="PRELIMINARY", auto_apply=True,
    ),))
    inputs = {"strip.length": ("10", "m"), "strip.height": ("0.6", "m")}
    assert evaluate_block(block, inputs)["volume"].value is None
    preview = evaluate_block(block, inputs, allow_preliminary_defaults=True)["volume"]
    assert preview.value == Decimal("2.4")
    assert preview.warnings == ("PRELIMINARY_DEFAULT:strip.width",)
    explicit = evaluate_block(block, {**inputs, "strip.width": ("0.5", "m")})["volume"]
    assert explicit.value == Decimal("3") and not explicit.warnings
    invalid = evaluate_block(block, {**inputs, "strip.width": ("0.6", "m")})["volume"]
    assert invalid.value is None and "INVALID_INPUT:width" in invalid.errors


def test_template_copy_keeps_default_values_but_remaps_parameter_identity():
    original = replace(concrete_block(), parameters=(BlockParameter(
        "strip.width", "Width", "mm", default=Decimal("400"), source="fixture", status="PRELIMINARY",
        auto_apply=True,
    ),))
    mapping = {"strip.length": "slab.length", "strip.width": "slab.width", "strip.height": "slab.height"}
    copy = copy_block(original, input_mapping=mapping)
    assert original.parameters[0].input_key == "strip.width"
    assert copy.parameters[0].input_key == "slab.width"
    assert copy.parameters[0].default == Decimal("400")


def test_bar_layout_uses_explicit_edges_spacing_and_project_additions():
    block = CalculationBlock("reinforcement", "Test fixture", (
        CalculationNode("width", "INPUT", "mm", input_key="width"),
        CalculationNode("cover", "INPUT", "mm", input_key="cover"),
        CalculationNode("diameter", "INPUT", "mm", input_key="diameter"),
        CalculationNode("min", "INPUT", "mm", input_key="min_spacing"),
        CalculationNode("max", "INPUT", "mm", input_key="max_spacing"),
        CalculationNode("length", "INPUT", "m", input_key="bar_length"),
        CalculationNode("extra", "INPUT", "m", input_key="explicit_extra_length"),
        CalculationNode("density", "INPUT", "kg_per_m", input_key="mass_per_m"),
        CalculationNode("bars", "PIECEWISE", "piece", inputs=("width",), thresholds=(
            Threshold(Decimal("350"), Decimal("500"), Decimal("3")),
            Threshold(Decimal("500"), Decimal("500"), Decimal("4"), True),
        )),
        CalculationNode("spacing", "BAR_SPACING", "mm", inputs=("width", "cover", "diameter", "bars", "min", "max")),
        CalculationNode("straight", "MULTIPLY", "m", inputs=("bars", "length")),
        CalculationNode("total", "ADD", "m", inputs=("straight", "extra")),
        CalculationNode("unverified_mass", "MULTIPLY", "kg", inputs=("total", "density")),
        CalculationNode("mass", "REQUIRE_VALID", "kg", inputs=("unverified_mass", "spacing")),
    ), ("bars", "spacing", "mass"))
    common = {"cover": ("40", "mm"), "diameter": ("12", "mm"), "min_spacing": ("100", "mm"),
              "max_spacing": ("200", "mm"), "bar_length": ("10", "m"),
              "explicit_extra_length": ("0", "m"), "mass_per_m": ("0.888", "kg_per_m")}
    for width, count, spacing, mass in (("350", "3", "129", "26.64"), ("400", "3", "154", "26.64"),
                                         ("450", "3", "179", "26.64"), ("500", "4", "136", "35.52")):
        result = evaluate_block(block, {**common, "width": (width, "mm")})
        assert result["bars"].value == Decimal(count)
        assert result["spacing"].value == Decimal(spacing)
        assert result["mass"].value == Decimal(mass)
    conflict = evaluate_block(block, {**common, "width": ("400", "mm"), "max_spacing": ("130", "mm")})
    assert conflict["mass"].value is None and conflict["mass"].errors == ("RULE_CONFLICT:spacing",)
    missing = evaluate_block(block, {key: value for key, value in {**common, "width": ("400", "mm")}.items()
                                     if key != "explicit_extra_length"})
    assert missing["mass"].value is None and "MISSING_INPUT:explicit_extra_length" in missing["mass"].errors
