from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ValidationError
from app.services.admin_user_role_management import (
    DISABLE_CONFIRMATION,
    assign_company_admin,
    assign_role_to_user,
    assign_workspace_to_user,
    disable_user_account,
    get_user_role_admin_detail,
    get_user_role_admin_history,
    get_user_role_admin_overview,
    moderate_company_workspace,
    require_user_role_admin,
    revoke_company_admin,
    save_user_type_access_matrix_changes,
    set_company_employee_module_access,
    set_company_employee_widget_access,
)


router = APIRouter(prefix="/admin/users-roles/view", tags=["admin-users-roles-view"])
ui_router = APIRouter(prefix="/app/users-roles", tags=["admin-users-roles-ui"])
templates = Jinja2Templates(directory="templates")


def _module3_template_context(
    *,
    mode: str,
    overview: dict,
    detail: dict | None = None,
    detail_error: dict | None = None,
) -> dict:
    return {
        "mode": mode,
        "overview": overview,
        "detail": detail,
        "detail_error": detail_error,
        "disable_confirmation": DISABLE_CONFIRMATION,
        "atom_topbar_current_block": "Модуль №3: Пользователи и роли",
        "atom_topbar_profile_name": "Admin",
    }


async def _render_users_roles_list(request: Request, db: DBSession, actor: CurrentUser):
    overview = await get_user_role_admin_overview(db, actor)
    return templates.TemplateResponse(
        request,
        "admin_users_roles.html",
        _module3_template_context(mode="list", overview=overview),
    )


async def _render_user_card(request: Request, db: DBSession, user_id: str, actor: CurrentUser):
    overview = await get_user_role_admin_overview(db, actor)
    try:
        parsed_user_id = UUID(str(user_id))
        detail = await get_user_role_admin_detail(
            db,
            parsed_user_id,
            actor,
            profile_subject=request.query_params.get("profile"),
        )
    except ValueError:
        return _render_user_card_error(request, overview, status_code=404)
    except HTTPException as exc:
        return _render_user_card_error(request, overview, status_code=exc.status_code)
    return templates.TemplateResponse(
        request,
        "admin_users_roles.html",
        _module3_template_context(mode="detail", overview=overview, detail=detail),
    )


def _render_user_card_error(request: Request, overview: dict, *, status_code: int):
    detail_error = {
        "title": "Карточка не найдена",
        "message": "Пользователь или компания недоступны для просмотра. Вернитесь к списку и выберите существующую запись.",
        "backUrl": "/app/users-roles#users",
    }
    return templates.TemplateResponse(
        request,
        "admin_users_roles.html",
        _module3_template_context(mode="detail", overview=overview, detail_error=detail_error),
        status_code=status_code,
    )


@router.get("", response_class=HTMLResponse)
async def admin_users_roles_view(request: Request, db: DBSession, user: CurrentUser):
    return await _render_users_roles_list(request, db, user)


@ui_router.get("", response_class=HTMLResponse)
async def admin_users_roles_app_view(request: Request, db: DBSession, user: CurrentUser):
    return await _render_users_roles_list(request, db, user)


@ui_router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_card_app_view(user_id: str, request: Request, db: DBSession, user: CurrentUser):
    return await _render_user_card(request, db, user_id, user)

@router.get("/users")
async def admin_users_tab_redirect(user: CurrentUser):
    require_user_role_admin(user)
    return RedirectResponse("/api/v1/admin/users-roles/view#users", status_code=307)


@router.get("/access")
async def admin_access_tab_redirect(user: CurrentUser):
    require_user_role_admin(user)
    return RedirectResponse("/api/v1/admin/users-roles/view#access-matrix", status_code=307)


@router.get("/access-matrix")
async def admin_access_matrix_tab_redirect(user: CurrentUser):
    require_user_role_admin(user)
    return RedirectResponse("/api/v1/admin/users-roles/view#access-matrix", status_code=307)


@router.get("/history", response_class=HTMLResponse)
async def admin_history_view(request: Request, db: DBSession, user: CurrentUser):
    history_page = await get_user_role_admin_history(db, user)
    return templates.TemplateResponse(
        request,
        "admin_users_roles_history.html",
        {
            "historyPage": history_page,
            "atom_topbar_current_block": "Модуль №3: История изменений",
            "atom_topbar_profile_name": "Admin",
        },
    )


