"""Explicit preliminary quantity rules, not a structural-design or pricing engine.

The estimation export remains an input contract: these helpers do not mutate or
publish technologies and never infer missing geometry, reinforcement or prices.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from typing import Any, Mapping


PI = Decimal("3.141592653589793238462643383279503")


@dataclass(frozen=True)
class QuantityRule:
    code: str
    expression: str
    inputs: tuple[tuple[str, str], ...]
    result_unit: str
    limitation: str
    version: int = 1


@dataclass(frozen=True)
class QuantityResult:
    rule_code: str
    value: Decimal | None
    unit: str
    missing_inputs: tuple[str, ...] = ()


RULES = {
    rule.code: rule for rule in (
        QuantityRule("PRISM_VOLUME", "length_m * width_m * height_m",
                     (("length_m", "m"), ("width_m", "m"), ("height_m", "m")), "m3",
                     "One non-overlapping prism; intersections require a separate union calculation."),
        QuantityRule("BOX_UNION_VOLUME", "volume(union(axis_aligned_boxes))",
                     (("boxes", "m"),), "m3",
                     "Exact union of axis-aligned rectangular volumes only; openings and other shapes require separate geometry."),
        QuantityRule("BOX_VOLUME_EXCLUDING_OCCUPIED", "volume(union(boxes, occupied_boxes)) - volume(union(occupied_boxes))",
                     (("boxes", "m"), ("occupied_boxes", "m")), "m3",
                     "Only axis-aligned rectangular volumes; occupied geometry must be explicitly supplied."),
        QuantityRule("NET_AREA", "gross_area_m2 - openings_area_m2",
                     (("gross_area_m2", "m2"), ("openings_area_m2", "m2")), "m2",
                     "The supplied area must already exclude overlaps with other elements; waste is not inferred."),
        QuantityRule("NET_AREA_VOLUME", "(gross_area_m2 - openings_area_m2) * thickness_m",
                     (("gross_area_m2", "m2"), ("openings_area_m2", "m2"), ("thickness_m", "m")), "m3",
                     "The supplied area must already exclude overlaps with other elements."),
        QuantityRule("CYLINDER_VOLUME", "pi * diameter_m^2 * length_m / 4",
                     (("diameter_m", "m"), ("length_m", "m")), "m3",
                     "One cylindrical pile; enlargement and ordered concrete are separate."),
        QuantityRule("SPACED_ELEMENT_COUNT", "ceil(axis_distance_m / max_spacing_m) + 1",
                     (("axis_distance_m", "m"), ("max_spacing_m", "m")), "piece",
                     "Both extreme axes are specified and occupied; intersecting zones are separate."),
        QuantityRule("SPACED_ZONES_COUNT", "sum(zone_counts) - shared_boundary_count",
                     (("zones", "m"),), "piece",
                     "One ordered axis; endpoints are occupied, and only explicitly shared boundary elements count once."),
        QuantityRule("BAR_TOTAL_LENGTH", "sum(bar_lengths_m)",
                     (("bar_lengths_m", "m"),), "m",
                     "Only specified lengths are counted; overlaps, bends and waste are not inferred."),
        QuantityRule("LAP_ALLOWANCE_LENGTH", "sum(splice_lengths_m)",
                     (("splice_lengths_m", "m"),), "m",
                     "Requires an explicit length for each splice; do not add again if already included in bar lengths."),
        QuantityRule("BAR_MASS", "sum(bar_lengths_m) * mass_kg_per_m",
                     (("bar_lengths_m", "m"), ("mass_kg_per_m", "kg/m")), "kg",
                     "Only specified lengths are counted; overlaps, bends and waste are not inferred."),
        QuantityRule("STIRRUP_CUT_LENGTH", "sum(centerline_segments_m) + sum(end_lengths_m)",
                     (("centerline_segments_m", "m"), ("end_lengths_m", "m")), "m",
                     "Requires the actual centerline shape and explicitly specified end lengths."),
        QuantityRule("HELIX_TURN_LENGTH", "sqrt((pi * centerline_diameter_m)^2 + pitch_m^2)",
                     (("centerline_diameter_m", "m"), ("pitch_m", "m")), "m",
                     "One complete turn; end details are separate."),
        QuantityRule("FORMWORK_AREA", "sum(forming_surface_areas_m2)",
                     (("forming_surface_areas_m2", "m2"),), "m2",
                     "Work area only; material purchase, cutting and reuse are separate."),
        QuantityRule("LAYOUT_ITEM_COUNT", "count(layout_items equal to material_code)",
                     (("layout_items", "piece"), ("material_code", "code"), ("layout_complete", "boolean")),
                     "piece", "A complete explicit layout is required; no volume-based estimation."),
        QuantityRule("COATING_QUANTITY", "area_m2 * confirmed_rate * layer_factor",
                     (("area_m2", "m2"), ("confirmed_rate", "unit/m2"), ("rate_basis", "PER_LAYER|TOTAL_SYSTEM"),
                      ("consumption_unit", "kg|l"), ("rate_confirmed", "boolean"), ("rate_source", "reference")), "specified",
                     "For PER_LAYER the explicit layer_count is required; total-system rate is not multiplied twice."),
        QuantityRule("WHOLE_PACKAGES", "ceil(required_items / items_per_package)",
                     (("required_items", "piece"), ("items_per_package", "piece/package")), "package",
                     "Requires physical item quantity and the actual package content."),
    )
}


def _number(value: Any, name: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{name} must be an exact decimal, not a boolean or float")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{name} must be an exact decimal") from None
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if allow_zero else 'positive'}")
    return result


def _integer(value: Any, name: str, *, allow_zero: bool = False) -> Decimal:
    result = _number(value, name, allow_zero=allow_zero)
    if result != result.to_integral_value():
        raise ValueError(f"{name} must be a whole number")
    return result


def _coordinate(value: Any, name: str) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValueError(f"{name} must be an exact decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{name} must be an exact decimal") from None
    if not result.is_finite():
        raise ValueError(f"{name} must be finite")
    return result


def _box_union_volume(raw_boxes: Any) -> Decimal:
    if not isinstance(raw_boxes, (list, tuple)) or not raw_boxes or len(raw_boxes) > 100:
        raise ValueError("boxes must be a nonempty list of at most 100 explicit boxes")
    keys = ("x_min_m", "x_max_m", "y_min_m", "y_max_m", "z_min_m", "z_max_m")
    boxes = []
    for raw in raw_boxes:
        if not isinstance(raw, dict) or set(raw) != set(keys):
            raise ValueError("each box requires exactly six axis-aligned coordinates")
        box = tuple(_coordinate(raw[key], key) for key in keys)
        if any(box[index] >= box[index + 1] for index in (0, 2, 4)):
            raise ValueError("each box maximum must exceed its minimum")
        boxes.append(box)
    total = Decimal(0)
    xs = sorted({value for box in boxes for value in box[:2]})
    for left, right in zip(xs, xs[1:]):
        active_x = [box for box in boxes if box[0] < right and box[1] > left]
        ys = sorted({value for box in active_x for value in box[2:4]})
        for bottom, top in zip(ys, ys[1:]):
            intervals = sorted((box[4], box[5]) for box in active_x if box[2] < top and box[3] > bottom)
            if not intervals:
                continue
            low, high = intervals[0]
            depth = Decimal(0)
            for start, end in intervals[1:]:
                if start <= high:
                    high = max(high, end)
                else:
                    depth += high - low
                    low, high = start, end
            depth += high - low
            total += (right - left) * (top - bottom) * depth
    return total


def _spaced_zones_count(raw_zones: Any) -> Decimal:
    if not isinstance(raw_zones, (list, tuple)) or not raw_zones:
        raise ValueError("zones must be a nonempty ordered list")
    total = Decimal(0)
    previous_end = None
    for zone in raw_zones:
        if not isinstance(zone, dict) or set(zone) != {"start_m", "end_m", "max_spacing_m", "shared_start_with_previous"}:
            raise ValueError("each zone requires start_m, end_m, max_spacing_m and explicit boundary sharing")
        start = _coordinate(zone["start_m"], "start_m")
        end = _coordinate(zone["end_m"], "end_m")
        spacing = _number(zone["max_spacing_m"], "max_spacing_m")
        if end <= start or (previous_end is not None and start < previous_end):
            raise ValueError("zones must be positive, ordered and non-overlapping")
        shared = zone["shared_start_with_previous"]
        if not isinstance(shared, bool):
            raise ValueError("shared_start_with_previous must be boolean")
        if shared and (previous_end is None or start != previous_end):
            raise ValueError("a shared boundary requires an adjacent preceding zone")
        total += ((end - start) / spacing).to_integral_value(rounding=ROUND_CEILING) + 1
        if shared:
            total -= 1
        previous_end = end
    return total


def _lengths(value: Any, name: str, *, empty_allowed: bool = False) -> tuple[Decimal, ...]:
    if not isinstance(value, (tuple, list)) or (not value and not empty_allowed):
        raise ValueError(f"{name} must be an explicit {'list' if empty_allowed else 'nonempty list'}")
    return tuple(_number(item, name, allow_zero=True) for item in value)


def describe_quantity_rule(code: str, *, role_code: str, material_id: str | None = None) -> dict[str, Any]:
    """Build a versioned knowledge payload; it does not publish or certify a rule."""
    from uuid import UUID

    if not isinstance(role_code, str) or not role_code.strip():
        raise ValueError("a material role is required")
    rule = RULES[code]
    material_reference = str(UUID(material_id)) if material_id is not None else None
    inputs = [{"name": name, "unit": unit} for name, unit in rule.inputs]
    if code == "COATING_QUANTITY":
        inputs.append({"name": "layer_count", "unit": "piece", "required_when": "rate_basis=PER_LAYER"})
    return {
        "kind": "FOUNDATION_QUANTITY_RULE", "code": rule.code, "version": rule.version,
        "expression": rule.expression, "inputs": inputs,
        "result_unit": rule.result_unit, "material_role_code": role_code,
        "canonical_material_id": material_reference, "parameter_status": "PRELIMINARY_ESTIMATE",
        "source": "USER_PROVIDED_SPRINT_SPECIFICATION", "limitation": rule.limitation,
        "structural_safety_verified": False,
    }


def evaluate_quantity_rule(code: str, inputs: Mapping[str, Any]) -> QuantityResult:
    """Evaluate a known operation only; unavailable values remain explicit gaps."""
    rule = RULES[code]
    required = [name for name, _unit in rule.inputs]
    allowed = set(required)
    if code == "COATING_QUANTITY":
        allowed.add("layer_count")
        if inputs.get("rate_basis") == "PER_LAYER":
            required.append("layer_count")
    unknown = set(inputs) - allowed
    if unknown:
        raise ValueError(f"unexpected inputs: {', '.join(sorted(unknown))}")
    missing = [name for name in required if name not in inputs or inputs[name] is None]
    if code == "LAYOUT_ITEM_COUNT" and inputs.get("layout_complete") is False:
        missing.append("complete_layout")
    if code == "COATING_QUANTITY" and inputs.get("rate_confirmed") is False:
        missing.append("confirmed_rate_source")
    if missing:
        return QuantityResult(code, None, rule.result_unit, tuple(dict.fromkeys(missing)))
    with localcontext() as ctx:
        ctx.prec = 34
        if code == "PRISM_VOLUME":
            value = _number(inputs["length_m"], "length_m") * _number(inputs["width_m"], "width_m") * _number(inputs["height_m"], "height_m")
        elif code == "BOX_UNION_VOLUME":
            value = _box_union_volume(inputs["boxes"])
        elif code == "BOX_VOLUME_EXCLUDING_OCCUPIED":
            boxes, occupied = inputs["boxes"], inputs["occupied_boxes"]
            if not isinstance(occupied, (tuple, list)):
                raise ValueError("occupied_boxes must be an explicit list")
            base = _box_union_volume(occupied) if occupied else Decimal(0)
            if not isinstance(boxes, (tuple, list)) or not boxes:
                raise ValueError("boxes must be an explicit nonempty list")
            value = _box_union_volume([*boxes, *occupied]) - base
        elif code in {"NET_AREA", "NET_AREA_VOLUME"}:
            area = _number(inputs["gross_area_m2"], "gross_area_m2", allow_zero=True)
            openings = _number(inputs["openings_area_m2"], "openings_area_m2", allow_zero=True)
            if openings > area:
                raise ValueError("openings_area_m2 cannot exceed gross_area_m2")
            value = area - openings
            if code == "NET_AREA_VOLUME":
                value *= _number(inputs["thickness_m"], "thickness_m")
        elif code == "CYLINDER_VOLUME":
            diameter = _number(inputs["diameter_m"], "diameter_m")
            value = PI * diameter * diameter * _number(inputs["length_m"], "length_m") / 4
        elif code == "SPACED_ELEMENT_COUNT":
            distance = _number(inputs["axis_distance_m"], "axis_distance_m", allow_zero=True)
            spacing = _number(inputs["max_spacing_m"], "max_spacing_m")
            value = (distance / spacing).to_integral_value(rounding=ROUND_CEILING) + 1
        elif code == "SPACED_ZONES_COUNT":
            value = _spaced_zones_count(inputs["zones"])
        elif code == "BAR_TOTAL_LENGTH":
            value = sum(_lengths(inputs["bar_lengths_m"], "bar_lengths_m"), Decimal(0))
        elif code == "LAP_ALLOWANCE_LENGTH":
            lengths = inputs["splice_lengths_m"]
            if not isinstance(lengths, (tuple, list)):
                raise ValueError("splice_lengths_m must be an explicit list")
            value = sum((_number(length, "splice_lengths_m") for length in lengths), Decimal(0))
        elif code == "BAR_MASS":
            value = sum(_lengths(inputs["bar_lengths_m"], "bar_lengths_m"), Decimal(0)) * _number(inputs["mass_kg_per_m"], "mass_kg_per_m")
        elif code == "STIRRUP_CUT_LENGTH":
            value = (sum(_lengths(inputs["centerline_segments_m"], "centerline_segments_m"), Decimal(0))
                     + sum(_lengths(inputs["end_lengths_m"], "end_lengths_m", empty_allowed=True), Decimal(0)))
        elif code == "HELIX_TURN_LENGTH":
            diameter = _number(inputs["centerline_diameter_m"], "centerline_diameter_m")
            pitch = _number(inputs["pitch_m"], "pitch_m")
            value = ((PI * diameter) ** 2 + pitch ** 2).sqrt()
        elif code == "FORMWORK_AREA":
            value = sum(_lengths(inputs["forming_surface_areas_m2"], "forming_surface_areas_m2"), Decimal(0))
        elif code == "LAYOUT_ITEM_COUNT":
            if inputs["layout_complete"] is not True:
                raise ValueError("layout_complete must be an explicit boolean")
            items, material = inputs["layout_items"], inputs["material_code"]
            if not isinstance(items, (tuple, list)) or any(not isinstance(item, str) or not item.strip() for item in items):
                raise ValueError("layout_items must contain explicit material codes")
            if not isinstance(material, str) or not material.strip():
                raise ValueError("material_code must be an explicit material code")
            value = Decimal(sum(item == material for item in items))
        elif code == "COATING_QUANTITY":
            if inputs["rate_confirmed"] is not True:
                raise ValueError("rate_confirmed must be an explicit boolean")
            if not isinstance(inputs["rate_source"], str) or not inputs["rate_source"].strip():
                raise ValueError("rate_source must identify the confirmed source")
            if inputs["consumption_unit"] not in {"kg", "l"}:
                raise ValueError("consumption_unit must be kg or l")
            if inputs["rate_basis"] not in {"PER_LAYER", "TOTAL_SYSTEM"}:
                raise ValueError("rate_basis must identify a layer or the whole system")
            factor = _integer(inputs["layer_count"], "layer_count") if inputs["rate_basis"] == "PER_LAYER" else Decimal(1)
            value = _number(inputs["area_m2"], "area_m2", allow_zero=True) * _number(inputs["confirmed_rate"], "confirmed_rate") * factor
            return QuantityResult(code, value, inputs["consumption_unit"])
        elif code == "WHOLE_PACKAGES":
            quantity = _integer(inputs["required_items"], "required_items", allow_zero=True)
            value = (quantity / _integer(inputs["items_per_package"], "items_per_package")).to_integral_value(rounding=ROUND_CEILING)
        else:
            raise ValueError("unsupported quantity rule")
    return QuantityResult(code, value, rule.result_unit)
