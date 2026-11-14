"""Bounded, deterministic building blocks for preliminary calculations.

The module has no database or network access and never evaluates user code.
Material/work links and publication permissions remain the caller's concern.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, DecimalException, ROUND_CEILING, ROUND_FLOOR, localcontext
from typing import Mapping
from uuid import uuid4


# Dimensions are (length, mass); a count is dimensionless but integral.
UNITS = {
    "1": ((0, 0), Decimal("1")),
    "piece": ((0, 0), Decimal("1")),
    "mm": ((1, 0), Decimal("0.001")),
    "m": ((1, 0), Decimal("1")),
    "m2": ((2, 0), Decimal("1")),
    "m3": ((3, 0), Decimal("1")),
    "kg": ((0, 1), Decimal("1")),
    "kg_per_m": ((-1, 1), Decimal("1")),
    "kg_per_m2_mm": ((-3, 1), Decimal("1000")),
}


@dataclass(frozen=True)
class Threshold:
    lower: Decimal
    upper: Decimal
    result: Decimal
    upper_inclusive: bool = False


@dataclass(frozen=True)
class CalculationNode:
    id: str
    operation: str
    unit: str
    inputs: tuple[str, ...] = ()
    input_key: str | None = None
    constant: Decimal | None = None
    thresholds: tuple[Threshold, ...] = ()
    label: str | None = None


@dataclass(frozen=True)
class BlockParameter:
    input_key: str
    label: str
    unit: str
    default: Decimal | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    source: str | None = None
    status: str = "UNCONFIRMED"
    auto_apply: bool = False


@dataclass(frozen=True)
class CalculationBlock:
    id: str
    name: str
    nodes: tuple[CalculationNode, ...]
    outputs: tuple[str, ...]
    parameters: tuple[BlockParameter, ...] = ()
    material_id: str | None = None
    work_code: str | None = None
    material_output_id: str | None = None
    work_output_id: str | None = None
    template_id: str | None = None
    template_version: int | None = None
    rule_source: str | None = None
    rule_status: str = "UNCONFIRMED"
    material_requirement_id: str | None = None
    work_step_id: str | None = None


@dataclass(frozen=True)
class CalculationValue:
    value: Decimal | None
    unit: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


_ARITY = {"INPUT": 0, "CONSTANT": 0, "ADD": 2, "SUBTRACT": 2, "MULTIPLY": 2,
          "DIVIDE": 2, "CEIL": 1, "FLOOR": 1, "LESS_THAN": 2, "IF": 3,
          "PIECEWISE": 1, "PRISM_VOLUME": 3, "BAR_SPACING": 6, "REQUIRE_VALID": 2}


def _decimal(value: object) -> Decimal:
    if isinstance(value, (bool, float)) or value is None:
        raise ValueError("values must be exact decimals")
    try:
        result = Decimal(str(value))
    except (DecimalException, ValueError, TypeError):
        raise ValueError("values must be exact decimals") from None
    if not result.is_finite() or result.adjusted() > 24 or result.adjusted() < -24:
        raise ValueError("decimal is non-finite or out of range")
    return result


def _dimension(unit: str) -> tuple[int, int]:
    try:
        return UNITS[unit][0]
    except KeyError:
        raise ValueError(f"unsupported unit: {unit}") from None


def validate_block(block: CalculationBlock) -> tuple[CalculationNode, ...]:
    """Check operator whitelist, references, dimensions, boundaries and DAG."""
    if not block.id or not block.name.strip() or not block.nodes or len(block.nodes) > 256:
        raise ValueError("block requires an id, name and 1..256 nodes")
    if block.rule_status not in {"UNCONFIRMED", "PRELIMINARY", "VERIFIED"}:
        raise ValueError("invalid rule status")
    if block.rule_status != "UNCONFIRMED" and not (block.rule_source or "").strip():
        raise ValueError("confirmed or preliminary rules require a source")
    nodes = {node.id: node for node in block.nodes}
    if len(nodes) != len(block.nodes) or any(not node_id for node_id in nodes):
        raise ValueError("node IDs must be nonempty and unique")
    if not block.outputs or any(node_id not in nodes for node_id in block.outputs):
        raise ValueError("block outputs must reference existing nodes")
    if any(output is not None and output not in block.outputs
           for output in (block.material_output_id, block.work_output_id)):
        raise ValueError("material and work outputs must be declared block outputs")
    parameters = {item.input_key: item for item in block.parameters}
    input_nodes = {node.input_key: node for node in block.nodes if node.operation == "INPUT"}
    for node in block.nodes:
        if node.operation == "INPUT" and node.input_key in input_nodes:
            if _dimension(node.unit) != _dimension(input_nodes[node.input_key].unit):
                raise ValueError("one input key cannot have conflicting dimensions")
    if len(parameters) != len(block.parameters) or not set(parameters).issubset(input_nodes):
        raise ValueError("parameter keys must uniquely reference input nodes")
    for parameter in block.parameters:
        if not parameter.label.strip() or _dimension(parameter.unit) != _dimension(input_nodes[parameter.input_key].unit):
            raise ValueError("parameter label and dimension must match the input")
        if parameter.status not in {"UNCONFIRMED", "PRELIMINARY", "VERIFIED"}:
            raise ValueError("invalid parameter status")
        if not isinstance(parameter.auto_apply, bool):
            raise ValueError("auto_apply must be boolean")
        minimum = _decimal(parameter.minimum) if parameter.minimum is not None else None
        maximum = _decimal(parameter.maximum) if parameter.maximum is not None else None
        default = _decimal(parameter.default) if parameter.default is not None else None
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("parameter minimum exceeds maximum")
        if default is not None and ((minimum is not None and default < minimum) or
                                    (maximum is not None and default > maximum)):
            raise ValueError("parameter default is out of range")
        if parameter.auto_apply and (default is None or not (parameter.source or "").strip()):
            raise ValueError("automatic defaults require a value and source")
    ordered: list[CalculationNode] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ValueError("calculation graph contains a cycle")
        if node_id in visited:
            return
        if node_id not in nodes:
            raise ValueError("calculation graph references a missing node")
        node = nodes[node_id]
        if node.operation not in _ARITY or len(node.inputs) != _ARITY[node.operation]:
            raise ValueError("unsupported operation or incorrect input count")
        dimension = _dimension(node.unit)
        if node.operation == "INPUT" and not (node.input_key or "").strip():
            raise ValueError("INPUT requires an explicit geometry or parameter key")
        if node.operation == "CONSTANT":
            _decimal(node.constant)
        if node.operation == "PIECEWISE":
            if not node.thresholds or len(node.thresholds) > 100:
                raise ValueError("PIECEWISE requires bounded thresholds")
            previous = None
            for threshold in node.thresholds:
                lower, upper = _decimal(threshold.lower), _decimal(threshold.upper)
                _decimal(threshold.result)
                if not isinstance(threshold.upper_inclusive, bool):
                    raise ValueError("threshold boundary must be boolean")
                if lower > upper or (lower == upper and not threshold.upper_inclusive):
                    raise ValueError("invalid threshold interval")
                if previous and (lower < _decimal(previous.upper) or
                                 (lower == _decimal(previous.upper) and previous.upper_inclusive)):
                    raise ValueError("threshold intervals overlap or are unordered")
                previous = threshold
        visiting.add(node_id)
        for dependency in node.inputs:
            visit(dependency)
        dimensions = [_dimension(nodes[item].unit) for item in node.inputs]
        if node.operation in {"ADD", "SUBTRACT"} and (dimensions[0] != dimensions[1] or dimensions[0] != dimension):
            raise ValueError("addition/subtraction dimensions do not match")
        if node.operation in {"MULTIPLY", "DIVIDE"}:
            sign = 1 if node.operation == "MULTIPLY" else -1
            if tuple(a + sign * b for a, b in zip(*dimensions)) != dimension:
                raise ValueError("multiplication/division dimensions do not match")
        if node.operation in {"CEIL", "FLOOR"} and (dimensions[0] != (0, 0) or dimension != (0, 0)):
            raise ValueError("rounding requires a dimensionless input")
        if node.operation == "LESS_THAN" and (dimensions[0] != dimensions[1] or dimension != (0, 0)):
            raise ValueError("comparison requires matching input dimensions")
        if node.operation == "IF" and (dimensions[0] != (0, 0) or dimensions[1] != dimensions[2]
                                       or dimensions[1] != dimension):
            raise ValueError("IF requires a boolean condition and matching branch dimensions")
        if node.operation == "BAR_SPACING" and (
                dimensions != [(1, 0), (1, 0), (1, 0), (0, 0), (1, 0), (1, 0)] or dimension != (1, 0)):
            raise ValueError("bar spacing requires width, cover, diameter, count and spacing limits")
        if node.operation == "REQUIRE_VALID" and dimensions[0] != dimension:
            raise ValueError("validated result must preserve the value dimension")
        if node.operation == "PRISM_VOLUME" and (dimensions != [(1, 0)] * 3 or dimension != (3, 0)):
            raise ValueError("prism requires three lengths and a volume output")
        visiting.remove(node_id)
        visited.add(node_id)
        ordered.append(node)

    for node_id in nodes:
        visit(node_id)
    return tuple(ordered)


def evaluate_block(
    block: CalculationBlock, inputs: Mapping[str, tuple[object, str]], *,
    allow_preliminary_defaults: bool = False,
) -> dict[str, CalculationValue]:
    """Evaluate independent branches; missing inputs remain local, not zero."""
    ordered = validate_block(block)
    values: dict[str, CalculationValue] = {}
    parameters = {item.input_key: item for item in block.parameters}
    with localcontext() as context:
        context.prec = 34
        context.Emax = 28
        context.Emin = -28
        for node in ordered:
            dependencies = [values[item] for item in node.inputs]
            # Only the selected IF branch is a dependency of the result.
            checked = dependencies
            if node.operation == "IF":
                checked = [dependencies[0]]
                condition = dependencies[0].value
                if not dependencies[0].errors and condition in (Decimal(0), Decimal(1)):
                    checked.append(dependencies[1] if condition else dependencies[2])
            errors = tuple(dict.fromkeys(error for item in checked for error in item.errors))
            warnings = tuple(dict.fromkeys(warning for item in checked for warning in item.warnings))
            if errors:
                values[node.id] = CalculationValue(None, node.unit, errors, warnings)
                continue
            try:
                scale = UNITS[node.unit][1]
                if node.operation == "INPUT":
                    item = inputs.get(node.input_key or "")
                    parameter = parameters.get(node.input_key or "")
                    if (item is None and parameter and parameter.auto_apply and
                            (parameter.status == "VERIFIED" or
                             (parameter.status == "PRELIMINARY" and allow_preliminary_defaults))):
                        item = (parameter.default, parameter.unit)
                        if parameter.status == "PRELIMINARY":
                            warnings = (*warnings, f"PRELIMINARY_DEFAULT:{node.input_key}")
                    if item is None:
                        values[node.id] = CalculationValue(None, node.unit, (f"MISSING_INPUT:{node.input_key}",))
                        continue
                    raw, source_unit = item
                    if _dimension(source_unit) != _dimension(node.unit):
                        raise ValueError("input dimension does not match")
                    physical = _decimal(raw) * UNITS[source_unit][1]
                    if parameter:
                        param_value = physical / UNITS[parameter.unit][1]
                        if ((parameter.minimum is not None and param_value < _decimal(parameter.minimum)) or
                                (parameter.maximum is not None and param_value > _decimal(parameter.maximum))):
                            raise ValueError("parameter is outside its allowed range")
                    value = physical / scale
                elif node.operation == "CONSTANT":
                    value = _decimal(node.constant)
                elif node.operation in {"ADD", "SUBTRACT"}:
                    left, right = (item.value * UNITS[item.unit][1] for item in dependencies)
                    value = (left + right if node.operation == "ADD" else left - right) / scale
                elif node.operation in {"MULTIPLY", "DIVIDE"}:
                    left, right = (item.value * UNITS[item.unit][1] for item in dependencies)
                    value = (left * right if node.operation == "MULTIPLY" else left / right) / scale
                elif node.operation in {"CEIL", "FLOOR"}:
                    rounding = ROUND_CEILING if node.operation == "CEIL" else ROUND_FLOOR
                    value = dependencies[0].value.to_integral_value(rounding=rounding)
                elif node.operation == "LESS_THAN":
                    left, right = (item.value * UNITS[item.unit][1] for item in dependencies)
                    value = Decimal(int(left < right))
                elif node.operation == "IF":
                    if dependencies[0].value not in (Decimal(0), Decimal(1)):
                        raise ValueError("IF requires a boolean condition")
                    selected = dependencies[1] if dependencies[0].value else dependencies[2]
                    value = selected.value * UNITS[selected.unit][1] / scale
                elif node.operation == "PRISM_VOLUME":
                    lengths = [item.value * UNITS[item.unit][1] for item in dependencies]
                    if any(item <= 0 for item in lengths):
                        raise ValueError("prism dimensions must be positive")
                    value = lengths[0] * lengths[1] * lengths[2] / scale
                elif node.operation == "BAR_SPACING":
                    width, cover, diameter, count, minimum, maximum = (
                        item.value * UNITS[item.unit][1] for item in dependencies
                    )
                    if (width <= 0 or cover < 0 or diameter <= 0 or count < 2 or
                            count != count.to_integral_value() or minimum <= 0 or maximum < minimum):
                        raise ValueError("invalid bar layout inputs")
                    clear = width - 2 * (cover + diameter / 2)
                    spacing = clear / (count - 1)
                    if clear <= 0 or spacing < minimum or spacing > maximum:
                        values[node.id] = CalculationValue(None, node.unit, (f"RULE_CONFLICT:{node.id}",), warnings)
                        continue
                    value = spacing / scale
                elif node.operation == "REQUIRE_VALID":
                    value = dependencies[0].value * UNITS[dependencies[0].unit][1] / scale
                else:
                    source = dependencies[0].value
                    threshold = next((case for case in node.thresholds if source >= _decimal(case.lower) and
                                      (source <= _decimal(case.upper) if case.upper_inclusive
                                       else source < _decimal(case.upper))), None)
                    if threshold is None:
                        values[node.id] = CalculationValue(None, node.unit, ("OUT_OF_DOMAIN",), warnings)
                        continue
                    value = _decimal(threshold.result)
                    if block.rule_status != "VERIFIED":
                        warnings = (*warnings, "PRELIMINARY_RULE")
                value = _decimal(value)
                if node.unit == "piece" and (value < 0 or value != value.to_integral_value()):
                    raise ValueError("piece quantities must be nonnegative integers")
                values[node.id] = CalculationValue(value, node.unit, warnings=warnings)
            except (DecimalException, ValueError, TypeError, KeyError):
                values[node.id] = CalculationValue(None, node.unit, (f"INVALID_INPUT:{node.id}",), warnings)
    return values


def copy_block(
    block: CalculationBlock, *, input_mapping: Mapping[str, str],
    material_id: str | None = None, work_code: str | None = None,
) -> CalculationBlock:
    """Create an independent instance; mapping geometry is always explicit."""
    validate_block(block)
    input_keys = {node.input_key for node in block.nodes if node.operation == "INPUT"}
    if set(input_mapping) != input_keys or any(not isinstance(value, str) or not value.strip()
                                                for value in input_mapping.values()):
        raise ValueError("every input must be explicitly mapped")
    identifiers = {node.id: str(uuid4()) for node in block.nodes}
    result = replace(
        block, id=str(uuid4()), material_id=material_id, work_code=work_code,
        material_requirement_id=None, work_step_id=None,
        nodes=tuple(replace(node, id=identifiers[node.id], inputs=tuple(identifiers[item] for item in node.inputs),
                            input_key=input_mapping[node.input_key] if node.operation == "INPUT" else node.input_key)
                    for node in block.nodes),
        outputs=tuple(identifiers[item] for item in block.outputs),
        parameters=tuple(replace(item, input_key=input_mapping[item.input_key]) for item in block.parameters),
        material_output_id=identifiers[block.material_output_id] if block.material_output_id else None,
        work_output_id=identifiers[block.work_output_id] if block.work_output_id else None,
    )
    validate_block(result)
    return result
