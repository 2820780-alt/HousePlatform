from decimal import Decimal

from app.services.module2_calculation_graph import Threshold, copy_block, evaluate_block
from app.services.module2_calculation_presets import (
    area_consumption_block, counted_prism_volume_block, cylindrical_piles_volume_block, rectangular_volume_block,
    reinforcement_block, slab_net_area_volume_block,
)


def test_volume_preset_requires_dimensions_and_is_independently_mapped():
    template = rectangular_volume_block()
    assert evaluate_block(template, {})[template.material_output_id].errors
    copy = copy_block(template, input_mapping={
        "geometry.length": "slab.length", "geometry.width": "slab.width", "geometry.height": "slab.height",
    }, material_id=None, work_code=None)
    assert set(node.id for node in template.nodes).isdisjoint(node.id for node in copy.nodes)
    original = evaluate_block(template, {"geometry.length": ("10", "m"),
                                         "geometry.width": ("400", "mm"),
                                         "geometry.height": ("1", "m")})
    changed = evaluate_block(copy, {"slab.length": ("6", "m"), "slab.width": ("5", "m"),
                                    "slab.height": ("0.2", "m")})
    assert original[template.material_output_id].value == Decimal("4")
    assert changed[copy.work_output_id].value == Decimal("6")
    assert template.material_output_id == template.work_output_id


def test_area_preset_returns_distinct_material_and_work_quantities():
    block = area_consumption_block()
    values = evaluate_block(block, {"geometry.area": ("12", "m2"),
                                    "technology.thickness": ("10", "mm"),
                                    "material.consumption": ("1.5", "kg_per_m2_mm")})
    assert values[block.material_output_id].value == Decimal("180")
    assert values[block.work_output_id].value == Decimal("12")
    missing = evaluate_block(block, {"geometry.area": ("12", "m2")})
    assert missing[block.material_output_id].errors
    assert missing[block.work_output_id].value == Decimal("12")
    negative = evaluate_block(block, {"geometry.area": ("-1", "m2")})
    assert negative[block.work_output_id].errors


def test_slab_volume_requires_net_area_and_thickness_and_recalculates():
    block = slab_net_area_volume_block()
    assert evaluate_block(block, {})[block.material_output_id].value is None
    inputs = {"geometry.net_area": ("60", "m2"), "technology.slab_thickness": ("0.2", "m")}
    assert evaluate_block(block, inputs)[block.material_output_id].value == Decimal("12")
    assert evaluate_block(block, {**inputs, "geometry.net_area": ("50", "m2")})[block.work_output_id].value == Decimal("10")
    assert evaluate_block(block, {**inputs, "technology.slab_thickness": ("-1", "m")})[block.material_output_id].value is None


def test_counted_prism_requires_integer_count_and_explicit_dimensions():
    block = counted_prism_volume_block()
    values = {"element.length": ("2", "m"), "element.width": ("0.5", "m"),
              "element.height": ("0.4", "m"), "element.count": ("5", "piece")}
    result = evaluate_block(block, values)
    assert result[block.material_output_id].value == Decimal("2")
    assert result[block.work_output_id].value == Decimal("5")
    assert evaluate_block(block, {**values, "element.count": ("2.5", "piece")})[block.material_output_id].value is None
    assert evaluate_block(block, {key: value for key, value in values.items() if key != "element.height"})[block.material_output_id].value is None


def test_cylindrical_piles_use_explicit_geometry_without_engineering_defaults():
    block = cylindrical_piles_volume_block()
    values = {"pile.diameter": ("0.3", "m"), "pile.length": ("3", "m"), "pile.count": ("10", "piece")}
    first = evaluate_block(block, values)
    assert first[block.material_output_id].value.quantize(Decimal("0.000001")) == Decimal("2.120575")
    assert first[block.work_output_id].value == Decimal("10")
    second = evaluate_block(block, {**values, "pile.count": ("5", "piece")})
    assert (second[block.material_output_id].value * 2).quantize(Decimal("0.000000001")) == (
        first[block.material_output_id].value.quantize(Decimal("0.000000001")))
    assert evaluate_block(block, {"pile.count": ("10", "piece")})[block.material_output_id].value is None


def test_reinforcement_preset_uses_explicit_test_ranges_and_laps():
    cases = (Threshold(Decimal("350"), Decimal("500"), Decimal("3")),
             Threshold(Decimal("500"), Decimal("501"), Decimal("4"), True))
    block = reinforcement_block(thresholds=cases, source="QA fixture, not a standard")
    inputs = {"geometry.width": ("350", "mm"), "geometry.length": ("10", "m"),
              "reinforcement.cover": ("40", "mm"), "reinforcement.diameter": ("12", "mm"),
              "reinforcement.min_spacing": ("100", "mm"), "reinforcement.max_spacing": ("200", "mm"),
              "reinforcement.lap_length": ("0.5", "m"), "reinforcement.joints": ("2", "piece"),
              "material.mass_per_m": ("0.888", "kg_per_m")}
    first = evaluate_block(block, inputs)[block.material_output_id]
    assert first.value == Decimal("27.528") and "PRELIMINARY_RULE" in first.warnings
    changed = evaluate_block(block, {**inputs, "geometry.width": ("500", "mm")})[block.material_output_id]
    assert changed.value == Decimal("36.408")
    conflict = evaluate_block(block, {**inputs, "reinforcement.max_spacing": ("100", "mm")})[block.material_output_id]
    assert conflict.value is None and any(error.startswith("RULE_CONFLICT") for error in conflict.errors)
