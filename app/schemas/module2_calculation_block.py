from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _exact(value):
    if isinstance(value, (float, bool)):
        raise ValueError("decimal values must be strings or integers, not float or boolean")
    return value


class ThresholdPayload(_StrictModel):
    lower: Decimal
    upper: Decimal
    result: Decimal
    upper_inclusive: StrictBool = False

    _exact_values = field_validator("lower", "upper", "result", mode="before")(_exact)


class NodePayload(_StrictModel):
    id: str = Field(min_length=1, max_length=120)
    operation: str = Field(min_length=1, max_length=40)
    unit: str = Field(min_length=1, max_length=40)
    inputs: tuple[str, ...] = Field(default=(), max_length=6)
    input_key: str | None = Field(default=None, max_length=160)
    constant: Decimal | None = None
    thresholds: tuple[ThresholdPayload, ...] = Field(default=(), max_length=100)
    label: str | None = Field(default=None, max_length=255)

    _exact_constant = field_validator("constant", mode="before")(_exact)


class ParameterPayload(_StrictModel):
    input_key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=255)
    unit: str = Field(min_length=1, max_length=40)
    default: Decimal | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    source: str | None = Field(default=None, max_length=1000)
    status: Literal["UNCONFIRMED", "PRELIMINARY", "VERIFIED"] = "UNCONFIRMED"
    auto_apply: StrictBool = False

    _exact_values = field_validator("default", "minimum", "maximum", mode="before")(_exact)


class CalculationBlockDefinition(_StrictModel):
    schema_version: Literal[1] = 1
    nodes: tuple[NodePayload, ...] = Field(min_length=1, max_length=256)
    outputs: tuple[str, ...] = Field(min_length=1, max_length=256)
    parameters: tuple[ParameterPayload, ...] = Field(default=(), max_length=256)
    material_output_id: str | None = Field(default=None, max_length=120)
    work_output_id: str | None = Field(default=None, max_length=120)
    rule_source: str | None = Field(default=None, max_length=1000)
    rule_status: Literal["UNCONFIRMED", "PRELIMINARY", "VERIFIED"] = "UNCONFIRMED"
    material_requirement_id: str | None = Field(default=None, max_length=36)
    work_step_id: str | None = Field(default=None, max_length=36)
