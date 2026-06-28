from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import DBSession
from app.core.permission_guard import DEV_USER
from app.services.admin_module_registry_management import (
    ARCHIVE_CONFIRMATION,
    archive_module_registry_item,
    get_module_registry_detail,
    get_module_registry_overview,
    update_module_registry_item,
)


router = APIRouter(prefix="/admin/module-registry/view", tags=["admin-module-registry-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_module_registry_view(request: Request, db: DBSession):
    actor = _dev_actor()
    overview = await get_module_registry_overview(db, actor)
    detail = None
    if overview["modules"]:
        detail = await get_module_registry_detail(db, overview["modules"][0]["moduleCode"], actor)
    return _template(request, overview, detail)


@router.get("/{module_code}", response_class=HTMLResponse)
async def admin_module_registry_detail_view(module_code: str, request: Request, db: DBSession):
    actor = _dev_actor()
    overview = await get_module_registry_overview(db, actor)
    detail = await get_module_registry_detail(db, module_code, actor)
    return _template(request, overview, detail)


@router.post("/{module_code}/update")
async def admin_update_module_registry_item(
    module_code: str,
    db: DBSession,
    status: str = Form(...),
    visible_in_sidebar: bool = Form(False),
    visible_on_dashboard: bool = Form(False),
    visible_on_atom_map: bool = Form(False),
    available_for_widgets: bool = Form(False),
):
    await update_module_registry_item(
        db,
        actor=_dev_actor(),
        module_code=module_code,
        status=status,
        visible_in_sidebar=visible_in_sidebar,
        visible_on_dashboard=visible_on_dashboard,
        visible_on_atom_map=visible_on_atom_map,
        available_for_widgets=available_for_widgets,
    )
    await db.commit()
    return RedirectResponse(f"/api/v1/admin/module-registry/view/{module_code}", status_code=303)


@router.post("/{module_code}/archive")
async def admin_archive_module_registry_item(
    module_code: str,
    db: DBSession,
    confirmation: str = Form(...),
):
    await archive_module_registry_item(
        db,
        actor=_dev_actor(),
        module_code=module_code,
        confirmation=confirmation,
    )
    await db.commit()
    return RedirectResponse(f"/api/v1/admin/module-registry/view/{module_code}", status_code=303)


def _template(request: Request, overview: dict, detail: dict | None):
    return templates.TemplateResponse(
        request,
        "admin_module_registry.html",
        {
            "overview": overview,
            "detail": detail,
            "archive_confirmation": ARCHIVE_CONFIRMATION,
            "atom_topbar_current_block": "Реестр модулей",
            "atom_topbar_profile_name": "Администратор",
        },
    )


def _dev_actor() -> dict[str, str]:
    return DEV_USER
