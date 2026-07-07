from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, ValidationError
from app.core.permission_guard import require_permission
from app.services import user_module_quick_actions as quick_action_service


router = APIRouter(prefix="/quick-actions/user-module", tags=["user-module-quick-actions"])


class UserQuickActionCreateRequest(BaseModel):
    sourceModuleCode: str
    actionKey: str
    title: str
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    featureCode: str | None = None
    description: str | None = None
    icon: str | None = None
    route: str | None = None
    deepLink: str | None = None
    savedConfigRef: str | None = None
    configSnapshot: dict[str, Any] | None = None
    pinToAtomCard: bool = False
    atomCardAccent: str | None = None
    atomCardOrder: int | None = Field(default=None, ge=1)


class UserQuickActionUpdateRequest(BaseModel):
    title: str | None = None
    order: int | None = Field(default=None, ge=1)
    isVisibleInModuleBar: bool | None = None
    isPinnedToAtomCard: bool | None = None
    atomCardOrder: int | None = Field(default=None, ge=1)
    atomCardAccent: str | None = None


class UserQuickActionRenameRequest(BaseModel):
    title: str


class UserQuickActionReorderRequest(BaseModel):
    sourceModuleCode: str
    orderedIds: list[UUID]


class UserQuickActionRunRequest(BaseModel):
    sourceModuleCode: str
    actionKey: str
    disabledModuleCodes: list[str] = Field(default_factory=list)
    availableActionKeys: list[str] = Field(default_factory=list)
    brokenConfigRefs: list[str] = Field(default_factory=list)


class UserQuickActionPinAtomCardRequest(BaseModel):
    atomCardAccent: str | None = None
    atomCardOrder: int | None = Field(default=None, ge=1)


@router.get("")
async def list_user_module_quick_actions(
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
    includeInactive: bool = Query(False),
):
    actions = await quick_action_service.getUserModuleQuickActions(
        db,
        _current_user_id(user),
        sourceModuleCode,
        _context(user, source_module_code=sourceModuleCode),
    )
    if includeInactive is not True:
        actions = [action for action in actions if _value(action, "status") == quick_action_service.ACTIVE_STATUS]
    return [_action_to_dict(action) for action in actions]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user_module_quick_action(
    data: UserQuickActionCreateRequest,
    db: DBSession,
    user: CurrentUser,
):
    _require_action_access(user, data.sourceModuleCode, data.actionKey)
    payload = data.model_dump(exclude_none=True)
    payload["userId"] = _current_user_id(user)
    action = await quick_action_service.addUserModuleQuickAction(
        db,
        payload,
        _context(user, source_module_code=data.sourceModuleCode, action_key=data.actionKey),
    )
    if data.atomCardAccent or data.atomCardOrder:
        action = await quick_action_service.updateUserModuleQuickAction(
            db,
            _value(action, "id"),
            {
                "atomCardAccent": data.atomCardAccent,
                "atomCardOrder": data.atomCardOrder,
            },
            _context(user, source_module_code=data.sourceModuleCode, action_key=data.actionKey),
        )
    return _action_to_dict(action)


