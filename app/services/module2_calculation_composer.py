"""Compose bounded calculation graphs from structured UI steps, never user code."""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import uuid4

from app.services.module2_calculation_graph import BlockParameter, CalculationBlock, CalculationNode, UNITS, validate_block


OPERATIONS = {
    "INPUT": 0, "CONSTANT": 0, "ADD": 2, "SUBTRACT": 2, "MULTIPLY": 2,
    "DIVIDE": 2, "CEIL": 1, "FLOOR": 1, "LESS_THAN": 2, "IF": 3, "PRISM_VOLUME": 3,
}
GEOMETRY_INPUTS = {"geometry.length", "geometry.width", "geometry.height"}


@dataclass(frozen=True)
class ComposerStep:
    label: str
    operation: str
    unit: str
    references: tuple[int, ...] = ()
    source: str = ""
    constant: Decimal | None = None


def compose_block(name: str, steps: tuple[ComposerStep, ...], *, material_step: int | None,
                  work_step: int | None, rule_source: str | None = None) -> CalculationBlock:
    if not name.strip() or len(name) > 255 or not 1 <= len(steps) <= 24:
        raise ValueError("a name and 1..24 steps are required")
    ids = [str(uuid4()) for _ in steps]
    nodes, parameters = [], []
    for index, step in enumerate(steps):
        if not step.label.strip() or len(step.label) > 255 or step.operation not in OPERATIONS:
            raise ValueError("each step requires a name and supported operation")
        if len(step.references) != OPERATIONS[step.operation] or any(
            isinstance(ref, bool) or not isinstance(ref, int) or ref < 1 or ref > index for ref in step.references
        ):
            raise ValueError("steps may only refer to earlier steps")
        key = None
        if step.operation == "INPUT":
            if step.source == "PARAMETER":
                key = f"parameter.{uuid4().hex}"
                parameters.append(BlockParameter(key, step.label.strip(), step.unit))
            elif step.source in GEOMETRY_INPUTS:
                if step.unit not in UNITS or UNITS[step.unit][0] != (1, 0):
                    raise ValueError("geometry dimensions require a length unit")
                key = step.source
            else:
                raise ValueError("select a geometry input or parameter")
        if step.operation == "CONSTANT" and not (rule_source or "").strip():
            raise ValueError("a constant requires a rule source")
        nodes.append(CalculationNode(ids[index], step.operation, step.unit,
                     inputs=tuple(ids[ref - 1] for ref in step.references), input_key=key,
                     constant=step.constant if step.operation == "CONSTANT" else None, label=step.label.strip()))
    selected = [value for value in (material_step, work_step) if value is not None]
    if not selected or any(isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > len(ids)
                           for value in selected):
        raise ValueError("choose an existing output step")
    material_id = ids[material_step - 1] if material_step is not None else None
    work_id = ids[work_step - 1] if work_step is not None else None
    source = (rule_source or "").strip() or None
    block = CalculationBlock(str(uuid4()), name.strip(), tuple(nodes), tuple(dict.fromkeys(
        item for item in (material_id, work_id) if item)), tuple(parameters),
        material_output_id=material_id, work_output_id=work_id, rule_source=source,
        rule_status="PRELIMINARY" if source else "UNCONFIRMED")
    validate_block(block)
    return block


def composer_form_data(block: CalculationBlock) -> dict | None:
    """Expose supported graphs as ordered, named form steps without raw JSON editing."""
    nodes = validate_block(block)
    if len(nodes) > 12 or any(node.operation not in OPERATIONS for node in nodes):
        return None
    parameter_keys = {parameter.input_key for parameter in block.parameters}
    if any(node.operation == "INPUT" and node.input_key not in GEOMETRY_INPUTS | parameter_keys for node in nodes):
        return None
    positions = {node.id: index + 1 for index, node in enumerate(nodes)}
    return {"steps": [{"label": node.label or f"Шаг {index + 1}", "operation": node.operation,
                        "unit": node.unit, "source": node.input_key if node.input_key in GEOMETRY_INPUTS else "PARAMETER",
                        "constant": str(node.constant) if node.constant is not None else "",
                        "references": [positions[item] for item in node.inputs]}
                       for index, node in enumerate(nodes)],
            "material_step": positions.get(block.material_output_id), "work_step": positions.get(block.work_output_id)}


def recompose_block(original: CalculationBlock, updated: CalculationBlock) -> CalculationBlock:
    """Keep defaults for unchanged input slots; every changed rule needs review."""
    old_nodes = validate_block(original)
    old_parameters = {item.input_key: item for item in original.parameters}
    parameters = {item.input_key: item for item in updated.parameters}
    nodes = list(updated.nodes)
    for index, node in enumerate(nodes):
        if index >= len(old_nodes) or node.operation != "INPUT" or old_nodes[index].operation != "INPUT":
            continue
        old = old_nodes[index]
        old_parameter = old_parameters.get(old.input_key)
        same_geometry = node.input_key == old.input_key and node.input_key in GEOMETRY_INPUTS
        same_parameter = (node.input_key in parameters and old_parameter is not None
                          and old.input_key not in GEOMETRY_INPUTS)
        if old_parameter and old.unit == node.unit and (same_geometry or same_parameter):
            if same_parameter:
                new_parameter = parameters.pop(node.input_key)
                nodes[index] = replace(node, input_key=old.input_key)
                parameters[old.input_key] = replace(old_parameter, label=new_parameter.label)
            else:
                parameters[old.input_key] = old_parameter
    result = replace(updated, id=original.id, nodes=tuple(nodes), parameters=tuple(parameters.values()),
                     rule_status="PRELIMINARY" if updated.rule_source else "UNCONFIRMED")
    validate_block(result)
    return result
