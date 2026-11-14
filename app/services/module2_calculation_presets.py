"""Safe starting points for editable M2 calculation blocks, without design norms."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.services.module2_calculation_graph import (
    BlockParameter, CalculationBlock, CalculationNode, Threshold, validate_block,
)


def rectangular_volume_block(*, name: str = "Объём конструкции") -> CalculationBlock:
    """A prism with explicitly supplied dimensions; no engineering defaults."""
    ids = {key: str(uuid4()) for key in ("length", "width", "height", "volume")}
    result = CalculationBlock(
        id=str(uuid4()), name=name,
        nodes=(
            CalculationNode(ids["length"], "INPUT", "m", input_key="geometry.length"),
            CalculationNode(ids["width"], "INPUT", "m", input_key="geometry.width"),
            CalculationNode(ids["height"], "INPUT", "m", input_key="geometry.height"),
            CalculationNode(ids["volume"], "PRISM_VOLUME", "m3",
                            inputs=(ids["length"], ids["width"], ids["height"])),
        ),
        outputs=(ids["volume"],),
        parameters=(
            BlockParameter("geometry.length", "Длина", "m"),
            BlockParameter("geometry.width", "Ширина", "m"),
            BlockParameter("geometry.height", "Высота", "m"),
        ),
        material_output_id=ids["volume"], work_output_id=ids["volume"],
    )
    validate_block(result)
    return result


def area_consumption_block(*, name: str = "Покрытие поверхности") -> CalculationBlock:
    """Quantity from an explicit area, thickness and material-specific rate."""
    ids = {key: str(uuid4()) for key in ("area", "thickness", "rate", "volume", "mass")}
    result = CalculationBlock(
        id=str(uuid4()), name=name,
        nodes=(
            CalculationNode(ids["area"], "INPUT", "m2", input_key="geometry.area"),
            CalculationNode(ids["thickness"], "INPUT", "mm", input_key="technology.thickness"),
            CalculationNode(ids["rate"], "INPUT", "kg_per_m2_mm", input_key="material.consumption"),
            CalculationNode(ids["volume"], "MULTIPLY", "m3", inputs=(ids["area"], ids["thickness"])),
            CalculationNode(ids["mass"], "MULTIPLY", "kg", inputs=(ids["volume"], ids["rate"])),
        ),
        outputs=(ids["mass"], ids["area"]),
        parameters=(
            BlockParameter("geometry.area", "Площадь", "m2", minimum=Decimal(0)),
            BlockParameter("technology.thickness", "Толщина", "mm", minimum=Decimal(0)),
            BlockParameter("material.consumption", "Расход материала", "kg_per_m2_mm", minimum=Decimal(0)),
        ),
        material_output_id=ids["mass"], work_output_id=ids["area"],
    )
    validate_block(result)
    return result


def reinforcement_block(*, thresholds: tuple[Threshold, ...], source: str,
                        name: str = "Продольная арматура") -> CalculationBlock:
    """Explicit project-selected bar counts and lap lengths; no normative defaults."""
    if not source.strip() or any(case.result < 2 or case.result != case.result.to_integral_value() for case in thresholds):
        raise ValueError("bar counts and their source must be explicitly specified")
    names = ("width", "length", "cover", "diameter", "min", "max", "lap", "joints", "mass_per_m",
             "bars", "spacing", "bar_length", "lap_total", "total_length", "raw_mass", "mass")
    ids = {key: str(uuid4()) for key in names}
    node = lambda key, operation, unit, **kwargs: CalculationNode(ids[key], operation, unit, **kwargs)
    inputs = (
        ("width", "geometry.width", "mm", "Ширина"), ("length", "geometry.length", "m", "Длина"),
        ("cover", "reinforcement.cover", "mm", "Защитный слой"),
        ("diameter", "reinforcement.diameter", "mm", "Диаметр"),
        ("min", "reinforcement.min_spacing", "mm", "Минимальный интервал"),
        ("max", "reinforcement.max_spacing", "mm", "Максимальный интервал"),
        ("lap", "reinforcement.lap_length", "m", "Длина одного нахлёста"),
        ("joints", "reinforcement.joints", "piece", "Количество нахлёстов"),
        ("mass_per_m", "material.mass_per_m", "kg_per_m", "Масса погонного метра"),
    )
    nodes = tuple(node(key, "INPUT", unit, input_key=input_key) for key, input_key, unit, _ in inputs) + (
        node("bars", "PIECEWISE", "piece", inputs=(ids["width"],), thresholds=thresholds),
        node("spacing", "BAR_SPACING", "mm", inputs=tuple(ids[key] for key in ("width", "cover", "diameter", "bars", "min", "max"))),
        node("bar_length", "MULTIPLY", "m", inputs=(ids["bars"], ids["length"])),
        node("lap_total", "MULTIPLY", "m", inputs=(ids["lap"], ids["joints"])),
        node("total_length", "ADD", "m", inputs=(ids["bar_length"], ids["lap_total"])),
        node("raw_mass", "MULTIPLY", "kg", inputs=(ids["total_length"], ids["mass_per_m"])),
        node("mass", "REQUIRE_VALID", "kg", inputs=(ids["raw_mass"], ids["spacing"])),
    )
    block = CalculationBlock(id=str(uuid4()), name=name, nodes=nodes, outputs=(ids["mass"],),
        parameters=tuple(BlockParameter(input_key, label, unit) for _, input_key, unit, label in inputs),
        material_output_id=ids["mass"], work_output_id=ids["mass"], rule_source=source.strip(), rule_status="PRELIMINARY")
    validate_block(block)
    return block