@router.patch("/{quick_action_id}")
async def update_user_module_quick_action(
    quick_action_id: UUID,
    data: UserQuickActionUpdateRequest,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    action = await quick_action_service.updateUserModuleQuickAction(
        db,
        quick_action_id,
        data.model_dump(exclude_unset=True),
        _context(user, source_module_code=sourceModuleCode),
    )
    return _action_to_dict(action)


@router.post("/{quick_action_id}/rename")
async def rename_user_module_quick_action(
    quick_action_id: UUID,
    data: UserQuickActionRenameRequest,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    action = await quick_action_service.updateUserModuleQuickAction(
        db,
        quick_action_id,
        {"title": data.title},
        _context(user, source_module_code=sourceModuleCode),
    )
    return _action_to_dict(action)


@router.delete("/{quick_action_id}")
async def remove_user_module_quick_action(
    quick_action_id: UUID,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    await quick_action_service.removeUserModuleQuickAction(db, quick_action_id, _context(user, source_module_code=sourceModuleCode))
    return {"removed": True, "quickActionId": str(quick_action_id)}


@router.post("/reorder")
async def reorder_user_module_quick_actions(
    data: UserQuickActionReorderRequest,
    db: DBSession,
    user: CurrentUser,
):
    actions = await quick_action_service.reorderUserModuleQuickActions(
        db,
        data.sourceModuleCode,
        data.orderedIds,
        _context(user, source_module_code=data.sourceModuleCode),
    )
    return [_action_to_dict(action) for action in actions]


@router.post("/{quick_action_id}/pin-module-bar")
async def pin_user_module_quick_action_to_module_bar(
    quick_action_id: UUID,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    action = await quick_action_service.updateUserModuleQuickAction(
        db,
        quick_action_id,
        {"isVisibleInModuleBar": True},
        _context(user, source_module_code=sourceModuleCode),
    )
    return _action_to_dict(action)


@router.post("/{quick_action_id}/unpin-module-bar")
async def unpin_user_module_quick_action_from_module_bar(
    quick_action_id: UUID,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    action = await quick_action_service.updateUserModuleQuickAction(
        db,
        quick_action_id,
        {"isVisibleInModuleBar": False},
        _context(user, source_module_code=sourceModuleCode),
    )
    return _action_to_dict(action)


@router.post("/{quick_action_id}/pin-atom-card")
async def pin_user_module_quick_action_to_atom_card(
    quick_action_id: UUID,
    data: UserQuickActionPinAtomCardRequest,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    payload = data.model_dump(exclude_unset=True)
    payload["isPinnedToAtomCard"] = True
    action = await quick_action_service.updateUserModuleQuickAction(
        db,
        quick_action_id,
        payload,
        _context(user, source_module_code=sourceModuleCode),
    )
    return _action_to_dict(action)


@router.post("/{quick_action_id}/unpin-atom-card")
async def unpin_user_module_quick_action_from_atom_card(
    quick_action_id: UUID,
    db: DBSession,
    user: CurrentUser,
    sourceModuleCode: str = Query(..., min_length=1),
):
    action = await quick_action_service.unpinQuickActionFromAtomCard(db, quick_action_id, _context(user, source_module_code=sourceModuleCode))
    return _action_to_dict(action)


@router.post("/{quick_action_id}/validate")
async def validate_user_module_quick_action_before_run(
    quick_action_id: UUID,
    data: UserQuickActionRunRequest,
    db: DBSession,
    user: CurrentUser,
):
    _require_action_access(user, data.sourceModuleCode, data.actionKey)
    result = await quick_action_service.validateQuickActionBeforeRun(
        db,
        quick_action_id,
        _run_context(user, data),
    )
    _ensure_result_matches_request(result, data)
    return _result_to_dict(result)


@router.post("/{quick_action_id}/run")
async def run_user_module_quick_action(
    quick_action_id: UUID,
    data: UserQuickActionRunRequest,
    db: DBSession,
    user: CurrentUser,
):
    _require_action_access(user, data.sourceModuleCode, data.actionKey)
    validation = await quick_action_service.validateQuickActionBeforeRun(
        db,
        quick_action_id,
        _run_context(user, data),
    )
    _ensure_result_matches_request(validation, data)
    if _value(validation, "status") != "READY":
        return _result_to_dict(validation)
    result = await quick_action_service.runUserQuickAction(
        db,
        quick_action_id,
        _run_context(user, data),
    )
    _ensure_result_matches_request(result, data)
    return _result_to_dict(result)


def _context(
    user: Any,
    *,
    source_module_code: str | None = None,
    action_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = {
        "userId": _current_user_id(user),
    }
    if source_module_code:
        context["sourceModuleCode"] = source_module_code
        context["currentModuleCode"] = source_module_code
    if action_key:
        context["actionKey"] = action_key
    if extra:
        context.update(extra)
    return context


def _run_context(user: Any, data: UserQuickActionRunRequest) -> dict[str, Any]:
    return _context(
        user,
        source_module_code=data.sourceModuleCode,
        action_key=data.actionKey,
        extra={
            "disabledModuleCodes": data.disabledModuleCodes,
            "availableActionKeys": data.availableActionKeys,
            "brokenConfigRefs": data.brokenConfigRefs,
        },
    )


def _require_action_access(user: Any, source_module_code: str, action_key: str) -> None:
    try:
        require_permission(user, source_module_code, action_key)
    except ForbiddenError:
        raise
    except Exception as exc:
        raise ForbiddenError("Quick action is not allowed for current user.") from exc


def _ensure_result_matches_request(result: Any, data: UserQuickActionRunRequest) -> None:
    if _value(result, "sourceModuleCode") != data.sourceModuleCode:
        raise ForbiddenError("Quick action source module mismatch.")
    if _value(result, "actionKey") != data.actionKey:
        raise ForbiddenError("Quick action actionKey mismatch.")


def _current_user_id(user: Any) -> str:
    user_id = _value(user, "id") or _value(user, "userId") or _value(user, "user_id")
    if not user_id:
        raise ValidationError("Current user id is required for quick actions.")
    return str(user_id)


def _action_to_dict(action: Any) -> dict[str, Any]:
    return {
        "quickActionId": str(_value(action, "id")),
        "userId": str(_value(action, "user_id")),
        "workspaceId": _string_or_none(_value(action, "workspace_id")),
        "activeRegionCode": _value(action, "active_region_code"),
        "sourceModuleCode": _value(action, "source_module_code"),
        "featureCode": _value(action, "feature_code"),
        "actionKey": _value(action, "action_key"),
        "title": _value(action, "title"),
        "description": _value(action, "description"),
        "icon": _value(action, "icon"),
        "route": _value(action, "route"),
        "deepLink": _value(action, "deep_link"),
        "savedConfigRef": _value(action, "saved_config_ref"),
        "configSnapshot": _value(action, "config_snapshot"),
        "sortOrder": _value(action, "order"),
        "isVisibleInModuleBar": bool(_value(action, "is_visible_in_module_bar")),
        "isPinnedToAtomCard": bool(_value(action, "is_pinned_to_atom_card")),
        "atomCardOrder": _value(action, "atom_card_order"),
        "atomCardAccent": _value(action, "atom_card_accent"),
        "status": _value(action, "status"),
        "createdAt": _iso_or_none(_value(action, "created_at")),
        "updatedAt": _iso_or_none(_value(action, "updated_at")),
    }


def _result_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    if isinstance(result, dict):
        return dict(result)
    raise ValidationError("Unsupported quick action result.")


def _value(source: Any, name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
