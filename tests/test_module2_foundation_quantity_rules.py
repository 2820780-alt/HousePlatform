from decimal import Decimal
from uuid import uuid4

import pytest

from app.schemas.module2_estimation_contract import EstimationKnowledgeConstraint
from app.services.module2_foundation_quantity_rules import (
    RULES, describe_quantity_rule, evaluate_quantity_rule,
)


def _value(code, **inputs):
    result = evaluate_quantity_rule(code, inputs)
    assert not result.missing_inputs
    return result.value


def test_control_strip_prism_and_separate_rebar_role():
    assert _value("PRISM_VOLUME", length_m="10", width_m="0.4", height_m="0.6") == Decimal("2.4")
    assert _value("BAR_MASS", bar_lengths_m=["10"] * 4, mass_kg_per_m="0.888") == Decimal("35.520")
    assert _value("SPACED_ELEMENT_COUNT", axis_distance_m="10", max_spacing_m="0.2") == 51


def test_lap_allowance_requires_explicit_splice_lengths_and_does_not_infer_norms():
    assert _value("LAP_ALLOWANCE_LENGTH", splice_lengths_m=["0.5", "0.6", "0.5"]) == Decimal("1.6")
    assert _value("LAP_ALLOWANCE_LENGTH", splice_lengths_m=[]) == 0
    assert evaluate_quantity_rule("LAP_ALLOWANCE_LENGTH", {}).missing_inputs == ("splice_lengths_m",)
    with pytest.raises(ValueError):
        _value("LAP_ALLOWANCE_LENGTH", splice_lengths_m=["0"])
    with pytest.raises(ValueError):
        _value("LAP_ALLOWANCE_LENGTH", splice_lengths_m=[0.5])


def test_intersecting_rectangular_concrete_sections_are_not_double_counted():
    boxes = [
        {"x_min_m": "0", "x_max_m": "10", "y_min_m": "0", "y_max_m": "0.4", "z_min_m": "0", "z_max_m": "0.6"},
        {"x_min_m": "0", "x_max_m": "0.4", "y_min_m": "0", "y_max_m": "10", "z_min_m": "0", "z_max_m": "0.6"},
    ]
    assert _value("BOX_UNION_VOLUME", boxes=boxes) == Decimal("4.704")
    assert _value("BOX_UNION_VOLUME", boxes=boxes + [boxes[0]]) == Decimal("4.704")
    with pytest.raises(ValueError):
        _value("BOX_UNION_VOLUME", boxes=[{**boxes[0], "x_max_m": "-1"}])


def test_rib_volume_excludes_the_already_counted_slab():
    slab = {"x_min_m": "0", "x_max_m": "10", "y_min_m": "0", "y_max_m": "10", "z_min_m": "0", "z_max_m": "0.25"}
    rib = {"x_min_m": "0", "x_max_m": "10", "y_min_m": "0", "y_max_m": "0.4", "z_min_m": "0", "z_max_m": "0.6"}
    assert _value("BOX_UNION_VOLUME", boxes=[slab]) == Decimal("25.00")
    assert _value("BOX_VOLUME_EXCLUDING_OCCUPIED", boxes=[rib], occupied_boxes=[slab]) == Decimal("1.400")
    assert _value("BOX_VOLUME_EXCLUDING_OCCUPIED", boxes=[rib], occupied_boxes=[]) == Decimal("2.400")
    assert evaluate_quantity_rule("BOX_VOLUME_EXCLUDING_OCCUPIED", {"boxes": [rib]}).missing_inputs == ("occupied_boxes",)


