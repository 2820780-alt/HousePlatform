from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import DBSession
from app.core.exceptions import ValidationError
from app.core.permission_guard import DEV_USER
from app.services.admin_user_role_management import (
    DISABLE_CONFIRMATION,
    assign_company_admin,
    assign_role_to_user,
    assign_workspace_to_user,
    disable_user_account,
    get_user_role_admin_detail,
    get_user_role_admin_overview,
    revoke_company_admin,
    save_user_type_access_matrix_changes,
    set_company_employee_module_access,
    set_company_employee_widget_access,
)


router = APIRouter(prefix="/admin/users-roles/view", tags=["admin-users-roles-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_users_roles_view(request: Request, db: DBSession):
    actor = _dev_actor()
    overview = await get_user_role_admin_overview(db, actor)
    return templates.TemplateResponse(
        request,
        "admin_users_roles.html",
        {
            "mode": "list",
            "overview": overview,
            "detail": None,
            "disable_confirmation": DISABLE_CONFIRMATION,
            "atom_topbar_current_block": "Модуль №3: Пользователи и роли",
            "atom_topbar_profile_name": "Admin",
        },
    )


@router.get("/users")
async def admin_users_tab_redirect():
    return RedirectResponse("/api/v1/admin/users-roles/view#users", status_code=307)


@router.get("/access")
async def admin_access_tab_redirect():
    return RedirectResponse("/api/v1/admin/users-roles/view#access-matrix", status_code=307)


@router.get("/access-matrix")
async def admin_access_matrix_tab_redirect():
    return RedirectResponse("/api/v1/admin/users-roles/view#access-matrix", status_code=307)


@router.get("/history")
async def admin_history_tab_redirect():
    return RedirectResponse("/api/v1/admin/users-roles/view#audit-log", status_code=307)


@router.get("/settings")
async def admin_settings_tab_redirect():
    return RedirectResponse("/api/v1/admin/users-roles/view#settings", status_code=307)


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_card_view(user_id: UUID, request: Request, db: DBSession):
    actor = _dev_actor()
    overview = await get_user_role_admin_overview(db, actor)
    detail = await get_user_role_admin_detail(db, user_id, actor)
    return templates.TemplateResponse(
        request,
        "admin_users_roles.html",
        {
            "mode": "detail",
            "overview": overview,
            "detail": detail,
            "disable_confirmation": DISABLE_CONFIRMATION,
            "atom_topbar_current_block": "Модуль №3: Пользователи и роли",
            "atom_topbar_profile_name": "Admin",
        },
    )


@router.post("/users/{user_id}/roles")
async def admin_assign_user_role(
    user_id: UUID,
    db: DBSession,
    role_code: str = Form(...),
    workspace_id: str | None = Form(None),
):
    await assign_role_to_user(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        role_code=role_code,
        workspace_id=_optional_uuid(workspace_id),
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}",
        status_code=303,
    )


@router.post("/users/{user_id}/workspace")
async def admin_assign_user_workspace(
    user_id: UUID,
    db: DBSession,
    workspace_id: str = Form(...),
    role_code: str = Form(...),
):
    await assign_workspace_to_user(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
        role_code=role_code,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}",
        status_code=303,
    )


@router.post("/users/{user_id}/company-admin")
async def admin_assign_company_admin(
    user_id: UUID,
    db: DBSession,
    workspace_id: str = Form(...),
):
    await assign_company_admin(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}",
        status_code=303,
    )


@router.post("/users/{user_id}/company-admin/revoke")
async def admin_revoke_company_admin(
    user_id: UUID,
    db: DBSession,
    workspace_id: str = Form(...),
):
    await revoke_company_admin(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}",
        status_code=303,
    )


@router.post("/users/{user_id}/disable")
async def admin_disable_user(
    user_id: UUID,
    db: DBSession,
    confirmation: str = Form(...),
):
    await disable_user_account(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        confirmation=confirmation,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}",
        status_code=303,
    )


@router.post("/users/{user_id}/module-access")
async def admin_set_user_module_access(
    user_id: UUID,
    db: DBSession,
    workspace_id: str = Form(...),
    module_code: str = Form(...),
    access_level: str = Form(...),
    access_scope: str = Form("OWN"),
):
    await set_company_employee_module_access(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
        module_code=module_code,
        access_level=access_level,
        access_scope=access_scope,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}#access-matrix-detail",
        status_code=303,
    )


@router.post("/users/{user_id}/widget-access")
async def admin_set_user_widget_access(
    user_id: UUID,
    db: DBSession,
    workspace_id: str = Form(...),
    widget_code: str = Form(...),
    access_level: str = Form(...),
    access_scope: str = Form("OWN"),
):
    await set_company_employee_widget_access(
        db,
        actor=_dev_actor(),
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
        widget_code=widget_code,
        access_level=access_level,
        access_scope=access_scope,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}#access-matrix-detail",
        status_code=303,
    )


@router.post("/access-matrix")
async def admin_save_user_type_access_matrix(
    db: DBSession,
    matrix_payload: str = Form("{}"),
):
    try:
        payload = json.loads(matrix_payload or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid access matrix payload.") from exc
    await save_user_type_access_matrix_changes(
        db,
        actor=_dev_actor(),
        matrix_payload=payload,
    )
    await db.commit()
    return RedirectResponse(
        "/api/v1/admin/users-roles/view#access-matrix",
        status_code=303,
    )


def _dev_actor() -> dict[str, str]:
    return DEV_USER


def _optional_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    return _required_uuid(value, "workspace_id")


def _required_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError(f"Invalid {field_name}.") from exc
