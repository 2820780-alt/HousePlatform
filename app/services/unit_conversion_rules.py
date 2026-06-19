from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class ConversionResult:
    can_convert: bool
    value: Decimal | None = None
    unit: str | None = None
    reason: str | None = None
    missing_specifications: tuple[str, ...] = ()


UNIT_FACTORS_TO_BASE = {
    "мм": Decimal("0.001"),
    "mm": Decimal("0.001"),
    "см": Decimal("0.01"),
    "cm": Decimal("0.01"),
    "м": Decimal("1"),
    "m": Decimal("1"),
    "г": Decimal("0.001"),
    "g": Decimal("0.001"),
    "кг": Decimal("1"),
    "kg": Decimal("1"),
}

SPEC_ALIASES = {
    "thickness": ("thickness", "толщина"),
    "width": ("width", "ширина"),
    "length": ("length", "длина"),
    "height": ("height", "высота"),
    "package_weight": ("package_weight", "bag_weight", "вес мешка", "масса мешка"),
    "roll_length": ("roll_length", "длина бухты", "длина рулона"),
    "single_piece_weight": ("single_piece_weight", "вес одной штуки", "масса одной штуки"),
}


def convert_quantity(
    quantity: Decimal | int | float | str,
    *,
    from_unit: str,
    to_unit: str,
    formula_type: str,
    specifications: dict[str, Any],
    coefficient: Decimal | int | float | str | None = None,
) -> ConversionResult:
    """Convert material quantity only when the supplied specifications are enough."""
    quantity_decimal = _to_decimal(quantity)
    if quantity_decimal is None:
        return ConversionResult(False, reason="Количество указано в неподдерживаемом формате")

    formula_type = formula_type.upper()
    from_unit = _normalize_unit(from_unit)
    to_unit = _normalize_unit(to_unit)

    if formula_type in {"DIMENSION_VOLUME", "PIECE_TO_VOLUME"}:
        return _dimension_volume(quantity_decimal, to_unit, specifications)
    if formula_type in {"DIMENSION_AREA", "PIECE_TO_AREA"}:
        return _dimension_area(quantity_decimal, to_unit, specifications)
    if formula_type == "PACKAGE_TO_UNIT":
        return _package_to_unit(quantity_decimal, to_unit, specifications, coefficient)
    if formula_type == "WEIGHT_TO_PIECE":
        return _weight_to_piece(quantity_decimal, from_unit, to_unit, specifications)
    if formula_type == "LINEAR_COEFFICIENT":
        coefficient_decimal = _to_decimal(coefficient)
        if coefficient_decimal is None:
            return ConversionResult(False, reason="Не задан подтвержденный коэффициент")
        return ConversionResult(True, quantity_decimal * coefficient_decimal, to_unit)

    return ConversionResult(False, reason=f"Тип формулы не поддержан: {formula_type}")


