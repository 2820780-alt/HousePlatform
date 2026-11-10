"""Read-only foundation offer queues; no tasks, products or prices are created."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import CatalogProductStatus, MaterialStatus
from app.models.material import Material
from app.models.material_attribute import MaterialAttribute
from app.services.module1_foundation_target_package import PACKAGE


@dataclass(frozen=True)
class MarketQueueItem:
    material_id: UUID
    material_name: str
    material_status: str
    queue: str
    reason: str
    active_product_count: int
    priced_product_count: int
    supplier_price_count: int
    expired_supplier_price_count: int
    automatic_matching_allowed: bool


def _positive_price(value: Any) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value > 0


def classify_market_needs(material: Any, products: Iterable[Any], supplier_prices: Iterable[Any], *, as_of: date):
    """Classify existing records only; technical review and sourcing remain separate."""
    if not isinstance(as_of, date):
        raise ValueError("an explicit assessment date is required")
    if material.status in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED}:
        return ()
    active_products = tuple(item for item in products if item.status == CatalogProductStatus.ACTIVE)
    priced_products = tuple(item for item in active_products if _positive_price(item.price))
    priced_supplier_records = tuple(item for item in supplier_prices if _positive_price(item.price))
    expired = sum(bool(item.valid_until and item.valid_until < as_of) for item in priced_supplier_records)
    verified = material.status == MaterialStatus.VERIFIED
    common = {
        "material_id": material.id, "material_name": material.canonical_name,
        "material_status": material.status.value, "active_product_count": len(active_products),
        "priced_product_count": len(priced_products), "supplier_price_count": len(priced_supplier_records),
        "expired_supplier_price_count": expired, "automatic_matching_allowed": verified,
    }
    result = []
    if not active_products and not priced_supplier_records:
        result.append(MarketQueueItem(queue="SEARCH", reason="NO_KNOWN_OFFER", **common))
    elif any(not _positive_price(item.price) or not item.external_url for item in active_products):
        result.append(MarketQueueItem(queue="SEARCH", reason="OFFER_INFORMATION_INCOMPLETE", **common))
    if priced_products or priced_supplier_records:
        result.append(MarketQueueItem(queue="REFRESH", reason="KNOWN_PRICE_REQUIRES_REVIEW", **common))
    return tuple(result)


async def build_foundation_market_queues(db: AsyncSession, *, as_of: date) -> tuple[MarketQueueItem, ...]:
    """Project existing target and offer data; SourceTask and gap records are untouched."""
    statement = (
        select(Material)
        .join(MaterialAttribute, MaterialAttribute.material_id == Material.id)
        .where(MaterialAttribute.attribute_name == "registry_origin", MaterialAttribute.attribute_value == PACKAGE)
        .where(Material.status.not_in((MaterialStatus.ARCHIVED, MaterialStatus.REJECTED)))
        .options(selectinload(Material.catalog_products), selectinload(Material.supplier_prices))
        .order_by(Material.canonical_name, Material.id)
    )
    materials = (await db.scalars(statement)).unique().all()
    return tuple(item for material in materials for item in classify_market_needs(
        material, material.catalog_products, material.supplier_prices, as_of=as_of))
