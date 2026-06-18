from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DBSession
from app.models.catalog_product import CatalogProduct
from app.models.material import Material
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.price_history import PriceHistory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult


router = APIRouter(prefix="/admin/material-hub/view", tags=["material-hub-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def material_hub_view(request: Request, db: DBSession):
    stats = await _load_stats(db)
    sources = await _load_sources(db)
    tasks = await _load_tasks(db)
    products = await _load_catalog_products(db)
    materials = await _load_materials(db)
    candidates = await _load_candidates(db)
    prices = await _load_prices(db)
    documents = await _load_documents(db)
    logs = await _load_logs(db)
    results = await _load_results(db)

    return templates.TemplateResponse(
        request,
        "material_hub_view.html",
        {
            "stats": stats,
            "sources": sources,
            "tasks": tasks,
            "products": products,
            "materials": materials,
            "candidates": candidates,
            "prices": prices,
            "documents": documents,
            "logs": logs,
            "results": results,
            "sample_task_payload": {
                "action_type": "INITIAL_MATERIAL_SCAN",
                "source_ids": ["<source-id>"],
                "all_sources": False,
                "parameters": {
                    "scan_mode": "CATEGORY",
                    "category_url_contains": ["stroymaterialy"],
                    "max_pages": 100,
                    "max_attempts": 300,
                },
            },
        },
    )


async def _load_stats(db: DBSession) -> dict[str, int]:
    models = {
        "sources": Source,
        "tasks": SourceTask,
        "catalog_products": CatalogProduct,
        "materials": Material,
        "match_candidates": MaterialMatchCandidate,
        "price_history": PriceHistory,
        "documents": MaterialDocument,
    }
    stats: dict[str, int] = {}
    for key, model in models.items():
        result = await db.execute(select(func.count(model.id)))
        stats[key] = result.scalar() or 0
    return stats


async def _load_sources(db: DBSession) -> list[Source]:
    result = await db.execute(
        select(Source).order_by(Source.priority.asc(), Source.name.asc()).limit(100)
    )
    return list(result.scalars().all())


async def _load_tasks(db: DBSession) -> list[SourceTask]:
    result = await db.execute(
        select(SourceTask)
        .options(selectinload(SourceTask.source))
        .order_by(SourceTask.created_at.desc())
        .limit(30)
    )
    return list(result.scalars().all())


async def _load_catalog_products(db: DBSession) -> list[CatalogProduct]:
    result = await db.execute(
        select(CatalogProduct)
        .options(
            selectinload(CatalogProduct.source),
            selectinload(CatalogProduct.material),
        )
        .order_by(CatalogProduct.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def _load_materials(db: DBSession) -> list[Material]:
    result = await db.execute(
        select(Material).order_by(Material.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def _load_candidates(db: DBSession) -> list[MaterialMatchCandidate]:
    result = await db.execute(
        select(MaterialMatchCandidate)
        .options(
            selectinload(MaterialMatchCandidate.catalog_product),
            selectinload(MaterialMatchCandidate.candidate_material),
        )
        .order_by(MaterialMatchCandidate.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def _load_prices(db: DBSession) -> list[PriceHistory]:
    result = await db.execute(
        select(PriceHistory).order_by(PriceHistory.collected_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def _load_documents(db: DBSession) -> list[MaterialDocument]:
    result = await db.execute(
        select(MaterialDocument)
        .options(
            selectinload(MaterialDocument.source),
            selectinload(MaterialDocument.material),
            selectinload(MaterialDocument.manufacturer),
        )
        .order_by(MaterialDocument.created_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


async def _load_logs(db: DBSession) -> list[SourceTaskLog]:
    result = await db.execute(
        select(SourceTaskLog).order_by(SourceTaskLog.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())


async def _load_results(db: DBSession) -> list[SourceTaskResult]:
    result = await db.execute(
        select(SourceTaskResult).order_by(SourceTaskResult.created_at.desc()).limit(50)
    )
    return list(result.scalars().all())
