"""Review current offers before allowing them into an M1 calculation quote."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_guard import require_permission
from app.models.module1_offer_qualification import CalculationOfferQualification
from app.models.catalog_product import CatalogProduct
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.supplier_price import SupplierPrice
from app.models.supplier import Supplier
from app.models.enums import CatalogProductStatus, SupplierStatus
from app.services.audit_service import log_event
from app.services.module1_calculation_price import PriceCandidate
from app.services.module1_manual_calculation_price import quote_calculation_price
from app.services.module1_provider_work_cost_offers import _apply_list_permissions

MODULE1_CODE = "MODULE_01_MATERIAL_HUB"


def _material_offer_context_valid(offer: SupplierPrice, supplier: Supplier | None,
                                  product: CatalogProduct | None) -> bool:
    # Quantity is not part of the quote context, so minimum-order terms cannot be compared.
    if not supplier or supplier.status == SupplierStatus.BLOCKED or offer.min_order_quantity is not None:
        return False
    if offer.catalog_product_id is not None:
        return bool(product and product.status == CatalogProductStatus.ACTIVE
                    and product.material_id == offer.material_id)
    return True


def offer_fingerprint(offer: SupplierPrice | ProviderWorkCostOffer) -> str:
    """Only a price change preserves qualification; identity/terms changes do not."""
    if isinstance(offer, SupplierPrice):
        fields = ("id", "supplier_id", "material_id", "catalog_product_id", "unit", "currency", "region",
                  "availability", "min_order_quantity", "delivery_terms", "valid_until")
    elif isinstance(offer, ProviderWorkCostOffer):
        fields = ("id", "owner_user_id", "work_code", "pricing_mode", "pricing_unit", "currency", "region",
                  "valid_from", "valid_until", "status", "comment")
    else:
        raise ValueError("unsupported offer type")
    payload = {name: str(getattr(offer, name)) if getattr(offer, name) is not None else None for name in fields}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


async def review_offer(
    db: AsyncSession, *, supplier_price_id: uuid.UUID | None = None, work_offer_id: uuid.UUID | None = None,
    terms: str, status: str, actor: object,
    base_units_per_sale_unit: Decimal | None = None, conversion_source: str | None = None,
) -> CalculationOfferQualification:
    """Append an explicit administrator review of the offer's identity and terms."""
    require_permission(actor, MODULE1_CODE, "ADMIN")
    actor_id = getattr(actor, "id", None)
    if (supplier_price_id is None) == (work_offer_id is None):
        raise ValueError("select exactly one offer")
    terms = " ".join(terms.split()).casefold()
    if not terms or len(terms) > 255 or status not in {"CONFIRMED", "WITHDRAWN"}:
        raise ValueError("comparable terms and review status are required")
    if base_units_per_sale_unit is not None:
        if isinstance(base_units_per_sale_unit, (float, bool)):
            raise ValueError("conversion must be exact")
        try:
            value = Decimal(str(base_units_per_sale_unit))
        except (InvalidOperation, ValueError):
            raise ValueError("conversion must be exact") from None
        if (not value.is_finite() or value <= 0 or value.adjusted() > 15 or value.as_tuple().exponent < -8 or
                not (conversion_source or "").strip()):
            raise ValueError("conversion requires a positive value and a source")
        base_units_per_sale_unit = value
    model = SupplierPrice if supplier_price_id else ProviderWorkCostOffer
    offer_id = supplier_price_id or work_offer_id
    offer = await db.scalar(select(model).where(model.id == offer_id).with_for_update())
    if offer is None:
        raise ValueError("offer not found")
    owner_filter = (CalculationOfferQualification.supplier_price_id == supplier_price_id if supplier_price_id
                    else CalculationOfferQualification.work_offer_id == work_offer_id)
    version = (await db.scalar(select(func.max(CalculationOfferQualification.version)).where(owner_filter)) or 0) + 1
    review = CalculationOfferQualification(
        id=uuid.uuid4(), supplier_price_id=supplier_price_id, work_offer_id=work_offer_id, version=version,
        status=status, terms=terms, offer_fingerprint=offer_fingerprint(offer),
        base_units_per_sale_unit=base_units_per_sale_unit, conversion_source=conversion_source,
        reviewed_by_user_id=actor_id,
    )
    db.add(review)
    await db.flush()
    await log_event(db, "M1_CALCULATION_OFFER_REVIEWED", "CalculationOfferQualification", review.id, actor_id,
                    {"version": version, "status": status})
    return review


async def quote_current_offers(
    db: AsyncSession, *, material_id: uuid.UUID | None = None, work_code: str | None = None,
    region: str, terms: str, as_of: date, actor: object,
):
    """Query offers server-side; historical prices need a separate immutable snapshot."""
    require_permission(actor, MODULE1_CODE, "VIEW")
    if (material_id is None) == (work_code is None):
        raise ValueError("select exactly one material or work")
    if as_of != date.today():
        raise ValueError("historical offer quotes require an immutable price snapshot")
    is_material = material_id is not None
    model = SupplierPrice if is_material else ProviderWorkCostOffer
    owner = model.material_id == material_id if is_material else model.work_code == work_code
    query = select(model).where(owner)
    if not is_material:
        query = _apply_list_permissions(query, actor, owner_user_id=None)
    offers = (await db.scalars(query)).all()
    candidates = []
    for offer in offers:
        owner_filter = (CalculationOfferQualification.supplier_price_id == offer.id if is_material
                        else CalculationOfferQualification.work_offer_id == offer.id)
        review = await db.scalar(select(CalculationOfferQualification).where(owner_filter).order_by(
            CalculationOfferQualification.version.desc()).limit(1))
        confirmed = bool(review and review.status == "CONFIRMED" and review.offer_fingerprint == offer_fingerprint(offer))
        available = ((offer.availability or "").strip().casefold() in {"available", "in_stock", "в наличии", "есть в наличии"}
                     if is_material else offer.status == "active")
        if is_material:
            supplier = await db.get(Supplier, offer.supplier_id)
            product = await db.get(CatalogProduct, offer.catalog_product_id) if offer.catalog_product_id else None
            available = bool(available and _material_offer_context_valid(offer, supplier, product))
        candidates.append(PriceCandidate(
            str(offer.id), offer.price if is_material else offer.fixed_amount,
            (offer.unit or "") if is_material else offer.pricing_unit, offer.currency or "",
            offer.region or "", review.terms if review else "", "active" if available else "inactive", confirmed,
            valid_from=None if is_material else offer.valid_from, valid_until=offer.valid_until,
            pricing_mode="fixed" if is_material else offer.pricing_mode,
            base_units_per_sale_unit=review.base_units_per_sale_unit if review else None,
            conversion_source=review.conversion_source if review else None,
        ))
    return await quote_calculation_price(db, material_id=material_id, work_code=work_code,
                                         region=region, terms=terms, as_of=as_of, offers=candidates)
