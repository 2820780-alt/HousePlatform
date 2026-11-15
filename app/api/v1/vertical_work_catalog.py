"""Opt-in M1 work cards and manual fallback prices for the vertical preview."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DBSession
from app.config import settings
from app.core.permission_guard import can, require_permission
from app.core.exceptions import ForbiddenError
from app.models.enums import MaterialStatus, SupplierStatus
from app.models.material import Material
from app.models.module1_work_item import ManualCalculationPriceRevision, WorkCatalogItem
from app.models.module2_technology import Technology, TechnologyWorkStep
from app.models.module1_offer_qualification import CalculationOfferQualification
from app.models.supplier import Supplier
from app.models.supplier_price import SupplierPrice
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.user import User
from app.models.unit import Unit
from app.services.audit_service import log_event
from app.services.module1_calculation_price import _positive_decimal
from app.services.module1_manual_calculation_price import _context_text, append_manual_price
from app.services.module1_offer_qualification import offer_fingerprint, quote_current_offers, review_offer
from app.services.module1_provider_work_cost_offers import _apply_list_permissions, provider_work_cost_offer_to_dict
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import WorkCatalogWrite, approve_work_item, save_work_item

router = APIRouter(prefix="/admin/vertical-m1", tags=["vertical-m1"])
templates = Jinja2Templates(directory="templates")


def _guard(user, action="EDIT", *, catalog=False):
    if not catalog and not settings.VERTICAL_CALCULATION_PREVIEW_ENABLED:
        raise HTTPException(status_code=404)
    require_permission(user, "MODULE_01_MATERIAL_HUB", action)


@router.get("/works", response_class=HTMLResponse)
async def works(request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "VIEW", catalog=True)
    registry = get_work_catalog_registry()
    search = str(request.query_params.get("q") or "").strip()[:200]
    group = str(request.query_params.get("group") or "").strip()[:120]
    region = str(request.query_params.get("region") or "").strip()[:120]
    terms = str(request.query_params.get("terms") or "").strip()[:200]
    try:
        page = max(1, min(int(request.query_params.get("page", "1")), 10000))
    except ValueError:
        page = 1
    may_edit = can(user, "MODULE_01_MATERIAL_HUB", "EDIT")
    conditions = [WorkCatalogItem.status != "ARCHIVED"] if may_edit else [WorkCatalogItem.status == "ACTIVE"]
    if search:
        needle = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(or_(WorkCatalogItem.work_name.ilike(needle, escape="\\"),
                              WorkCatalogItem.work_code.ilike(needle, escape="\\")))
    if group:
        conditions.append(WorkCatalogItem.work_group == group)
    total = await db.scalar(select(func.count()).select_from(WorkCatalogItem).where(*conditions))
    pages = max(1, (total + 24) // 25)
    page = min(page, pages)
    rows = (await db.scalars(select(WorkCatalogItem).where(*conditions)
                             .order_by(WorkCatalogItem.work_name, WorkCatalogItem.work_code)
                             .offset((page - 1) * 25).limit(25))).all()
    prices = {}
    prices_restricted = False
    if region and terms:
        for item in rows:
            try:
                prices[item.work_code] = await quote_current_offers(
                    db, work_code=item.work_code, region=region, terms=terms, as_of=date.today(), actor=user)
            except ForbiddenError:
                prices_restricted = True
                break
    query = urlencode({key: value for key, value in {"q": search, "group": group,
                       "region": region, "terms": terms}.items() if value})
    return templates.TemplateResponse(request, "vertical_work_catalog.html", {
        "works": rows, "groups": registry.groups, "units": registry.units,
        "search": search, "group": group, "region": region, "terms": terms,
        "total": total, "page": page, "pages": pages, "query": query, "prices": prices,
        "prices_restricted": prices_restricted,
        "may_edit": may_edit,
        "error": request.query_params.get("error"),
    })


@router.get("/works/{work_code}", response_class=HTMLResponse)
async def work_card(work_code: str, request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "VIEW", catalog=True)
    work = await db.get(WorkCatalogItem, work_code)
    if (work is None or work.status == "ARCHIVED" or
            (work.status != "ACTIVE" and not can(user, "MODULE_01_MATERIAL_HUB", "EDIT"))):
        raise HTTPException(status_code=404)
    registry = get_work_catalog_registry()
    region = str(request.query_params.get("region") or "").strip()[:120]
    terms = str(request.query_params.get("terms") or "").strip()[:200]
    back = str(request.query_params.get("back") or "")
    if not (back == "/api/v1/admin/vertical-m1/works" or
            back.startswith("/api/v1/admin/vertical-m1/works?")):
        back = "/api/v1/admin/vertical-m1/works"
    price = None
    manual_price = None
    prices_restricted = False
    if region and terms:
        try:
            price = await quote_current_offers(db, work_code=work_code, region=region, terms=terms,
                                               as_of=date.today(), actor=user)
            manual_price = await db.scalar(select(ManualCalculationPriceRevision).where(
                ManualCalculationPriceRevision.work_code == work_code,
                ManualCalculationPriceRevision.currency == "RUB",
                ManualCalculationPriceRevision.unit == work.default_unit,
                ManualCalculationPriceRevision.region == _context_text(region),
                ManualCalculationPriceRevision.terms == _context_text(terms),
                ManualCalculationPriceRevision.effective_from <= date.today()).order_by(
                ManualCalculationPriceRevision.effective_from.desc(),
                ManualCalculationPriceRevision.version.desc()).limit(1))
        except ForbiddenError:
            prices_restricted = True
    offers = []
    may_view_offers = False
    try:
        query = _apply_list_permissions(select(ProviderWorkCostOffer).where(
            ProviderWorkCostOffer.work_code == work_code), user, owner_user_id=None)
        offers = [provider_work_cost_offer_to_dict(offer, user, work_by_code={work_code: work})
                  for offer in (await db.scalars(query.order_by(ProviderWorkCostOffer.created_at.desc()).limit(100))).all()]
        may_view_offers = True
    except ForbiddenError:
        pass
    technologies = []
    if can(user, "MODULE_02_KNOWLEDGE_BASE", "VIEW"):
        technology_status = (Technology.status != "ARCHIVED" if can(user, "MODULE_02_KNOWLEDGE_BASE", "EDIT")
                             else Technology.status == "ACTIVE")
        technologies = (await db.scalars(select(Technology).join(
            TechnologyWorkStep, TechnologyWorkStep.technology_id == Technology.id).where(
            TechnologyWorkStep.work_code == work_code, technology_status)
            .order_by(Technology.name, Technology.revision).distinct())).all()
    return templates.TemplateResponse(request, "vertical_work_catalog.html", {
        "work": work, "works": (), "groups": registry.groups, "units": registry.units,
        "region": region, "terms": terms, "price": price, "manual_price": manual_price,
        "technologies": technologies, "back": back,
        "prices_restricted": prices_restricted, "offers": offers, "may_view_offers": may_view_offers,
        "may_edit": can(user, "MODULE_01_MATERIAL_HUB", "EDIT"),
        "may_approve": can(user, "MODULE_01_MATERIAL_HUB", "APPROVE"),
        "error": request.query_params.get("error"),
    })


@router.post("/works/save")
async def save_work(request: Request, db: DBSession, user: CurrentUser):
    _guard(user, catalog=True)
    form = await request.form()
    code = str(form.get("work_code") or "")
    target = "/api/v1/admin/vertical-m1/works"
    try:
        current = await db.get(WorkCatalogItem, code) if code else None
        if code and not current:
            raise ValueError("work not found")
        group_code = str(form.get("work_group") or "")
        group = next((item for item in get_work_catalog_registry().groups if item.work_group == group_code), None)
        if group is None:
            raise ValueError("unknown work group")
        unit = str(form.get("unit") or "")
        allowed = list(current.allowed_units) if current and unit == current.default_unit else [unit]
        payload = WorkCatalogWrite(work_code=code or "manual_" + uuid.uuid4().hex, work_group=group.work_group,
            work_category=group.work_category, work_name=str(form.get("name") or ""), default_unit=unit,
            allowed_units=allowed, description=str(form.get("description") or "").strip() or None,
            is_range_allowed=current.is_range_allowed if current else False,
            applies_to=current.applies_to if current else "both", conditions=current.conditions if current else {})
        saved = await save_work_item(db, payload, actor_id=user.id,
                                     expected_version=int(str(form["version"])) if current else None)
        target += "/" + quote(saved.work_code, safe="")
        await db.commit()
    except (KeyError, ValueError):
        await db.rollback()
        target += "?" + urlencode({"error": "Не удалось сохранить работу. Проверьте поля и существующие связи."})
    return RedirectResponse(target, status_code=303)


@router.post("/works/{work_code}/approve")
async def approve_work(work_code: str, request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "APPROVE", catalog=True)
    form = await request.form()
    target = "/api/v1/admin/vertical-m1/works/" + quote(work_code, safe="")
    try:
        await approve_work_item(db, work_code=work_code, expected_version=int(str(form["version"])), actor=user)
        await db.commit()
    except (KeyError, ValueError):
        await db.rollback()
        target += "?" + urlencode({"error": "Не удалось утвердить работу. Обновите карточку."})
    return RedirectResponse(target, status_code=303)


@router.get("/prices/{kind}/{identifier}", response_class=HTMLResponse)
async def price_card(kind: str, identifier: str, request: Request, db: DBSession, user: CurrentUser):
    _guard(user, catalog=kind == "work")
    try:
        material_id = uuid.UUID(identifier) if kind == "material" else None
    except ValueError:
        raise HTTPException(status_code=404) from None
    if kind not in {"work", "material"}:
        raise HTTPException(status_code=404)
    resource = await db.get(Material, material_id) if material_id else await db.get(WorkCatalogItem, identifier)
    if resource is None:
        raise HTTPException(status_code=404)
    region, terms = str(request.query_params.get("region") or ""), str(request.query_params.get("terms") or "")
    quote_result = None
    if region and terms:
        quote_result = await quote_current_offers(db, material_id=material_id, work_code=identifier if not material_id else None,
                                                   region=region, terms=terms, as_of=date.today(), actor=user)
    owner = (ManualCalculationPriceRevision.material_id == material_id if material_id
             else ManualCalculationPriceRevision.work_code == identifier)
    history = (await db.scalars(select(ManualCalculationPriceRevision).where(owner).order_by(
        ManualCalculationPriceRevision.created_at.desc()).limit(50))).all()
    suppliers, offers, work_offers = (), [], []
    may_review = can(user, "MODULE_01_MATERIAL_HUB", "ADMIN")
    if material_id and may_review:
        suppliers = (await db.scalars(select(Supplier).where(Supplier.status != SupplierStatus.BLOCKED)
                                      .order_by(Supplier.name))).all()
        rows = (await db.execute(select(SupplierPrice, Supplier).join(Supplier, Supplier.id == SupplierPrice.supplier_id)
                                 .where(SupplierPrice.material_id == material_id).order_by(SupplierPrice.created_at.desc()))).all()
        for offer, supplier in rows:
            review = await db.scalar(select(CalculationOfferQualification).where(
                CalculationOfferQualification.supplier_price_id == offer.id).order_by(
                CalculationOfferQualification.version.desc()).limit(1))
            offers.append((offer, supplier, review, bool(review and review.status == "CONFIRMED" and
                                                         review.offer_fingerprint == offer_fingerprint(offer))))
    if kind == "work" and may_review:
        rows = (await db.execute(select(ProviderWorkCostOffer, User).join(User, User.id == ProviderWorkCostOffer.owner_user_id)
                                 .where(ProviderWorkCostOffer.work_code == identifier).order_by(
                                     ProviderWorkCostOffer.created_at.desc()))).all()
        for offer, owner_user in rows:
            review = await db.scalar(select(CalculationOfferQualification).where(
                CalculationOfferQualification.work_offer_id == offer.id).order_by(
                CalculationOfferQualification.version.desc()).limit(1))
            valid = bool(review and review.status == "CONFIRMED" and review.offer_fingerprint == offer_fingerprint(offer))
            work_offers.append((offer, owner_user, review, valid))
    return templates.TemplateResponse(request, "vertical_price_card.html", {
        "kind": kind, "identifier": identifier, "name": resource.canonical_name if material_id else resource.work_name,
        "region": region, "terms": terms, "quote_result": quote_result, "history": history,
        "error": request.query_params.get("error"), "suppliers": suppliers, "offers": offers,
        "work_offers": work_offers, "may_review": may_review,
    })


@router.post("/prices/{kind}/{identifier}")
async def save_price(kind: str, identifier: str, request: Request, db: DBSession, user: CurrentUser):
    _guard(user, catalog=kind == "work")
    form = await request.form()
    region, terms = str(form.get("region") or ""), str(form.get("terms") or "")
    try:
        if kind not in {"material", "work"}:
            raise ValueError("unknown resource")
        amount = str(form.get("amount") or "").strip().replace(",", ".")
        if amount and _positive_decimal(Decimal(amount)) is None:
            raise ValueError("invalid amount")
        await append_manual_price(db, material_id=uuid.UUID(identifier) if kind == "material" else None,
                                  work_code=identifier if kind == "work" else None,
                                  amount=Decimal(amount) if amount else None, region=region, terms=terms,
                                  effective_from=date.today(), actor_id=user.id)
        await db.commit()
        query = urlencode({"region": region, "terms": terms})
    except (ValueError, InvalidOperation):
        await db.rollback()
        query = urlencode({"error": "Не удалось сохранить цену. Проверьте поля."})
    if kind == "work" and form.get("return_work") == "1":
        return RedirectResponse(f"/api/v1/admin/vertical-m1/works/{quote(identifier, safe='')}?{query}", status_code=303)
    return RedirectResponse(f"/api/v1/admin/vertical-m1/prices/{kind}/{quote(identifier, safe='')}?{query}", status_code=303)


@router.post("/prices/material/{identifier}/offers")
async def create_material_offer(identifier: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "ADMIN")
    form = await request.form()
    region, terms = str(form.get("region") or "").strip(), str(form.get("terms") or "").strip()
    try:
        material = await db.get(Material, identifier)
        supplier = await db.get(Supplier, uuid.UUID(str(form["supplier_id"])))
        amount = Decimal(str(form.get("amount") or "").strip().replace(",", "."))
        if (not material or material.status in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED} or
                not supplier or supplier.status == SupplierStatus.BLOCKED or not region or not terms or
                not form.get("confirmed") or _positive_decimal(amount) is None or amount.adjusted() > 12 or
                amount.as_tuple().exponent < -2):
            raise ValueError("invalid offer")
        unit = await db.get(Unit, material.base_unit_id) if material.base_unit_id else None
        if unit is None:
            raise ValueError("base unit required")
        offer = SupplierPrice(id=uuid.uuid4(), supplier_id=supplier.id, material_id=identifier,
                              price=amount, currency="RUB", unit=unit.abbreviation, region=region,
                              availability="available", delivery_terms=terms)
        db.add(offer)
        await db.flush()
        await review_offer(db, supplier_price_id=offer.id, terms=terms, status="CONFIRMED", actor=user)
        await log_event(db, "M1_CALCULATION_MATERIAL_OFFER_CREATED", "SupplierPrice", offer.id, user.id,
                        {"material_id": str(identifier), "supplier_id": str(supplier.id)})
        await db.commit()
        query = urlencode({"region": region, "terms": terms})
    except (KeyError, ValueError, InvalidOperation):
        await db.rollback()
        query = urlencode({"error": "Не удалось добавить предложение. Проверьте поля и подтверждение."})
    return RedirectResponse(f"/api/v1/admin/vertical-m1/prices/material/{identifier}?{query}", status_code=303)


@router.post("/prices/material/{identifier}/offers/{offer_id}/withdraw")
async def withdraw_material_offer(identifier: uuid.UUID, offer_id: uuid.UUID, request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "ADMIN")
    form = await request.form()
    region, terms = str(form.get("region") or ""), str(form.get("terms") or "")
    try:
        offer = await db.get(SupplierPrice, offer_id)
        if not offer or offer.material_id != identifier or not terms:
            raise ValueError("offer not found")
        await review_offer(db, supplier_price_id=offer.id, terms=terms, status="WITHDRAWN", actor=user)
        await db.commit()
        query = urlencode({"region": region, "terms": terms})
    except ValueError:
        await db.rollback()
        query = urlencode({"error": "Не удалось исключить предложение."})
    return RedirectResponse(f"/api/v1/admin/vertical-m1/prices/material/{identifier}?{query}", status_code=303)


@router.post("/prices/work/{work_code}/offers/{offer_id}/{decision}")
async def review_work_offer(work_code: str, offer_id: uuid.UUID, decision: str,
                            request: Request, db: DBSession, user: CurrentUser):
    _guard(user, "ADMIN", catalog=True)
    form = await request.form()
    region, terms = str(form.get("region") or ""), str(form.get("terms") or "")
    try:
        offer = await db.get(ProviderWorkCostOffer, offer_id)
        if not offer or offer.work_code != work_code or decision not in {"confirm", "withdraw"} or not terms:
            raise ValueError("invalid work offer")
        if decision == "confirm" and not form.get("confirmed"):
            raise ValueError("identity confirmation required")
        await review_offer(db, work_offer_id=offer.id, terms=terms,
                           status="CONFIRMED" if decision == "confirm" else "WITHDRAWN", actor=user)
        await db.commit()
        query = urlencode({"region": region, "terms": terms})
    except ValueError:
        await db.rollback()
        query = urlencode({"error": "Не удалось изменить допуск предложения."})
    return RedirectResponse(f"/api/v1/admin/vertical-m1/prices/work/{quote(work_code, safe='')}?{query}", status_code=303)
