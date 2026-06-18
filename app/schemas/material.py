from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import MaterialStatus


class MaterialCreate(BaseModel):
    canonical_name: str
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    manufacturer_id: UUID | None = None
    brand_id: UUID | None = None
    base_unit_id: UUID | None = None
    brand: str | None = None
    manufacturer: str | None = None
    description: str | None = None


class MaterialUpdate(BaseModel):
    canonical_name: str | None = None
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    manufacturer_id: UUID | None = None
    brand_id: UUID | None = None
    base_unit_id: UUID | None = None
    brand: str | None = None
    manufacturer: str | None = None
    description: str | None = None
    status: MaterialStatus | None = None


class MaterialRead(BaseModel):
    id: UUID
    canonical_name: str
    category_id: UUID | None = None
    subcategory_id: UUID | None = None
    manufacturer_id: UUID | None = None
    brand_id: UUID | None = None
    base_unit_id: UUID | None = None
    brand: str | None = None
    manufacturer: str | None = None
    description: str | None = None
    status: MaterialStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MaterialAttributeRead(BaseModel):
    id: UUID
    attribute_name: str
    attribute_value: str
    unit_id: UUID | None = None
    sort_order: int

    model_config = {"from_attributes": True}
