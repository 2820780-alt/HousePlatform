from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class CategoryCreate(BaseModel):
    name: str
    slug: str
    parent_id: UUID | None = None
    sort_order: int = 0


class CategoryRead(BaseModel):
    id: UUID
    parent_id: UUID | None = None
    name: str
    slug: str
    level: int
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CategorySchemaUpdate(BaseModel):
    required_attributes: list | None = None
    optional_attributes: list | None = None
    comparison_rules: dict | None = None
    dedup_rules: dict | None = None
    unit_rules: dict | None = None
    normalization_rules: dict | None = None


class CategorySchemaRead(BaseModel):
    id: UUID
    category_id: UUID
    required_attributes: list
    optional_attributes: list
    comparison_rules: dict
    dedup_rules: dict
    unit_rules: dict
    normalization_rules: dict

    model_config = {"from_attributes": True}
