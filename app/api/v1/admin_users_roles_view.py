from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import DBSession
from app.core.exceptions import ValidationError
from app.core.permission_guard import DEV_USER
from app.services.admin_user_role_management import (
    DISABLE_CONFIRMATION,
    assign_role_to_user,
    assign_workspace_to_user,
    disable_user_account,
    get_user_role_admin_detail,
    get_user_role_admin_overview,
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
            "atom_topbar_current_block": "Пользователи и роли",
            "atom_topbar_profile_name": "Администратор",
        },
    )


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
            "atom_topbar_current_block": "Карточка пользователя",
            "atom_topbar_profile_name": "Администратор",
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
