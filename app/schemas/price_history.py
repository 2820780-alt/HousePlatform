from pydantic import BaseModel
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID


class PriceHistoryRead(BaseModel):
    id: UUID
    material_id: UUID
    catalog_product_id: UUID | None = None
    source_id: UUID | None = None
    supplier_id: UUID | None = None
    region: str | None = None
    price: Decimal
    currency: str
    unit: str | None = None
    availability: str | None = None
    collected_at: datetime
    price_date: date | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
