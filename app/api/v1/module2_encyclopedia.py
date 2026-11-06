from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.access_scopes import AccessScope
from app.core.permission_guard import require_permission
from app.models.module2_technology import MODULE2_OWNER_CODE, TechnologyWorkStep
from app.services.module1_work_catalog import get_work_item
from app.services.module2_encyclopedia import (
    public_catalog,
    public_category,
    public_technology,
    technology_article,
)


router = APIRouter(prefix="/module2/encyclopedia", tags=["module2-encyclopedia"])
templates = Jinja2Templates(directory="templates")


def _view(user: CurrentUser) -> None:
    require_permission(user, MODULE2_OWNER_CODE, "VIEW", scope=AccessScope.LIMITED)


def _render(request: Request, view: str, **context):
    return templates.TemplateResponse(
        request,
        "module2_encyclopedia.html",
        {"view": view, "atom_topbar_current_block": "Модуль №2: Энциклопедия", **context},
    )


@router.get("", response_class=HTMLResponse)
async def encyclopedia_index(request: Request, db: DBSession, user: CurrentUser):
    _view(user)
    query = str(request.query_params.get("q") or "").strip()[:120]
    return _render(request, "index", catalog=await public_catalog(db, query), query=query)


@router.get("/categories/{category_code}", response_class=HTMLResponse)
async def encyclopedia_category(
    category_code: str, request: Request, db: DBSession, user: CurrentUser
):
    _view(user)
    category = await public_category(db, category_code)
    if category is None:
        raise HTTPException(status_code=404)
    return _render(request, "category", **category)


async def _article(db: DBSession, technology_code: str) -> dict:
    technology = await public_technology(db, technology_code)
    if technology is None:
        raise HTTPException(status_code=404)
    return await technology_article(db, technology)


@router.get("/technologies/{technology_code}", response_class=HTMLResponse)
async def encyclopedia_technology(
    technology_code: str, request: Request, db: DBSession, user: CurrentUser
):
    _view(user)
    return _render(request, "technology", article=await _article(db, technology_code))


@router.get(
    "/technologies/{technology_code}/materials/{requirement_code}",
    response_class=HTMLResponse,
)
async def encyclopedia_material_application(
    technology_code: str, requirement_code: str, request: Request,
    db: DBSession, user: CurrentUser,
):
    _view(user)
    article = await _article(db, technology_code)
    requirement = next(
        (item for item in article["requirements"] if item["model"].code == requirement_code),
        None,
    )
    if requirement is None:
        raise HTTPException(status_code=404)
    return _render(request, "material", article=article, requirement=requirement)


@router.get("/technologies/{technology_code}/nodes/{node_code}", response_class=HTMLResponse)
async def encyclopedia_node(
    technology_code: str, node_code: str, request: Request, db: DBSession, user: CurrentUser
):
    _view(user)
    article = await _article(db, technology_code)
    node = next((item for item in article["nodes"] if item.code == node_code), None)
    if node is None:
        raise HTTPException(status_code=404)
    return _render(request, "node", article=article, node=node)


@router.get("/works/{work_code}", response_class=HTMLResponse)
async def encyclopedia_work(
    work_code: str, request: Request, db: DBSession, user: CurrentUser
):
    _view(user)
    work = get_work_item(work_code)
    if work is None:
        raise HTTPException(status_code=404)
    catalog = await public_catalog(db)
    current = {row["technology"].id: row for row in catalog["technologies"]}
    if not current:
        raise HTTPException(status_code=404)
    result = await db.execute(
        select(TechnologyWorkStep.technology_id).where(
            TechnologyWorkStep.work_code == work_code,
            TechnologyWorkStep.technology_id.in_(current),
        )
    )
    technologies = tuple(current[item] for item in dict.fromkeys(result.scalars().all()))
    if not technologies:
        raise HTTPException(status_code=404)
    return _render(request, "work", work=work, technologies=technologies)
