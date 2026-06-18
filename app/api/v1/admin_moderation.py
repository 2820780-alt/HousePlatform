from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.catalog_product import CatalogProduct
from app.models.enums import AdminDecision, CatalogProductStatus, MatchCandidateStatus, MaterialStatus, UserRole
from app.models.material import Material
from app.models.material_alias import MaterialAlias
from app.models.material_match_candidate import MaterialMatchCandidate
from app.schemas.common import PaginatedResponse
from app.schemas.material_hub import MaterialMatchCandidateRead
from app.schemas.moderation import ModerationApprove, ModerationCreateMaterial, ModerationReject
from app.services.audit_service import log_event

router = APIRouter(prefix="/admin/moderation", tags=["admin-moderation"])


def _check_admin(user):
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()


@router.get("/pending", response_model=PaginatedResponse[MaterialMatchCandidateRead])
async def list_pending(
    db: DBSession,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    _check_admin(user)
    total_q = await db.execute(
        select(func.count(MaterialMatchCandidate.id)).where(
            MaterialMatchCandidate.status.in_([
                MatchCandidateStatus.OPEN,
                MatchCandidateStatus.NEEDS_REVIEW,
            ])
        )
    )
    total = total_q.scalar()
    result = await db.execute(
        select(MaterialMatchCandidate)
        .where(MaterialMatchCandidate.status.in_([
            MatchCandidateStatus.OPEN,
            MatchCandidateStatus.NEEDS_REVIEW,
        ]))
        .order_by(MaterialMatchCandidate.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return PaginatedResponse(items=result.scalars().all(), total=total, offset=offset, limit=limit)


@router.get("/{candidate_id}", response_model=MaterialMatchCandidateRead)
async def get_candidate(candidate_id: UUID, db: DBSession, user: CurrentUser):
    _check_admin(user)
    result = await db.execute(
        select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise NotFoundError("Match candidate not found")
    return candidate


@router.post("/{candidate_id}/approve", response_model=MaterialMatchCandidateRead)
async def approve_candidate(
    candidate_id: UUID,
    data: ModerationApprove,
    db: DBSession,
    user: CurrentUser,
):
    _check_admin(user)
    result = await db.execute(
        select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise NotFoundError("Match candidate not found")

    material_id = data.material_id or candidate.candidate_material_id
    if not material_id:
        raise ValidationError("material_id is required to approve a candidate")

    catalog_result = await db.execute(
        select(CatalogProduct).where(CatalogProduct.id == candidate.catalog_product_id)
    )
    catalog_product = catalog_result.scalar_one_or_none()
    if not catalog_product:
        raise NotFoundError("Catalog product not found")

    catalog_product.material_id = material_id
    catalog_product.status = CatalogProductStatus.ACTIVE
    candidate.candidate_material_id = material_id
    candidate.status = MatchCandidateStatus.APPROVED
    candidate.admin_decision = AdminDecision.APPROVE

    db.add(catalog_product)
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    await log_event(db, "match_candidate_approved", "MaterialMatchCandidate", candidate.id, user.id, {
        "material_id": str(material_id),
        "catalog_product_id": str(catalog_product.id),
    })
    return candidate


@router.post("/{candidate_id}/reject", response_model=MaterialMatchCandidateRead)
async def reject_candidate(
    candidate_id: UUID,
    data: ModerationReject,
    db: DBSession,
    user: CurrentUser,
):
    _check_admin(user)
    result = await db.execute(
        select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise NotFoundError("Match candidate not found")

    candidate.status = MatchCandidateStatus.REJECTED
    candidate.admin_decision = AdminDecision.REJECT
    if data.reason:
        candidate.match_reason = f"{candidate.match_reason or ''}\nAdmin reject: {data.reason}".strip()

    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)
    await log_event(db, "match_candidate_rejected", "MaterialMatchCandidate", candidate.id, user.id)
    return candidate


@router.post("/{candidate_id}/create-material", response_model=MaterialMatchCandidateRead)
async def create_material_from_candidate(
    candidate_id: UUID,
    data: ModerationCreateMaterial,
    db: DBSession,
    user: CurrentUser,
):
    _check_admin(user)
    result = await db.execute(
        select(MaterialMatchCandidate).where(MaterialMatchCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise NotFoundError("Match candidate not found")

    catalog_result = await db.execute(
        select(CatalogProduct).where(CatalogProduct.id == candidate.catalog_product_id)
    )
    catalog_product = catalog_result.scalar_one_or_none()
    if not catalog_product:
        raise NotFoundError("Catalog product not found")

    material = Material(
        canonical_name=data.canonical_name or catalog_product.normalized_name or catalog_product.raw_name,
        category_id=data.category_id,
        brand=data.brand or catalog_product.raw_brand,
        manufacturer=data.manufacturer or catalog_product.raw_manufacturer,
        status=MaterialStatus.AUTO_CREATED,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    alias = MaterialAlias(
        material_id=material.id,
        original_name=catalog_product.raw_name,
        normalized_name=catalog_product.normalized_name or catalog_product.raw_name,
        confidence_score=candidate.match_score or Decimal("0.5"),
    )
    db.add(alias)

    catalog_product.material_id = material.id
    catalog_product.status = CatalogProductStatus.ACTIVE
    candidate.candidate_material_id = material.id
    candidate.status = MatchCandidateStatus.APPROVED
    candidate.admin_decision = AdminDecision.APPROVE

    db.add(catalog_product)
    db.add(candidate)
    await db.flush()
    await db.refresh(candidate)

    await log_event(db, "material_created_from_candidate", "Material", material.id, user.id, {
        "candidate_id": str(candidate.id),
        "catalog_product_id": str(catalog_product.id),
    })
    return candidate
