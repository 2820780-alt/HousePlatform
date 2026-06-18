from uuid import UUID
from fastapi import APIRouter, Query
from sqlalchemy import select, func

from app.api.deps import DBSession, CurrentUser, require_role
from app.models.user import User
from app.models.supplier import Supplier
from app.models.enums import UserRole
from app.schemas.supplier import SupplierCreate, SupplierUpdate, SupplierRead, SupplierStatusUpdate
from app.schemas.common import PaginatedResponse
from app.services.audit_service import log_event
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/admin/suppliers", tags=["admin-suppliers"])


@router.get("", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    db: DBSession,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()
    total_q = await db.execute(select(func.count(Supplier.id)))
    total = total_q.scalar()
    result = await db.execute(select(Supplier).offset(offset).limit(limit).order_by(Supplier.created_at.desc()))
    items = result.scalars().all()
    return PaginatedResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=SupplierRead, status_code=201)
async def create_supplier(data: SupplierCreate, db: DBSession, user: CurrentUser):
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()
    supplier = Supplier(**data.model_dump())
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    await log_event(db, "supplier_created", "Supplier", supplier.id, user.id)
    return supplier


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: UUID, db: DBSession, user: CurrentUser):
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Supplier not found")
    return supplier


@router.put("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(supplier_id: UUID, data: SupplierUpdate, db: DBSession, user: CurrentUser):
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Supplier not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    await log_event(db, "supplier_updated", "Supplier", supplier.id, user.id)
    return supplier


@router.patch("/{supplier_id}/status", response_model=SupplierRead)
async def update_supplier_status(supplier_id: UUID, data: SupplierStatusUpdate, db: DBSession, user: CurrentUser):
    if user.role != UserRole.ADMIN:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Supplier not found")
    supplier.status = data.status
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    await log_event(db, "supplier_status_changed", "Supplier", supplier.id, user.id, {"new_status": data.status.value})
    return supplier
