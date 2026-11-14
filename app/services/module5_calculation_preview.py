"""Preliminary material/work statement from M2 blocks and M1 price quotes.

No database writes, engineering approvals, supplier selection or price averaging
occur here. Persistent M5/M7 snapshots and authorization belong to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Literal, Mapping

from app.services.module1_calculation_price import CalculationPrice
from app.services.module1_unit_conversion_registry import UnitConversionRegistry
from app.services.module2_calculation_graph import CalculationBlock, CalculationValue, evaluate_block

PROTECTED_GEOMETRY_INPUTS = frozenset({"geometry.length", "geometry.width", "geometry.height"})


@dataclass(frozen=True)
class StatementBinding:
    id: str
    block_id: str
    kind: Literal["MATERIAL", "WORK"]
    resource_id: str | None
    output_node_id: str
    accounting_key: str
    technology_role_id: str | None = None


@dataclass(frozen=True)
class StatementLine:
    binding: StatementBinding
    quantity: Decimal | None
    unit: str
    unit_price: Decimal | None
    price_source: str
    line_amount: Decimal | None
    amount_for_total: Decimal
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    trace: tuple[tuple[str, CalculationValue], ...]


@dataclass(frozen=True)
class StatementPreview:
    materials: tuple[StatementLine, ...]
    works: tuple[StatementLine, ...]
    material_subtotal: Decimal
    work_subtotal: Decimal
    known_total: Decimal
    complete: bool
    mode: Literal["PREVIEW"] = "PREVIEW"


def calculate_statement_preview(
    blocks: tuple[CalculationBlock, ...], bindings: tuple[StatementBinding, ...],
    geometry: Mapping[str, tuple[object, str]], quotes: Mapping[tuple[str, str], CalculationPrice], *,
    allow_preliminary_defaults: bool = False,
    parameter_values: Mapping[tuple[str, str], tuple[object, str]] | None = None,
    block_issues: Mapping[str, tuple[str, ...]] | None = None,
) -> StatementPreview:
    """Calculate independent statements from exact IDs and already-resolved M1 prices."""
    by_id = {block.id: block for block in blocks}
    if len(by_id) != len(blocks) or any(not key for key in by_id):
        raise ValueError("block IDs must be unique and nonempty")
    if len({binding.id for binding in bindings}) != len(bindings):
        raise ValueError("binding IDs must be unique")
    accounting = [(binding.kind, binding.accounting_key) for binding in bindings]
    if any(not binding.id or not binding.accounting_key for binding in bindings):
        raise ValueError("binding IDs and accounting keys are required")
    if len(set(accounting)) != len(accounting):
        raise ValueError("duplicate accounting key would count the same resource role twice")
    resource_counts = Counter((binding.kind, binding.resource_id) for binding in bindings if binding.resource_id)
    supplied = parameter_values or {}
    allowed = {(block.id, parameter.input_key): parameter for block in blocks for parameter in block.parameters}
    if set(supplied) - set(allowed) or any(key in PROTECTED_GEOMETRY_INPUTS for _, key in supplied):
        raise ValueError("parameter values must belong to their calculation block")
    if set(block_issues or {}) - set(by_id):
        raise ValueError("issues must belong to a calculation block")
    evaluated = {}
    for block in blocks:
        inputs = dict(geometry)
        inputs.update({key: value for (block_id, key), value in supplied.items() if block_id == block.id})
        evaluated[block.id] = evaluate_block(block, inputs, allow_preliminary_defaults=allow_preliminary_defaults)
    contexts = {quote.context for quote in quotes.values()}
    if len({(item.currency.upper(), item.region.casefold(), item.terms.casefold(), item.as_of) for item in contexts}) > 1:
        raise ValueError("price quotes must have one comparable context")
    lines: list[StatementLine] = []
    registry = UnitConversionRegistry()
    with localcontext() as context:
        context.prec = 34
        for binding in bindings:
            if binding.kind not in {"MATERIAL", "WORK"} or binding.block_id not in by_id:
                raise ValueError("binding must reference an existing block and a valid resource kind")
            block = by_id[binding.block_id]
            if binding.output_node_id not in block.outputs:
                raise ValueError("binding must reference a declared block output")
            result = evaluated[binding.block_id][binding.output_node_id]
            quote = quotes.get((binding.kind, binding.resource_id)) if binding.resource_id else None
            issues = [*result.errors, *(block_issues or {}).get(binding.block_id, ())]
            if binding.resource_id and resource_counts[(binding.kind, binding.resource_id)] > 1:
                issues.append("POTENTIAL_DOUBLE_COUNT")
            if not binding.resource_id:
                issues.append("MATERIAL_UNRESOLVED" if binding.kind == "MATERIAL" else "WORK_UNRESOLVED")
            quantity, unit = result.value, result.unit
            if quantity is not None and quantity < 0:
                quantity = None
                issues.append("NEGATIVE_QUANTITY")
            price = quote.amount if quote is not None else None
            if quote is None or quote.source == "NO_PRICE" or price is None:
                price = None
                if binding.resource_id:
                    issues.append("NO_PRICE")
            elif not isinstance(price, Decimal) or not price.is_finite() or price <= 0:
                price = None
                issues.append("INVALID_PRICE")
            if quantity is not None and quote is not None and quote.context.base_unit != unit:
                conversion = registry.get_conversion_rule(unit, quote.context.base_unit)
                if conversion is None or conversion.source not in {"identity", "builtin"}:
                    quantity = None
                    issues.append("UNIT_CONVERSION_REQUIRED")
                else:
                    quantity *= conversion.factor
                    unit = quote.context.base_unit
            line_amount = None
            if quantity is not None and price is not None:
                line_amount = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lines.append(StatementLine(
                binding, quantity, unit, price, quote.source if quote else "NO_PRICE", line_amount,
                line_amount if line_amount is not None and not {"POTENTIAL_DOUBLE_COUNT", "TECHNOLOGY_ROLE_INVALID"}.intersection(issues)
                else Decimal("0"),
                tuple(dict.fromkeys(issues)),
                result.warnings, tuple(evaluated[binding.block_id].items()),
            ))
    materials = tuple(item for item in lines if item.binding.kind == "MATERIAL")
    works = tuple(item for item in lines if item.binding.kind == "WORK")
    material_total = sum((item.amount_for_total for item in materials), Decimal(0))
    work_total = sum((item.amount_for_total for item in works), Decimal(0))
    return StatementPreview(materials, works, material_total, work_total, material_total + work_total,
                            complete=bool(lines) and not any(item.issues for item in lines))