def test_adjacent_reinforcement_zones_share_a_single_boundary_element():
    zones = [{"start_m": "0", "end_m": "2", "max_spacing_m": "0.2", "shared_start_with_previous": False},
             {"start_m": "2", "end_m": "3", "max_spacing_m": "0.1", "shared_start_with_previous": True}]
    assert _value("SPACED_ZONES_COUNT", zones=zones) == 21
    assert _value("SPACED_ZONES_COUNT", zones=[zones[0], {**zones[1], "shared_start_with_previous": False}]) == 22
    assert _value("SPACED_ZONES_COUNT", zones=[zones[0], {**zones[1], "start_m": "2.5", "shared_start_with_previous": False}]) == 17
    with pytest.raises(ValueError):
        _value("SPACED_ZONES_COUNT", zones=[zones[0], {**zones[1], "start_m": "1.9"}])
    with pytest.raises(ValueError):
        _value("SPACED_ZONES_COUNT", zones=[zones[0], {**zones[1], "start_m": "2.5"}])


def test_control_basement_wall_four_separate_reinforcement_groups():
    assert _value("NET_AREA_VOLUME", gross_area_m2="25", openings_area_m2="0", thickness_m="0.25") == Decimal("6.25")
    vertical = _value("SPACED_ELEMENT_COUNT", axis_distance_m="9.9", max_spacing_m="0.2")
    horizontal = _value("SPACED_ELEMENT_COUNT", axis_distance_m="2.4", max_spacing_m="0.2")
    assert (vertical, horizontal) == (51, 13)
    lengths = ["2.4"] * (int(vertical) * 2) + ["9.9"] * (int(horizontal) * 2)
    assert _value("BAR_TOTAL_LENGTH", bar_lengths_m=lengths) == Decimal("502.2")
    assert _value("BAR_MASS", bar_lengths_m=lengths, mass_kg_per_m="0.888") == Decimal("445.9536")
    assert _value("FORMWORK_AREA", forming_surface_areas_m2=["25", "25"]) == Decimal("50")


def test_control_slab_uses_supplied_net_area_and_independent_groups():
    assert _value("NET_AREA_VOLUME", gross_area_m2="100", openings_area_m2="0", thickness_m="0.25") == Decimal("25")
    count = _value("SPACED_ELEMENT_COUNT", axis_distance_m="9.9", max_spacing_m="0.2")
    assert count == 51
    assert [_value("BAR_MASS", bar_lengths_m=["9.9"] * int(count), mass_kg_per_m="0.888")
            for _group in range(4)] == [Decimal("448.3512")] * 4


def test_net_area_is_in_square_metres_not_cubic_metres():
    result = evaluate_quantity_rule("NET_AREA", {"gross_area_m2": "25", "openings_area_m2": "2"})
    assert result.value == Decimal("23") and result.unit == "m2"
    with pytest.raises(ValueError):
        _value("NET_AREA", gross_area_m2="2", openings_area_m2="3")


def test_control_bored_pile_and_no_double_count_of_factory_piles():
    volume = _value("CYLINDER_VOLUME", diameter_m="0.3", length_m="3")
    assert abs(volume - Decimal("0.212057504117311")) < Decimal("0.000000000000001")
    assert _value("LAYOUT_ITEM_COUNT", layout_items=["PILE-RC-01", "PILE-RC-01"],
                  material_code="PILE-RC-01", layout_complete=True) == 2


def test_precast_count_is_by_complete_layout_and_mark():
    layout = ["FBS-02", "FBS-02", "FBS-05", "FBS-09", "FL-12"]
    assert _value("LAYOUT_ITEM_COUNT", layout_items=layout, material_code="FBS-02", layout_complete=True) == 2
    assert _value("LAYOUT_ITEM_COUNT", layout_items=layout, material_code="FBS-05", layout_complete=True) == 1
    assert _value("LAYOUT_ITEM_COUNT", layout_items=layout, material_code="FL-12", layout_complete=True) == 1
    assert evaluate_quantity_rule("LAYOUT_ITEM_COUNT", {"layout_items": layout, "material_code": "FL-12",
                                                        "layout_complete": False}).value is None


