from decimal import Decimal

from app.services.module2_calculation_graph import Threshold, copy_block, evaluate_block
from app.services.module2_calculation_presets import area_consumption_block, rectangular_volume_block, reinforcement_block


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
