"""Price display helpers for the M1 materials interface.

Prices remain attached to their original offers. Conversion is read-only and
requires enough information to express one sale unit in the material base unit.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from app.services.module1_unit_conversion_registry import UnitConversionRegistry


def comparable_unit_price(
    price: Decimal | int | str | None,
    sale_unit: str | None,
    base_unit: str | None,
    *,
    material_group: str | None = None,
    material_profile: Mapping[str, Any] | None = None,
    currency: str | None = "RUB",
) -> Decimal | None:
    """Return RUB per base unit, or None when an offer is not comparable."""
    if not sale_unit or not base_unit or (currency or "").upper() != "RUB":
        return None
    try:
        value = Decimal(str(price))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not value.is_finite() or value <= 0:
        return None
    registry = UnitConversionRegistry()
    if sale_unit.strip().casefold() == "шт.":
        sale_unit = "шт"
    if base_unit.strip().casefold() == "шт.":
        base_unit = "шт"
    from_unit, to_unit = registry.normalize_unit(sale_unit), registry.normalize_unit(base_unit)
    profile = material_profile or {}
    if material_group == "rebar" and "kg" in {from_unit, to_unit} and {from_unit, to_unit} <= {"m", "linear_meter", "kg"} and from_unit != to_unit:
        # The registry also estimates mass from diameter; a price needs an explicit mass.
        if "kg_per_meter" not in profile:
            return None
    numeric_fields = ("kg_per_meter", "length_mm", "width_mm", "height_mm", "thickness_mm",
                      "length_m", "width_m", "height_m", "thickness_m", "sheet_area_m2",
                      "package_area_m2", "package_volume_m3", "roll_area_m2", "roll_width_m", "roll_length_m")
    for field in numeric_fields:
        if field in profile:
            try:
                number = Decimal(str(profile[field]))
                if not number.is_finite() or number <= 0:
                    return None
            except (InvalidOperation, ValueError, TypeError):
                return None
    result = registry.convert_quantity(
        1, sale_unit, base_unit, material_profile=material_profile, material_group=material_group,
    )
    if not result.success or result.value is None or not result.value.is_finite() or result.value <= 0:
        return None
    return value / result.value


def comparable_rule_price(price: Decimal | int | str | None, sale_unit: str | None, base_unit: str | None,
                          rules: list[Any], *, currency: str | None = "RUB") -> Decimal | None:
    """Use an existing active material-specific coefficient only when unambiguous."""
    if not sale_unit or not base_unit or (currency or "").upper() != "RUB":
        return None
    registry = UnitConversionRegistry()
    sale = registry.normalize_unit("шт" if sale_unit.strip().casefold() == "шт." else sale_unit)
    base = registry.normalize_unit("шт" if base_unit.strip().casefold() == "шт." else base_unit)
    if not sale or not base or sale == base:
        return None
    try:
        value = Decimal(str(price))
        if not value.is_finite() or value <= 0:
            return None
        factors = set()
        for rule in rules:
            if (rule.status != "ACTIVE" or rule.formula_type != "LINEAR_COEFFICIENT" or not (rule.source or "").strip()
                    or registry.normalize_unit(rule.from_unit) != sale or registry.normalize_unit(rule.to_unit) != base):
                continue
            factor = Decimal(str(rule.coefficient))
            if factor.is_finite() and factor > 0:
                factors.add(factor)
        if len(factors) != 1:
            return None
        return value / factors.pop()
    except (InvalidOperation, ValueError, TypeError, ZeroDivisionError):
        return None