def missing_required_specifications(required: list[str] | tuple[str, ...], specifications: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    for field_key in required:
        if _spec_value(specifications, field_key) is None:
            missing.append(field_key)
    return tuple(missing)


def _dimension_volume(quantity: Decimal, to_unit: str, specifications: dict[str, Any]) -> ConversionResult:
    required = ("length", "width", "height")
    if _spec_value(specifications, "height") is None and _spec_value(specifications, "thickness") is not None:
        required = ("length", "width", "thickness")

    missing = missing_required_specifications(required, specifications)
    if missing:
        return ConversionResult(False, reason="Недостаточно характеристик для расчета объема", missing_specifications=missing)

    length = _dimension_to_meters(_spec_value(specifications, "length"))
    width = _dimension_to_meters(_spec_value(specifications, "width"))
    height_key = "height" if "height" in required else "thickness"
    height = _dimension_to_meters(_spec_value(specifications, height_key))
    if None in (length, width, height):
        return ConversionResult(False, reason="Размеры указаны в неподдерживаемом формате")

    if to_unit not in {"м3", "m3", "м³"}:
        return ConversionResult(False, reason="Объемная формула поддерживает перевод только в м3")
    return ConversionResult(True, quantity * length * width * height, "м3")


def _dimension_area(quantity: Decimal, to_unit: str, specifications: dict[str, Any]) -> ConversionResult:
    missing = missing_required_specifications(("length", "width"), specifications)
    if missing:
        return ConversionResult(False, reason="Недостаточно характеристик для расчета площади", missing_specifications=missing)

    length = _dimension_to_meters(_spec_value(specifications, "length"))
    width = _dimension_to_meters(_spec_value(specifications, "width"))
    if None in (length, width):
        return ConversionResult(False, reason="Размеры указаны в неподдерживаемом формате")

    if to_unit not in {"м2", "m2", "м²"}:
        return ConversionResult(False, reason="Площадная формула поддерживает перевод только в м2")
    return ConversionResult(True, quantity * length * width, "м2")


def _package_to_unit(
    quantity: Decimal,
    to_unit: str,
    specifications: dict[str, Any],
    coefficient: Decimal | int | float | str | None,
) -> ConversionResult:
    coefficient_decimal = _to_decimal(coefficient)
    if coefficient_decimal is None:
        key = "package_weight" if to_unit in {"кг", "kg"} else "roll_length"
        coefficient_decimal = _dimensionless_spec(specifications, key)
        if coefficient_decimal is None:
            return ConversionResult(False, reason="Не задан вес упаковки или длина бухты", missing_specifications=(key,))
    return ConversionResult(True, quantity * coefficient_decimal, to_unit)


def _weight_to_piece(quantity: Decimal, from_unit: str, to_unit: str, specifications: dict[str, Any]) -> ConversionResult:
    if to_unit not in {"шт", "piece", "pieces"}:
        return ConversionResult(False, reason="Весовая формула поддерживает перевод только в штуки")

    weight_kg = quantity
    if from_unit in {"г", "g"}:
        weight_kg = quantity * Decimal("0.001")
    elif from_unit not in {"кг", "kg"}:
        return ConversionResult(False, reason="Весовая формула поддерживает вход только в кг или г")

    single_piece_weight = _dimensionless_spec(specifications, "single_piece_weight")
    if single_piece_weight is None:
        return ConversionResult(
            False,
            reason="Нет подтвержденного веса одной штуки",
            missing_specifications=("single_piece_weight",),
        )
    if single_piece_weight == 0:
        return ConversionResult(False, reason="Вес одной штуки не может быть нулевым")
    return ConversionResult(True, weight_kg / single_piece_weight, "шт")


def _spec_value(specifications: dict[str, Any], field_key: str) -> Any:
    for alias in SPEC_ALIASES.get(field_key, (field_key,)):
        if alias in specifications and specifications[alias] not in (None, ""):
            return specifications[alias]
    return None


def _dimension_to_meters(value: Any) -> Decimal | None:
    if isinstance(value, dict):
        amount = _to_decimal(value.get("value"))
        unit = _normalize_unit(str(value.get("unit") or "мм"))
    else:
        amount = _to_decimal(value)
        unit = "мм"
    if amount is None:
        return None
    factor = UNIT_FACTORS_TO_BASE.get(unit)
    if factor is None:
        return None
    return amount * factor


def _dimensionless_spec(specifications: dict[str, Any], field_key: str) -> Decimal | None:
    value = _spec_value(specifications, field_key)
    if isinstance(value, dict):
        amount = _to_decimal(value.get("value"))
        unit = _normalize_unit(str(value.get("unit") or ""))
        if amount is None:
            return None
        if unit in UNIT_FACTORS_TO_BASE:
            return amount * UNIT_FACTORS_TO_BASE[unit]
        return amount
    return _to_decimal(value)


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ".").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _normalize_unit(unit: str) -> str:
    return unit.strip().lower().replace("³", "3").replace("²", "2")
