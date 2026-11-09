from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.access_scopes import AccessScope
from app.core.permission_guard import require_permission
from app.models.module2_technology import MODULE2_OWNER_CODE, TechnologyWorkStep
from app.services.module1_work_catalog import get_work_item
from app.services.module2_content_catalog import category_tree, list_categories
from app.services.module2_encyclopedia import (
    public_catalog,
    public_category,
    public_technology,
    technology_article,
)
from app.services.module2_workbench import workbench_permissions
from app.services.module2_encyclopedia_editorial import MATERIAL_NAMES, WORK_STEP_GUIDANCE


router = APIRouter(prefix="/module2/encyclopedia", tags=["module2-encyclopedia"])
templates = Jinja2Templates(directory="templates")
ILLUSTRATION_DIR = Path(__file__).resolve().parents[2] / "assets" / "module2_encyclopedia"


def _view(user: CurrentUser) -> None:
    require_permission(user, MODULE2_OWNER_CODE, "VIEW", scope=AccessScope.LIMITED)


def _render(request: Request, view: str, **context):
    nav_active = "categories" if view in {"category", "category_list"} else (
        "overview" if view == "index" else "technologies"
    )
    return templates.TemplateResponse(
        request,
        "module2_encyclopedia.html",
        {"view": view, "m2_nav_active": nav_active,
         "atom_topbar_current_block": "Модуль №2: Энциклопедия", **context},
    )


@router.get("/entry", include_in_schema=False)
async def module2_entry(user: CurrentUser):
    _view(user)
    target = "/api/v1/admin/module2/workbench" if workbench_permissions(user)["edit"] else "/api/v1/module2/encyclopedia"
    return RedirectResponse(target, status_code=303)


@router.get("/navigation", include_in_schema=False)
async def encyclopedia_navigation(db: DBSession, user: CurrentUser):
    _view(user)
    rows = category_tree(await list_categories(db), public=True)
    return {"categories": [
        {"code": row["category"].code, "name": row["category"].name}
        for row in rows if row["depth"] == 0
    ]}


@router.get("/assets/categories", include_in_schema=False)
async def encyclopedia_category_illustrations(user: CurrentUser):
    _view(user)
    return FileResponse(ILLUSTRATION_DIR / "categories.svg", media_type="image/svg+xml",
                        headers={"Cache-Control": "private, max-age=3600"})


@router.get("", response_class=HTMLResponse)
async def encyclopedia_index(request: Request, db: DBSession, user: CurrentUser):
    _view(user)
    query = str(request.query_params.get("q") or "").strip()[:120]
    return _render(request, "index", catalog=await public_catalog(db, query), query=query,
                   can_workbench=workbench_permissions(user)["edit"])


@router.get("/categories", response_class=HTMLResponse)
async def encyclopedia_categories(request: Request, db: DBSession, user: CurrentUser):
    _view(user)
    query = str(request.query_params.get("q") or "").strip()[:120]
    return _render(request, "category_list", catalog=await public_catalog(db, query), query=query,
                   can_workbench=workbench_permissions(user)["edit"])


@router.get("/technologies", response_class=HTMLResponse)
async def encyclopedia_technologies(request: Request, db: DBSession, user: CurrentUser):
    _view(user)
    query = str(request.query_params.get("q") or "").strip()[:120]
    return _render(request, "technology_list", catalog=await public_catalog(db, query), query=query,
                   can_workbench=workbench_permissions(user)["edit"])


@router.get("/categories/{category_code}", response_class=HTMLResponse)
async def encyclopedia_category(
    category_code: str, request: Request, db: DBSession, user: CurrentUser
):
    _view(user)
    category = await public_category(db, category_code)
    if category is None:
        raise HTTPException(status_code=404)
    return _render(request, "category", can_workbench=workbench_permissions(user)["edit"], **category)


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
    return _render(request, "technology", article=await _article(db, technology_code),
                   can_workbench=workbench_permissions(user)["edit"])


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
    return _render(request, "material", article=article, requirement=requirement,
                   can_workbench=workbench_permissions(user)["edit"])


@router.get("/technologies/{technology_code}/nodes/{node_code}", response_class=HTMLResponse)
async def encyclopedia_node(
    technology_code: str, node_code: str, request: Request, db: DBSession, user: CurrentUser
):
    _view(user)
    article = await _article(db, technology_code)
    node = next((item for item in article["nodes"] if item.code == node_code), None)
    if node is None:
        raise HTTPException(status_code=404)
    return _render(request, "node", article=article, node=node,
                   can_workbench=workbench_permissions(user)["edit"])


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
        select(TechnologyWorkStep).where(
            TechnologyWorkStep.work_code == work_code,
            TechnologyWorkStep.technology_id.in_(current),
        )
    )
    steps = tuple(result.scalars().all())
    technologies = tuple(current[item] for item in dict.fromkeys(step.technology_id for step in steps))
    if not technologies:
        raise HTTPException(status_code=404)
    guidance = WORK_STEP_GUIDANCE.get(work_code)
    return _render(request, "work", work=work, technologies=technologies, guidance=guidance,
                   instructions=tuple(dict.fromkeys(step.instructions for step in steps if step.instructions)),
                   material_names=tuple(MATERIAL_NAMES[code] for code in guidance[2] if code in MATERIAL_NAMES) if guidance else (),
                   can_workbench=workbench_permissions(user)["edit"])
