from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


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


class ProviderWorkCostMarketReferenceRead(BaseModel):
    median: Decimal
    q1: Decimal
    q3: Decimal
    lowerBound: Decimal
    upperBound: Decimal


class ProviderWorkCostMarketSanityRead(BaseModel):
    status: str
    statusLabel: str
    comparableOfferCount: int
    reason: str
    explanation: str
    asOf: date
    referenceStats: ProviderWorkCostMarketReferenceRead | None = None


class ProviderWorkCostOfferRead(BaseModel):
    id: UUID
    workCode: str
    workName: str | None = None
    workGroup: str | None = None
    workTitle: str | None = None
    workGroupTitle: str | None = None
    ownerUserId: UUID
    ownerDisplayName: str | None = None
    region: str
    regionDisplayName: str | None = None
    pricingMode: str
    pricingModeLabel: str | None = None
    fixedAmount: Decimal | None = None
    minimumAmount: Decimal | None = None
    maximumAmount: Decimal | None = None
    currency: str
    pricingUnit: str
    pricingUnitLabel: str | None = None
    priceLabel: str | None = None
    validFrom: date | None = None
    validUntil: date | None = None
    validityLabel: str | None = None
    status: str
    statusLabel: str | None = None
    qualityFlags: list[dict[str, Any]] = Field(default_factory=list)
    marketSanity: ProviderWorkCostMarketSanityRead | None = None
    canEdit: bool = False
    canActivate: bool = False
    canDeactivate: bool = False
    comment: str | None = None
    createdAt: datetime
    updatedAt: datetime
