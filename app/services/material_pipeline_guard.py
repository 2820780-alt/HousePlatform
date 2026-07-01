from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog_product import CatalogProduct
from app.models.enums import AdminDecision, CatalogProductStatus, MatchCandidateStatus, MaterialStatus
from app.models.material import Material
from app.models.material_alias import MaterialAlias
from app.models.material_match_candidate import MaterialMatchCandidate


PIPELINE_POLICY_NOTE = (
    "Canonical Material may be created only from a moderated MaterialMatchCandidate. "
    "Source/API/file/parser data must first become raw/catalog records and candidates."
)


def canonical_name_from_candidate(
    candidate: MaterialMatchCandidate,
    catalog_product: CatalogProduct,
    requested_name: str | None = None,
) -> str:
    name = requested_name or candidate.ai_suggestion or catalog_product.normalized_name or catalog_product.raw_name
    name = (name or "").strip()
    if not name:
        raise ValueError("Canonical material name is required")
    return name


async def create_material_from_moderated_candidate(
    db: AsyncSession,
    candidate: MaterialMatchCandidate,
    catalog_product: CatalogProduct,
    *,
    canonical_name: str | None = None,
    category_id=None,
    brand: str | None = None,
    manufacturer: str | None = None,
    reason: str | None = None,
) -> Material:
    if candidate.catalog_product_id != catalog_product.id:
        raise ValueError("Candidate and catalog product do not match")
    if candidate.status not in {MatchCandidateStatus.OPEN, MatchCandidateStatus.NEEDS_REVIEW}:
        raise ValueError("Only open/review candidates can create canonical materials")

    material = Material(
        canonical_name=canonical_name_from_candidate(candidate, catalog_product, canonical_name),
        category_id=category_id,
        brand=brand or catalog_product.raw_brand,
        manufacturer=manufacturer or catalog_product.raw_manufacturer,
        status=MaterialStatus.AUTO_CREATED,
    )
    db.add(material)
    await db.flush()
    await db.refresh(material)

    alias_name = catalog_product.normalized_name or catalog_product.raw_name
    if alias_name:
        alias = MaterialAlias(
            material_id=material.id,
            original_name=catalog_product.raw_name,
            normalized_name=alias_name,
            confidence_score=candidate.match_score or Decimal("0.5"),
        )
        db.add(alias)

    catalog_product.material_id = material.id
    catalog_product.status = CatalogProductStatus.ACTIVE
    candidate.candidate_material_id = material.id
    candidate.status = MatchCandidateStatus.APPROVED
    candidate.admin_decision = AdminDecision.APPROVE
    note = reason or "moderated candidate approved"
    candidate.match_reason = f"{candidate.match_reason or ''}\nСоздан новый Material через pipeline: {note}".strip()

    db.add(catalog_product)
    db.add(candidate)
    await db.flush()
    return material
