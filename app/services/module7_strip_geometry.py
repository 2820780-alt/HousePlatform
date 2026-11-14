"""Minimal M7 geometry with explicit revision and owner checks."""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_guard import require_permission
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.models.module7_geometry import DigitalHouseObject, StripGeometryRevision
from app.services.audit_service import log_event

MODULE7_CODE = "MODULE_07_DIGITAL_HOUSE"


def _length(value: object) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValueError("dimensions must be exact decimals")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("dimensions must be exact decimals") from None
    if not result.is_finite() or result <= 0 or result.adjusted() > 9 or result.as_tuple().exponent < -6:
        raise ValueError("dimensions must be positive and fit six decimal places")
    return result


async def _technology(db: AsyncSession, technology_id: uuid.UUID, actor: object) -> Technology:
    technology = await db.get(Technology, technology_id)
    if technology is None or technology.status not in {"ACTIVE", "DRAFT"}:
        raise ValueError("technology revision is unavailable")
    require_permission(actor, MODULE2_OWNER_CODE, "EDIT" if technology.status == "DRAFT" else "VIEW")
    return technology


async def create_object(db: AsyncSession, *, actor: object, name: str) -> DigitalHouseObject:
    require_permission(actor, MODULE7_CODE, "CREATE")
    owner_id = getattr(actor, "id", None)
    name = " ".join(name.split())
    if not owner_id or not name or len(name) > 255:
        raise ValueError("object name and authenticated owner are required")
    item = DigitalHouseObject(id=uuid.uuid4(), owner_user_id=owner_id, name=name)
    db.add(item)
    await db.flush()
    await log_event(db, "M7_OBJECT_CREATED", "DigitalHouseObject", item.id, owner_id, {"name": name})
    return item


async def save_strip_geometry(
    db: AsyncSession, *, actor: object, object_id: uuid.UUID, technology_id: uuid.UUID,
    length_m: object, width_m: object, height_m: object, expected_version: int,
) -> StripGeometryRevision:
    require_permission(actor, MODULE7_CODE, "EDIT")
    owner_id = getattr(actor, "id", None)
    item = await db.scalar(select(DigitalHouseObject).where(
        DigitalHouseObject.id == object_id, DigitalHouseObject.owner_user_id == owner_id).with_for_update())
    if item is None:
        raise ValueError("object not found")
    await _technology(db, technology_id, actor)
    length, width, height = _length(length_m), _length(width_m), _length(height_m)
    current = (await db.scalar(select(func.max(StripGeometryRevision.version)).where(
        StripGeometryRevision.object_id == object_id))) or 0
    if current != expected_version:
        raise ValueError("geometry changed; refresh before saving")
    revision = StripGeometryRevision(id=uuid.uuid4(), object_id=object_id, version=current + 1,
                                     technology_id=technology_id, length_m=length, width_m=width, height_m=height,
                                     created_by_user_id=owner_id)
    db.add(revision)
    await db.flush()
    await log_event(db, "M7_STRIP_GEOMETRY_SAVED", "StripGeometryRevision", revision.id, owner_id,
                    {"object_id": str(object_id), "version": revision.version, "technology_id": str(technology_id)})
    return revision


async def read_strip_geometry(db: AsyncSession, *, actor: object, revision_id: uuid.UUID) -> StripGeometryRevision:
    require_permission(actor, MODULE7_CODE, "VIEW")
    result = await db.scalar(select(StripGeometryRevision).join(
        DigitalHouseObject, DigitalHouseObject.id == StripGeometryRevision.object_id).where(
        StripGeometryRevision.id == revision_id, DigitalHouseObject.owner_user_id == getattr(actor, "id", None)))
    if result is None:
        raise ValueError("geometry not found")
    await _technology(db, result.technology_id, actor)
    return result