def test_coating_rate_basis_prevents_double_counting_and_requires_source():
    common = {"area_m2": "25", "confirmed_rate": "1.2", "consumption_unit": "kg",
              "rate_confirmed": True, "rate_source": "system-document:example"}
    assert _value("COATING_QUANTITY", **common, rate_basis="PER_LAYER", layer_count=2) == Decimal("60.0")
    assert _value("COATING_QUANTITY", **common, rate_basis="TOTAL_SYSTEM", layer_count=2) == Decimal("30.0")
    missing = evaluate_quantity_rule("COATING_QUANTITY", {**common, "rate_basis": "PER_LAYER"})
    assert missing.value is None and missing.missing_inputs == ("layer_count",)
    missing = evaluate_quantity_rule("COATING_QUANTITY", {**common, "rate_basis": "TOTAL_SYSTEM", "rate_confirmed": False})
    assert missing.value is None and "confirmed_rate_source" in missing.missing_inputs


def test_insulation_volume_and_whole_packages_do_not_guess_packaging():
    assert _value("NET_AREA_VOLUME", gross_area_m2="100", openings_area_m2="4", thickness_m="0.1") == Decimal("9.6")
    assert _value("WHOLE_PACKAGES", required_items=21, items_per_package=8) == 3
    assert evaluate_quantity_rule("WHOLE_PACKAGES", {"required_items": 21}).missing_inputs == ("items_per_package",)


def test_stirrup_requires_explicit_centerline_and_end_details():
    result = evaluate_quantity_rule("STIRRUP_CUT_LENGTH", {"centerline_segments_m": ["0.32", "0.52", "0.32", "0.52"]})
    assert result.value is None and result.missing_inputs == ("end_lengths_m",)
    assert _value("STIRRUP_CUT_LENGTH", centerline_segments_m=["0.32", "0.52", "0.32", "0.52"],
                  end_lengths_m=["0.1", "0.1"]) == Decimal("1.88")
    assert _value("HELIX_TURN_LENGTH", centerline_diameter_m="0.2", pitch_m="0.1") > Decimal("0.6")


@pytest.mark.parametrize("code,inputs", [
    ("PRISM_VOLUME", {"length_m": 1.0, "width_m": "1", "height_m": "1"}),
    ("CYLINDER_VOLUME", {"diameter_m": "NaN", "length_m": "1"}),
    ("SPACED_ELEMENT_COUNT", {"axis_distance_m": "5", "max_spacing_m": "0"}),
    ("NET_AREA_VOLUME", {"gross_area_m2": "2", "openings_area_m2": "3", "thickness_m": "1"}),
    ("WHOLE_PACKAGES", {"required_items": "1.5", "items_per_package": 2}),
])
def test_invalid_inputs_are_not_silently_coerced(code, inputs):
    with pytest.raises(ValueError):
        evaluate_quantity_rule(code, inputs)


def test_existing_m5_constraint_can_carry_rule_metadata_without_quantity_or_side_effects():
    material_id = str(uuid4())
    payload = describe_quantity_rule("SPACED_ELEMENT_COUNT", role_code="TOP_REBAR", material_id=material_id)
    constraint = EstimationKnowledgeConstraint(
        rule_id=uuid4(), rule_code="TEST_COUNT", revision=1, scope_kind="TECHNOLOGY",
        outcome_type="INFORMATION", outcome_payload=payload,
    )
    copied = EstimationKnowledgeConstraint.model_validate_json(constraint.model_dump_json())
    assert copied.outcome_payload["canonical_material_id"] == material_id
    assert copied.outcome_payload["structural_safety_verified"] is False
    assert copied.outcome_payload["parameter_status"] == "PRELIMINARY_ESTIMATE"
    assert set(RULES) and "value" not in copied.outcome_payload
    coating = describe_quantity_rule("COATING_QUANTITY", role_code="MASTIC")
    assert any(item.get("name") == "layer_count" and item.get("required_when") for item in coating["inputs"])
