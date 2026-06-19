from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.api.deps import DBSession
from app.models.enums import MatchCandidateStatus, MaterialStatus, TaskStatus
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source_task import SourceTask


router = APIRouter(prefix="/admin/cabinet/view", tags=["admin-cabinet-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_cabinet_view(request: Request, db: DBSession):
    material_total = await _count_model(db, Material)
    document_total = await _count_model(db, MaterialDocument)
    pending_candidates = await _count_pending_candidates(db)
    active_tasks = await _count_active_tasks(db)
    price_points = await _count_model(db, PriceHistory)
    price_dynamics_summary = await _load_price_dynamics_summary(db)
    cards = [
        {
            "title": "Модуль 1 · Material Hub",
            "subtitle": "Сбор, обработка и хранение информации",
            "description": "Материалы, источники, карточки товаров, документы, текущие цены и фактический журнал PriceHistory.",
            "href": "/api/v1/admin/material-hub/view",
            "action": "Открыть Модуль 1",
            "tone": "ok",
            "metrics": [
                {"label": "Всего материалов", "value": material_total},
                {"label": "Всего документов", "value": document_total},
                {"label": "Спорные совпадения", "value": pending_candidates, "alert": pending_candidates > 0},
                {"label": "Активные задачи", "value": active_tasks, "alert": active_tasks > 0},
            ],
        },
        {
            "title": "Модуль 14 · Динамика цен",
            "subtitle": "Аналитика изменения цен",
            "description": "Динамика по рынку, категориям и материалам на основе фактов из PriceHistory.",
            "href": "/api/v1/admin/price-dynamics/view",
            "action": "Открыть Модуль 14",
            "tone": "info",
            "metrics": [
                {"label": "Точек истории", "value": price_points},
                {"label": "Динамика рынка", "value": price_dynamics_summary["market"]},
                {"label": "Категорий с динамикой", "value": price_dynamics_summary["categories"]},
                {"label": "Динамика по группам", "value": "ожидает групп"},
            ],
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


async def _load_price_dynamics_summary(db: DBSession) -> dict:
    result = await db.execute(
        select(PriceHistory.material_id, PriceHistory.price, PriceHistory.collected_at, Material.category_id)
        .join(Material, PriceHistory.material_id == Material.id)
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .order_by(PriceHistory.material_id.asc(), PriceHistory.collected_at.desc())
        .limit(2000)
    )
    rows = result.all()
    by_material: dict[str, list] = {}
    categories = set()
    for material_id, price, collected_at, category_id in rows:
        by_material.setdefault(str(material_id), []).append((price, collected_at, category_id))

    changes = []
    for material_rows in by_material.values():
        sorted_rows = sorted(material_rows, key=lambda item: item[1], reverse=True)
        if len(sorted_rows) < 2:
            continue
        latest, previous = sorted_rows[0], sorted_rows[1]
        if previous[0]:
            changes.append((latest[0] - previous[0]) / previous[0] * 100)
            if latest[2]:
                categories.add(str(latest[2]))

    if not changes:
        market = "нужно больше данных"
    else:
        market = f"{sum(changes) / len(changes):.2f}%"

    return {
        "market": market,
        "categories": len(categories),
    }
