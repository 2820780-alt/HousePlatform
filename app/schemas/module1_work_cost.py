from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ProviderWorkCostOfferCreate(BaseModel):
    workCode: str
    region: str
    pricingMode: str
    pricingUnit: str
    currency: str = "RUB"
    fixedAmount: Decimal | None = None
    minimumAmount: Decimal | None = None
    maximumAmount: Decimal | None = None
    validFrom: date | None = None
    validUntil: date | None = None
    status: str = "draft"
    comment: str | None = None


class ProviderWorkCostOfferUpdate(ProviderWorkCostOfferCreate):
    pass


class ProviderWorkCostOfferRead(BaseModel):
    id: UUID
    workCode: str
    workName: str | None = None
    workGroup: str | None = None
    ownerUserId: UUID
    region: str
    pricingMode: str
    fixedAmount: Decimal | None = None
    minimumAmount: Decimal | None = None
    maximumAmount: Decimal | None = None
    currency: str
    pricingUnit: str
    validFrom: date | None = None
    validUntil: date | None = None
    status: str
    comment: str | None = None
    createdAt: datetime
    updatedAt: datetime
