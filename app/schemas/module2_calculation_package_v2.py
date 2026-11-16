"""Versioned M2 calculation inputs captured by an M5 preview."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.module2_calculation_block import CalculationBlockDefinition


class CalculationPackageBlockV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    version: int = Field(ge=1)
    position: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    material_id: UUID | None = None
    work_code: str | None = Field(default=None, max_length=120)
    definition: CalculationBlockDefinition


class CalculationPackageV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["2"] = "2"
    technology_id: UUID
    technology_code: str = Field(min_length=1, max_length=120)
    technology_revision: int = Field(ge=1)
    technology_status: Literal["DRAFT", "ACTIVE"]
    blocks: tuple[CalculationPackageBlockV2, ...]