@router.get("/history/full")
async def admin_history_full_redirect(user: CurrentUser):
    require_user_role_admin(user)
    return RedirectResponse("/api/v1/admin/users-roles/view/history", status_code=307)


@router.get("/settings")
async def admin_settings_tab_redirect(user: CurrentUser):
    require_user_role_admin(user)
    return RedirectResponse("/api/v1/admin/users-roles/view#settings", status_code=307)


@router.get("/docs", response_class=HTMLResponse)
async def admin_users_roles_docs_view(request: Request, user: CurrentUser):
    require_user_role_admin(user)
    return templates.TemplateResponse(
        request,
        "admin_users_roles_docs.html",
        {
            "atom_topbar_current_block": "Модуль №3: Документация",
            "atom_topbar_profile_name": "Admin",
        },
    )


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_card_view(user_id: UUID, request: Request, db: DBSession, user: CurrentUser):
    return await _render_user_card(request, db, str(user_id), user)

@router.post("/users/{user_id}/roles")
async def admin_assign_user_role(
    user_id: UUID,
    db: DBSession,
    user: CurrentUser,
    role_code: str = Form(...),
    workspace_id: str | None = Form(None),
):
    require_user_role_admin(user)
    await assign_role_to_user(
        db,
        actor=user,
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
    user: CurrentUser,
    workspace_id: str = Form(...),
    role_code: str = Form(...),
):
    require_user_role_admin(user)
    await assign_workspace_to_user(
        db,
        actor=user,
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
    user: CurrentUser,
    workspace_id: str = Form(...),
):
    require_user_role_admin(user)
    await assign_company_admin(
        db,
        actor=user,
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
    user: CurrentUser,
    workspace_id: str = Form(...),
):
    require_user_role_admin(user)
    await revoke_company_admin(
        db,
        actor=user,
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
    user: CurrentUser,
    confirmation: str = Form(...),
):
    require_user_role_admin(user)
    await disable_user_account(
        db,
        actor=user,
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
    user: CurrentUser,
    workspace_id: str = Form(...),
    module_code: str = Form(...),
    access_level: str = Form(...),
    access_scope: str = Form("OWN"),
):
    require_user_role_admin(user)
    await set_company_employee_module_access(
        db,
        actor=user,
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
        module_code=module_code,
        access_level=access_level,
        access_scope=access_scope,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}#profile-module-access",
        status_code=303,
    )


@router.post("/users/{user_id}/widget-access")
async def admin_set_user_widget_access(
    user_id: UUID,
    db: DBSession,
    user: CurrentUser,
    workspace_id: str = Form(...),
    widget_code: str = Form(...),
    access_level: str = Form(...),
    access_scope: str = Form("OWN"),
):
    require_user_role_admin(user)
    await set_company_employee_widget_access(
        db,
        actor=user,
        user_id=user_id,
        workspace_id=_required_uuid(workspace_id, "workspace_id"),
        widget_code=widget_code,
        access_level=access_level,
        access_scope=access_scope,
    )
    await db.commit()
    return RedirectResponse(
        f"/api/v1/admin/users-roles/view/users/{user_id}#profile-module-access",
        status_code=303,
    )


@router.post("/workspaces/{workspace_id}/moderation")
async def admin_moderate_company_workspace(
    workspace_id: UUID,
    db: DBSession,
    user: CurrentUser,
    decision: str = Form(...),
):
    require_user_role_admin(user)
    await moderate_company_workspace(
        db,
        actor=user,
        workspace_id=workspace_id,
        decision=decision,
    )
    await db.commit()
    return RedirectResponse(
        "/api/v1/admin/users-roles/view#verification-queue",
        status_code=303,
    )

@router.post("/access-matrix")
async def admin_save_user_type_access_matrix(
    db: DBSession,
    user: CurrentUser,
    matrix_payload: str = Form("{}"),
):
    require_user_role_admin(user)
    try:
        payload = json.loads(matrix_payload or "{}")
    except json.JSONDecodeError as exc:
        raise ValidationError("Invalid access matrix payload.") from exc
    await save_user_type_access_matrix_changes(
        db,
        actor=user,
        matrix_payload=payload,
    )
    await db.commit()
    return RedirectResponse(
        "/api/v1/admin/users-roles/view#access-matrix",
        status_code=303,
    )

def _optional_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    return _required_uuid(value, "workspace_id")


def _required_uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError(f"Invalid {field_name}.") from exc
