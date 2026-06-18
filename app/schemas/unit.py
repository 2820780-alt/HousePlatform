from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from app.models.enums import UnitType


class UnitCreate(BaseModel):
    name: str
    abbreviation: str
    unit_type: UnitType
    is_base: bool = False


class UnitRead(BaseModel):
    id: UUID
    name: str
    abbreviation: str
    unit_type: UnitType
    is_base: bool

    model_config = {"from_attributes": True}


class UnitAliasCreate(BaseModel):
    alias: str


class UnitAliasRead(BaseModel):
    id: UUID
    unit_id: UUID
    alias: str

    model_config = {"from_attributes": True}


class UnitConversionCreate(BaseModel):
    from_unit_id: UUID
    to_unit_id: UUID
    factor: Decimal
    condition: str | None = None
    material_category_id: UUID | None = None
    material_id: UUID | None = None


class UnitConversionRead(BaseModel):
    id: UUID
    from_unit_id: UUID
    to_unit_id: UUID
    factor: Decimal
    condition: str | None = None

    model_config = {"from_attributes": True}
