from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from app.models.enums import SupplierStatus


class SupplierCreate(BaseModel):
    name: str
    inn: str | None = None
    site: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = "Россия"
    address: str | None = None
    description: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    inn: str | None = None
    site: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    address: str | None = None
    description: str | None = None


class SupplierRead(BaseModel):
    id: UUID
    name: str
    inn: str | None = None
    site: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    address: str | None = None
    description: str | None = None
    status: SupplierStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierStatusUpdate(BaseModel):
    status: SupplierStatus
