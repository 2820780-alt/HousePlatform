from __future__ import annotations

import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession
from app.core.access_scopes import AccessScope
from app.core.permission_guard import require_permission
from app.models.catalog_product import CatalogProduct
from app.models.enums import CatalogProductStatus, DocumentStatus, MaterialStatus
from app.models.material import Material
from app.models.material_specification import MaterialSpecification
from app.models.price_history import PriceHistory
from app.models.supplier import Supplier


router = APIRouter(prefix="/module1/materials", tags=["module1-material-card"])
templates = Jinja2Templates(directory="templates")


def _safe_url(value: str | None) -> str | None:
    parsed = urlsplit(value or "")
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


@router.get("/{material_id}", response_class=HTMLResponse)
async def material_card(material_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, "MODULE_01_MATERIAL_HUB", "VIEW", scope=AccessScope.LIMITED)
    material = await db.scalar(
        select(Material)
        .options(
            selectinload(Material.category), selectinload(Material.subcategory),
            selectinload(Material.material_type), selectinload(Material.attributes),
            selectinload(Material.specifications).selectinload(MaterialSpecification.template),
            selectinload(Material.documents),
        )
        .where(Material.id == material_id, Material.status == MaterialStatus.VERIFIED)
    )
    if material is None:
        raise HTTPException(status_code=404)
    prices = (await db.scalars(
        select(PriceHistory).where(PriceHistory.material_id == material_id)
        .order_by(PriceHistory.collected_at.desc()).limit(10)
    )).all()
    offers = (await db.scalars(
        select(CatalogProduct)
        .where(CatalogProduct.material_id == material_id,
               CatalogProduct.status == CatalogProductStatus.ACTIVE)
        .order_by(CatalogProduct.updated_at.desc()).limit(20)
    )).all()
    supplier_ids = {item.supplier_id for item in prices if item.supplier_id}
    suppliers = {}
    if supplier_ids:
        suppliers = {item.id: item for item in (await db.scalars(
            select(Supplier).where(Supplier.id.in_(supplier_ids))
        )).all()}
    return templates.TemplateResponse(request, "module1_material_card.html", {
        "material": material,
        "documents": tuple({"title": item.title, "url": _safe_url(item.file_url or item.source_url)}
                           for item in material.documents if item.status == DocumentStatus.ACTIVE),
        "prices": tuple({"row": item, "supplier": suppliers.get(item.supplier_id),
                         "supplier_url": _safe_url(suppliers[item.supplier_id].site)
                         if item.supplier_id in suppliers else None} for item in prices),
        "offers": tuple({"name": item.raw_name, "url": _safe_url(item.external_url)}
                        for item in offers if _safe_url(item.external_url)),
        "atom_topbar_current_block": "Модуль №1: карточка материала",
    })
