"""Append-only manual M1 price revisions; callers enforce their existing RBAC."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module1_work_item import ManualCalculationPriceRevision, WorkCatalogItem
from app.models.unit import Unit
from app.services.audit_service import log_event
from app.services.module1_calculation_price import CalculationPrice, CalculationPriceContext, PriceCandidate, calculate_price


def _context_text(value: str) -> str:
    result = " ".join(value.split()).casefold()
    if not result or len(result) > 255:
        raise ValueError("region and comparable terms are required")
    return result


def _money(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (bool, float)):
        raise ValueError("manual price must be an exact decimal")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("manual price must be an exact decimal") from None
    if not amount.is_finite() or amount <= 0 or amount.adjusted() > 13 or amount.as_tuple().exponent < -4:
        raise ValueError("manual price must be positive and fit numeric(18,4)")
    return amount


async def _owner(
    db: AsyncSession, *, material_id: uuid.UUID | None, work_code: str | None, lock: bool,
) -> str:
    if (material_id is None) == (work_code is None):
        raise ValueError("choose exactly one material or work")
    if material_id is not None:
        statement = select(Material).where(Material.id == material_id)
        material = await db.scalar(statement.with_for_update() if lock else statement)
        if material is None or material.status in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED}:
            raise ValueError("material is missing or archived")
        unit = await db.get(Unit, material.base_unit_id) if material.base_unit_id else None
        if unit is None:
            raise ValueError("material base unit is required")
        return unit.abbreviation
    statement = select(WorkCatalogItem).where(WorkCatalogItem.work_code == work_code)
    work = await db.scalar(statement.with_for_update() if lock else statement)
    if work is None or work.status == "ARCHIVED":
        raise ValueError("work is missing or archived")
    return work.default_unit


async def append_manual_price(
    db: AsyncSession, *, material_id: uuid.UUID | None = None, work_code: str | None = None,
    amount: Decimal | None, region: str, terms: str, effective_from: date,
    actor_id: uuid.UUID | None,
) -> ManualCalculationPriceRevision:
    """Store a revision; None explicitly clears the manual fallback from this date."""
    if not isinstance(effective_from, date):
        raise ValueError("effective_from must be a date")
    base_unit = await _owner(db, material_id=material_id, work_code=work_code, lock=True)
    region, terms = _context_text(region), _context_text(terms)
    amount = _money(amount)
    filters = [ManualCalculationPriceRevision.currency == "RUB", ManualCalculationPriceRevision.unit == base_unit,
               ManualCalculationPriceRevision.region == region, ManualCalculationPriceRevision.terms == terms]
    filters.append(ManualCalculationPriceRevision.material_id == material_id if material_id is not None
                   else ManualCalculationPriceRevision.work_code == work_code)
    previous = await db.scalar(select(func.max(ManualCalculationPriceRevision.version)).where(*filters))
    revision = ManualCalculationPriceRevision(
        id=uuid.uuid4(), material_id=material_id, work_code=work_code, amount=amount, currency="RUB",
        unit=base_unit, region=region, terms=terms, effective_from=effective_from,
        version=(previous or 0) + 1, created_by_user_id=actor_id,
    )
    db.add(revision)
    await db.flush()
    await log_event(db, "M1_MANUAL_CALCULATION_PRICE_REVISED", "ManualCalculationPriceRevision", revision.id,
                    actor_id, {"material_id": str(material_id or ""), "work_code": work_code,
                               "version": revision.version, "cleared": amount is None})
    return revision


async def quote_calculation_price(
    db: AsyncSession, *, material_id: uuid.UUID | None = None, work_code: str | None = None,
    region: str, terms: str, as_of: date, offers: Iterable[PriceCandidate],
) -> CalculationPrice:
    """Resolve manual fallback and eligible candidate prices in one M1 service."""
    base_unit = await _owner(db, material_id=material_id, work_code=work_code, lock=False)
    region, terms = _context_text(region), _context_text(terms)
    filters = [ManualCalculationPriceRevision.currency == "RUB", ManualCalculationPriceRevision.unit == base_unit,
               ManualCalculationPriceRevision.region == region, ManualCalculationPriceRevision.terms == terms,
               ManualCalculationPriceRevision.effective_from <= as_of]
    filters.append(ManualCalculationPriceRevision.material_id == material_id if material_id is not None
                   else ManualCalculationPriceRevision.work_code == work_code)
    latest = await db.scalar(select(ManualCalculationPriceRevision).where(*filters).order_by(
        ManualCalculationPriceRevision.effective_from.desc(), ManualCalculationPriceRevision.version.desc()).limit(1))
    return calculate_price(CalculationPriceContext(base_unit, "RUB", region, terms, as_of), offers,
                           manual_price=latest.amount if latest else None)
