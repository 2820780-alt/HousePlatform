from uuid import UUID
from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DBSession, CurrentUser
from app.models.supplier import Supplier
from app.models.supplier_account import SupplierAccount
from app.models.supplier_branch import SupplierBranch
from app.models.enums import UserRole
from app.schemas.branch import BranchCreate, BranchUpdate, BranchRead
from app.services.audit_service import log_event
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/supplier/branches", tags=["supplier-branches"])


async def _get_my_supplier_id(db, user) -> UUID:
    if user.role != UserRole.SUPPLIER:
        raise ForbiddenError()
    result = await db.execute(
        select(SupplierAccount.supplier_id).where(SupplierAccount.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("No supplier linked")
    return row


@router.get("", response_model=list[BranchRead])
async def list_branches(db: DBSession, user: CurrentUser):
    sid = await _get_my_supplier_id(db, user)
    result = await db.execute(select(SupplierBranch).where(SupplierBranch.supplier_id == sid))
    return result.scalars().all()


@router.post("", response_model=BranchRead, status_code=201)
async def create_branch(data: BranchCreate, db: DBSession, user: CurrentUser):
    sid = await _get_my_supplier_id(db, user)
    branch = SupplierBranch(supplier_id=sid, **data.model_dump())
    db.add(branch)
    await db.flush()
    await db.refresh(branch)
    await log_event(db, "branch_created", "SupplierBranch", branch.id, user.id)
    return branch


@router.put("/{branch_id}", response_model=BranchRead)
async def update_branch(branch_id: UUID, data: BranchUpdate, db: DBSession, user: CurrentUser):
    sid = await _get_my_supplier_id(db, user)
    result = await db.execute(
        select(SupplierBranch).where(SupplierBranch.id == branch_id, SupplierBranch.supplier_id == sid)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise NotFoundError("Branch not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    db.add(branch)
    await db.flush()
    await db.refresh(branch)
    return branch


@router.delete("/{branch_id}", status_code=204)
async def delete_branch(branch_id: UUID, db: DBSession, user: CurrentUser):
    sid = await _get_my_supplier_id(db, user)
    result = await db.execute(
        select(SupplierBranch).where(SupplierBranch.id == branch_id, SupplierBranch.supplier_id == sid)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise NotFoundError("Branch not found")
    await db.delete(branch)
    await db.flush()
