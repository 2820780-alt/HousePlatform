from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.catalog_product import CatalogProduct
from app.models.enums import CatalogProductStatus, MatchCandidateStatus, MaterialStatus, TaskStatus
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask


router = APIRouter(prefix="/admin/cabinet/view", tags=["admin-cabinet-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_cabinet_view(request: Request, db: DBSession):
    cards = [
        {
            "title": "Модуль 1 · Material Hub",
            "value": await _count_model(db, Material),
            "note": "сбор, обработка и хранение материалов, источников, документов и цен",
            "href": "/api/v1/admin/material-hub/view",
            "action": "Открыть Модуль 1",
            "tone": "ok",
        },
        {
            "title": "Модуль 14 · Динамика цен",
            "value": await _count_model(db, PriceHistory),
            "note": "аналитика изменения цен на основе PriceHistory",
            "href": "/api/v1/admin/price-dynamics/view",
            "action": "Открыть Модуль 14",
            "tone": "info",
        },
        {
            "title": "Модерация",
            "value": await _count_pending_candidates(db),
            "note": "спорные совпадения и ручное согласование данных",
            "href": "/api/v1/admin/material-hub/view/moderation",
            "action": "Открыть очередь",
            "tone": "warn",
        },
        {
            "title": "Задачи анализа",
            "value": await _count_active_tasks(db),
            "note": "активные задачи сбора и обработки данных",
            "href": "/api/v1/admin/material-hub/view/tasks",
            "action": "Смотреть задачи",
            "tone": "danger",
        },
        {
            "title": "Источники",
            "value": await _count_model(db, Source),
            "note": "сайты, производители, retail и ручные загрузки",
            "href": "/api/v1/admin/material-hub/view/sources",
            "action": "Управлять источниками",
            "tone": "plain",
        },
        {
            "title": "Документы",
            "value": await _count_model(db, MaterialDocument),
            "note": "ссылки на сертификаты, инструкции и техническую документацию",
            "href": "/api/v1/admin/material-hub/view/documents",
            "action": "Смотреть документы",
            "tone": "info",
        },
        {
            "title": "Карточки источников",
            "value": await _count_where(db, CatalogProduct, CatalogProduct.status == CatalogProductStatus.NEEDS_REVIEW),
            "note": "карточки, требующие проверки",
            "href": "/api/v1/admin/material-hub/view/products",
            "action": "Проверить карточки",
            "tone": "warn",
        },
        {
            "title": "Материалы на проверке",
            "value": await _count_where(db, Material, Material.status == MaterialStatus.NEEDS_REVIEW),
            "note": "канонические материалы, ожидающие подтверждения",
            "href": "/api/v1/admin/material-hub/view/materials",
            "action": "Открыть материалы",
            "tone": "warn",
        },
    ]
    return templates.TemplateResponse(
        request,
        "admin_cabinet_view.html",
        {"cards": cards},
    )


async def _count_model(db: DBSession, model) -> int:
    result = await db.execute(select(func.count(model.id)))
    return result.scalar() or 0


async def _count_where(db: DBSession, model, condition) -> int:
    result = await db.execute(select(func.count(model.id)).where(condition))
    return result.scalar() or 0


async def _count_pending_candidates(db: DBSession) -> int:
    return await _count_where(
        db,
        MaterialMatchCandidate,
        MaterialMatchCandidate.status.in_([
            MatchCandidateStatus.OPEN,
            MatchCandidateStatus.NEEDS_REVIEW,
        ]),
    )


async def _count_active_tasks(db: DBSession) -> int:
    return await _count_where(
        db,
        SourceTask,
        SourceTask.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING]),
    )
