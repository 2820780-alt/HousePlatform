from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.models.material import Material
from app.models.price_history import PriceHistory
from app.models.supplier_price import SupplierPrice
from app.schemas.common import PaginatedResponse
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate
from app.schemas.material_hub import SupplierPriceRead
from app.schemas.price_history import PriceHistoryRead
from app.services.audit_service import log_event

router = APIRouter(prefix="/admin/materials", tags=["admin-materials"])


def _check_admin(user):
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()


@router.get("", response_model=PaginatedResponse[MaterialRead])
async def list_materials(
    db: DBSession,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    _check_admin(user)
    total_q = await db.execute(select(func.count(Material.id)))
    total = total_q.scalar()
    result = await db.execute(
        select(Material).order_by(Material.created_at.desc()).offset(offset).limit(limit)
    )
    return PaginatedResponse(items=result.scalars().all(), total=total, offset=offset, limit=limit)


@router.post("", response_model=MaterialRead, status_code=201)
async def create_material(data: MaterialCreate, db: DBSession, user: CurrentUser):
    _check_admin(user)
    material = Material(**data.model_dump())
    db.add(material)
    await db.flush()
    await db.refresh(material)
    await log_event(db, "material_created", "Material", material.id, user.id)
    return material


@router.get("/{material_id}", response_model=MaterialRead)
async def get_material(material_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise NotFoundError("Material not found")
    return material


@router.put("/{material_id}", response_model=MaterialRead)
async def update_material(material_id: UUID, data: MaterialUpdate, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(select(Material).where(Material.id == material_id))
    material = result.scalar_one_or_none()
    if not material:
        raise NotFoundError("Material not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(material, field, value)
    db.add(material)
    await db.flush()
    await db.refresh(material)
    await log_event(db, "material_updated", "Material", material.id, user.id)
    return material


@router.get("/{material_id}/supplier-prices", response_model=list[SupplierPriceRead])
async def get_material_supplier_prices(material_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(
        select(SupplierPrice).where(SupplierPrice.material_id == material_id).order_by(SupplierPrice.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{material_id}/price-history", response_model=list[PriceHistoryRead])
async def get_price_history(material_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(
        select(PriceHistory).where(PriceHistory.material_id == material_id).order_by(PriceHistory.collected_at.desc())
    )
    return result.scalars().all()
