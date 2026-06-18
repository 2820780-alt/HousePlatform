from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class BranchCreate(BaseModel):
    name: str | None = None
    city: str
    region: str | None = None
    address: str | None = None
    contacts: dict | None = None
    delivery_zone: str | None = None
    is_main: bool = False


class BranchUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    region: str | None = None
    address: str | None = None
    contacts: dict | None = None
    delivery_zone: str | None = None
    is_main: bool | None = None


class BranchRead(BaseModel):
    id: UUID
    supplier_id: UUID
    name: str | None = None
    city: str
    region: str | None = None
    address: str | None = None
    contacts: dict | None = None
    delivery_zone: str | None = None
    is_main: bool
    created_at: datetime

    model_config = {"from_attributes": True}
