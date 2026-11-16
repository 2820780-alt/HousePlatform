from decimal import Decimal

import pytest

from app.services.module7_foundation_inputs import (
    FOUNDATION_FIELDS, GeometryDefault, resolve_foundation_geometry,
)


def test_all_fifteen_foundation_types_have_distinct_typed_fields():
    assert len(FOUNDATION_FIELDS) == 15
    for fields in FOUNDATION_FIELDS.values():
        assert fields and len({item.key for item in fields}) == len(fields)
        assert all(item.label and item.unit in {"m", "m2", "m3", "piece"} for item in fields)


def test_ushp_edge_geometry_is_explicit_and_preserves_legacy_input():
    resolve = lambda data: resolve_foundation_geometry("FND_SLAB_USHP", user_values=data, project_values={})
    legacy = resolve({"geometry.edge_area": "2"})
    assert legacy.values["geometry.edge_area"] == (Decimal(2), "m2")
    missing = resolve({"edge.enabled": "1", "edge.contour_length": "40"})
    assert "edge.height" in missing.missing and "edge.excluded_length" in missing.missing
    assert "geometry.edge_area" not in missing.values
    result = resolve({"edge.enabled": "1", "edge.contour_length": "40", "edge.height": "0.5",
                      "edge.excluded_length": "4"})
    assert result.values["geometry.edge_area"] == (Decimal("18.0"), "m2")
    assert result.provenance["geometry.edge_area"] == "CALCULATED"
    disabled = resolve({"edge.enabled": "0", "geometry.edge_area": "9"})
    assert disabled.values["geometry.edge_area"] == (Decimal(0), "m2")
    with pytest.raises(ValueError, match="исключаемых"):
        resolve({"edge.enabled": "1", "edge.contour_length": "4", "edge.height": "1", "edge.excluded_length": "5"})
    with pytest.raises(ValueError, match="edge.enabled"):
        resolve({"edge.enabled": "2"})


def test_geometry_precedence_and_preliminary_defaults_are_explicit():
    defaults = {"geometry.width": GeometryDefault("0.6", "m", "QA project", "VERIFIED"),
                "geometry.height": GeometryDefault("0.8", "m", "QA project", "PRELIMINARY")}
    result = resolve_foundation_geometry("FND_STRIP_MONOLITHIC_RC",
        user_values={"geometry.width": "0,4"}, project_values={"geometry.width": "0.5", "geometry.length": "12"},
        defaults=defaults)
    assert result.values["geometry.width"] == (Decimal("0.4"), "m")
    assert result.provenance["geometry.width"] == "USER_OVERRIDE"
    assert result.provenance["geometry.length"] == "PROJECT_VALUE"
    assert "geometry.height" in result.missing and "strip.overlap_volume" in result.missing
    allowed = resolve_foundation_geometry("FND_STRIP_MONOLITHIC_RC", user_values={},
        project_values={"geometry.length": "12", "strip.overlap_volume": "0"},
        defaults=defaults, allow_preliminary=True)
    assert allowed.provenance["geometry.width"] == "M2_DEFAULT"
    assert allowed.warnings == ("geometry.height",) and not allowed.missing


@pytest.mark.parametrize("value", ["-1", "2.5", "NaN", "Infinity", True, 1.0])
def test_pile_count_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        resolve_foundation_geometry("FND_PILE_DRIVEN_RC", user_values={"pile.count": value}, project_values={})


def test_missing_and_zero_are_not_conflated_and_unknown_inputs_fail():
    empty = resolve_foundation_geometry("FND_STRIP_PRECAST_FBS_FL", user_values={}, project_values={})
    assert len(empty.missing) == 5 and "layout.items" in empty.missing and not empty.values
    zero = resolve_foundation_geometry("FND_STRIP_PRECAST_FBS_FL", user_values={"layout.fl": "0"}, project_values={})
    assert zero.values["layout.fl"] == (Decimal(0), "piece")
    assert "layout.fl" not in zero.missing
    assert "layout.items" in zero.missing
    with pytest.raises(ValueError, match="unknown geometry"):
        resolve_foundation_geometry("FND_PILE_DRIVEN_RC", user_values={"unknown": "3"}, project_values={})


def test_unverified_or_mismatched_defaults_cannot_silently_populate_values():
    for default in (GeometryDefault("1", "m", "", "VERIFIED"),
                    GeometryDefault("1", "kg", "QA", "VERIFIED"),
                    GeometryDefault("1", "m", "QA", "UNCONFIRMED")):
        with pytest.raises(ValueError, match="invalid M2 default"):
            resolve_foundation_geometry("FND_STRIP_MONOLITHIC_RC", user_values={}, project_values={},
                                        defaults={"geometry.width": default})
