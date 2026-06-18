from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DBSession, CurrentUser
from app.models.supplier import Supplier
from app.models.supplier_account import SupplierAccount
from app.models.enums import UserRole
from app.schemas.supplier import SupplierRead, SupplierUpdate
from app.services.audit_service import log_event
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/supplier/profile", tags=["supplier-profile"])


async def _get_my_supplier(db, user):
    if user.role != UserRole.SUPPLIER:
        raise ForbiddenError()
    result = await db.execute(
        select(Supplier).join(SupplierAccount).where(SupplierAccount.user_id == user.id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise NotFoundError("Supplier profile not found. Contact admin.")
    return supplier


@router.get("", response_model=SupplierRead)
async def get_profile(db: DBSession, user: CurrentUser):
    return await _get_my_supplier(db, user)


@router.put("", response_model=SupplierRead)
async def update_profile(data: SupplierUpdate, db: DBSession, user: CurrentUser):
    supplier = await _get_my_supplier(db, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.add(supplier)
    await db.flush()
    await db.refresh(supplier)
    await log_event(db, "supplier_profile_updated", "Supplier", supplier.id, user.id)
    return supplier
