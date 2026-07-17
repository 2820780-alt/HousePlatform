from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import PaginatedResponse
from app.schemas.module1_work_cost import (
    ProviderWorkCostOfferCreate,
    ProviderWorkCostOfferRead,
    ProviderWorkCostOfferUpdate,
)
from app.services.module1_provider_work_cost_offers import (
    ProviderWorkCostOfferPayload,
    create_provider_work_cost_offer,
    deactivate_provider_work_cost_offer,
    get_provider_work_cost_offer,
    list_provider_work_cost_offers,
    list_work_catalog_options,
    provider_work_cost_offer_to_dict,
    update_provider_work_cost_offer,
)
from app.services.module1_work_cost_export_contract import (
    build_work_cost_offer_export_package,
    work_cost_export_package_to_dict,
)


router = APIRouter(prefix="/admin/material-hub/work-cost-offers", tags=["module1-work-cost-offers"])


@router.post("", response_model=ProviderWorkCostOfferRead, status_code=201)
async def create_work_cost_offer(data: ProviderWorkCostOfferCreate, db: DBSession, user: CurrentUser):
    offer = await create_provider_work_cost_offer(db, _payload_from_schema(data), user)
    return provider_work_cost_offer_to_dict(offer, user)


@router.get("", response_model=PaginatedResponse[ProviderWorkCostOfferRead])
async def list_work_cost_offers(
    db: DBSession,
    user: CurrentUser,
    workCode: str | None = None,
    ownerUserId: UUID | None = None,
    region: str | None = None,
    status: str | None = None,
    pricingMode: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    result = await list_provider_work_cost_offers(
        db,
        user,
        work_code=workCode,
        owner_user_id=ownerUserId,
        region=region,
        status=status,
        pricing_mode=pricingMode,
        offset=offset,
        limit=limit,
    )
    return PaginatedResponse(
        items=[provider_work_cost_offer_to_dict(item, user) for item in result.items],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.get("/work-catalog")
async def list_work_cost_catalog(user: CurrentUser):
    return {"items": list(list_work_catalog_options())}


@router.get("/export-preview")
async def preview_work_cost_offer_export(
    db: DBSession,
    user: CurrentUser,
    workCode: str | None = None,
    region: str | None = None,
    providerUserId: UUID | None = None,
    currency: str | None = None,
    pricingUnit: str | None = None,
    updatedSince: datetime | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    package = await build_work_cost_offer_export_package(
        db,
        user,
        work_code=workCode,
        region=region,
        provider_user_id=providerUserId,
        currency=currency,
        pricing_unit=pricingUnit,
        updated_since=updatedSince,
        offset=offset,
        limit=limit,
    )
    return work_cost_export_package_to_dict(package)


@router.get("/{offer_id}", response_model=ProviderWorkCostOfferRead)
async def get_work_cost_offer(offer_id: UUID, db: DBSession, user: CurrentUser):
    offer = await get_provider_work_cost_offer(db, offer_id, user)
    return provider_work_cost_offer_to_dict(offer, user)


@router.put("/{offer_id}", response_model=ProviderWorkCostOfferRead)
async def update_work_cost_offer(
    offer_id: UUID,
    data: ProviderWorkCostOfferUpdate,
    db: DBSession,
    user: CurrentUser,
):
    offer = await update_provider_work_cost_offer(db, offer_id, _payload_from_schema(data), user)
    return provider_work_cost_offer_to_dict(offer, user)


@router.post("/{offer_id}/deactivate", response_model=ProviderWorkCostOfferRead)
async def deactivate_work_cost_offer(offer_id: UUID, db: DBSession, user: CurrentUser):
    offer = await deactivate_provider_work_cost_offer(db, offer_id, user)
    return provider_work_cost_offer_to_dict(offer, user)


def _payload_from_schema(data: ProviderWorkCostOfferCreate | ProviderWorkCostOfferUpdate) -> ProviderWorkCostOfferPayload:
    return ProviderWorkCostOfferPayload(
        work_code=data.workCode,
        region=data.region,
        pricing_mode=data.pricingMode,
        pricing_unit=data.pricingUnit,
        currency=data.currency,
        fixed_amount=data.fixedAmount,
        minimum_amount=data.minimumAmount,
        maximum_amount=data.maximumAmount,
        valid_from=data.validFrom,
        valid_until=data.validUntil,
        status=data.status,
        comment=data.comment,
    )
