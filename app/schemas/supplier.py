from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from app.models.enums import SupplierStatus
from app.schemas.material_hub_contracts import AccountLinkStatus, AccountSyncStatus


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
    contacts: dict | None = None
    manager_contacts: list[dict] | None = None
    bank_details: dict | None = None
    profile: dict | None = None
    supplier_account_id: UUID | None = None
    account_link_status: AccountLinkStatus | None = None
    verified_account: bool | None = None
    linked_at: datetime | None = None
    sync_status: AccountSyncStatus | None = None
    last_synced_at: datetime | None = None
    supplier_region_id: UUID | None = None
    supplier_city_id: UUID | None = None
    delivery_zone_ids: list[UUID] | None = None
    pickup_available: bool | None = None
    delivery_available: bool | None = None
    region_status: str | None = None


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
    contacts: dict | None = None
    manager_contacts: list[dict] | None = None
    bank_details: dict | None = None
    profile: dict | None = None
    supplier_account_id: UUID | None = None
    account_link_status: AccountLinkStatus | None = None
    verified_account: bool | None = None
    linked_at: datetime | None = None
    sync_status: AccountSyncStatus | None = None
    last_synced_at: datetime | None = None
    supplier_region_id: UUID | None = None
    supplier_city_id: UUID | None = None
    delivery_zone_ids: list[UUID] | None = None
    pickup_available: bool | None = None
    delivery_available: bool | None = None
    region_status: str | None = None


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
    contacts: dict | None = None
    manager_contacts: list[dict] | None = None
    bank_details: dict | None = None
    profile: dict | None = None
    supplier_account_id: UUID | None = None
    account_link_status: AccountLinkStatus | None = None
    verified_account: bool | None = None
    linked_at: datetime | None = None
    sync_status: AccountSyncStatus | None = None
    last_synced_at: datetime | None = None
    supplier_region_id: UUID | None = None
    supplier_city_id: UUID | None = None
    delivery_zone_ids: list[UUID] | None = None
    pickup_available: bool | None = None
    delivery_available: bool | None = None
    region_status: str | None = None
    status: SupplierStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierStatusUpdate(BaseModel):
    status: SupplierStatus
