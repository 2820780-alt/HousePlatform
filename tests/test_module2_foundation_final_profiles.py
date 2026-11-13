from decimal import Decimal

import pytest

from app.services.module2_foundation_preliminary_profiles import PROFILES
from app.services.module2_foundation_quantity_rules import describe_quantity_rule, evaluate_quantity_rule


BOX = {"x_min_m": "0", "x_max_m": "2", "y_min_m": "0", "y_max_m": "1",
       "z_min_m": "0", "z_max_m": "1"}
CASES = {
    "BAR_MASS": ({"bar_lengths_m": ["2", "3"], "mass_kg_per_m": "2"}, "10", "kg"),
    "BOX_UNION_VOLUME": ({"boxes": [BOX, BOX]}, "2", "m3"),
    "BOX_VOLUME_EXCLUDING_OCCUPIED": ({"boxes": [BOX], "occupied_boxes": [BOX]}, "0", "m3"),
    "COATING_QUANTITY": ({"area_m2": "10", "confirmed_rate": "0.5", "rate_basis": "PER_LAYER",
                          "consumption_unit": "kg", "rate_confirmed": True, "rate_source": "test",
                          "layer_count": "2"}, "10", "kg"),
    "CYLINDER_VOLUME": ({"diameter_m": "2", "length_m": "1"}, None, "m3"),
    "FORMWORK_AREA": ({"forming_surface_areas_m2": ["2", "3"]}, "5", "m2"),
    "LAP_ALLOWANCE_LENGTH": ({"splice_lengths_m": ["0.5", "0.6"]}, "1.1", "m"),
    "LAYOUT_ITEM_COUNT": ({"layout_items": ["A", "B", "A"], "material_code": "A",
                           "layout_complete": True}, "2", "piece"),
    "NET_AREA": ({"gross_area_m2": "10", "openings_area_m2": "2"}, "8", "m2"),
    "NET_AREA_VOLUME": ({"gross_area_m2": "10", "openings_area_m2": "2",
                         "thickness_m": "0.25"}, "2", "m3"),
    "SHEET_CUT_AREA": ({"cut_sheet_areas_m2": ["3.2", "3.4"], "layout_complete": True,
                        "overlaps_included": True}, "6.6", "m2"),
    "SPACED_ZONES_COUNT": ({"zones": [{"start_m": "0", "end_m": "1", "max_spacing_m": "0.5",
                                        "shared_start_with_previous": False},
                                       {"start_m": "1", "end_m": "2", "max_spacing_m": "0.5",
                                        "shared_start_with_previous": True}]}, "5", "piece"),
    "STIRRUP_CUT_LENGTH": ({"centerline_segments_m": ["1", "1"], "end_lengths_m": ["0.2"]}, "2.2", "m"),
}


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.technology_code)
def test_each_foundation_profile_calculates_only_from_explicit_inputs(profile):
    codes = {code for role in profile.roles for code in (role.quantity_rule, *role.follow_up_rules) if code}
    assert codes, "each foundation profile must expose a quantity rule or an explicit blocker"
    for code in codes:
        sample, expected, unit = CASES[code]
        missing = evaluate_quantity_rule(code, {})
        assert missing.value is None and missing.missing_inputs
        result = evaluate_quantity_rule(code, sample)
        assert result.unit == unit
        assert result.value is not None and result.value >= 0
        if expected is not None:
            assert result.value == Decimal(expected)


@pytest.mark.parametrize("field,missing", [("layout_complete", "complete_layout"),
                                           ("overlaps_included", "overlap_details")])
def test_sheet_purchase_area_requires_complete_cut_layout_with_overlaps(field, missing):
    sample = {**CASES["SHEET_CUT_AREA"][0], field: False}
    result = evaluate_quantity_rule("SHEET_CUT_AREA", sample)
    assert result.value is None and missing in result.missing_inputs


@pytest.mark.parametrize("field", ["layout_complete", "overlaps_included"])
def test_sheet_purchase_area_rejects_non_boolean_confirmation(field):
    sample = {**CASES["SHEET_CUT_AREA"][0], field: "true"}
    with pytest.raises(ValueError, match="explicit booleans"):
        evaluate_quantity_rule("SHEET_CUT_AREA", sample)


def test_sheet_rule_does_not_claim_to_be_a_user_supplied_norm():
    payload = describe_quantity_rule("SHEET_CUT_AREA", role_code="BITUMEN_MEMBRANE")
    assert payload["source"] == "DERIVED_LAYOUT_GEOMETRY"
    assert payload["structural_safety_verified"] is False
