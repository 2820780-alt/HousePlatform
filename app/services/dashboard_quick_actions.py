from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_scopes import AccessScope
from app.core.permission_guard import can
from app.models.user_module_quick_action import UserModuleQuickAction
from app.services.dashboard_auth_adapters import can_access_module
from app.services.dashboard_module_registry import get_canonical_module_code
from app.services.user_module_quick_actions import ACTIVE_STATUS, MAX_ATOM_CARD_PINNED_ACTIONS

ATOM_CARD_QUICK_ACTION_LIMIT = MAX_ATOM_CARD_PINNED_ACTIONS


@dataclass(frozen=True)
class DashboardQuickAction:
    actionCode: str
    label: str
    href: str
    icon: str
    moduleCode: str
    featureCode: str | None = None
    contextCode: str | None = None
    maxSurface: str = "BOTH"
    cabinetTypes: tuple[str, ...] = ("ADMIN",)
    requiresConfirmation: bool = False
    mock: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


QUICK_ACTION_REGISTRY: tuple[DashboardQuickAction, ...] = ()
DEFAULT_ATOM_CARD_ACTION_CODES: dict[str, tuple[str, ...]] = {}


def get_quick_actions_for_dashboard(user_context: Any, cabinet_context: dict[str, Any]) -> list[dict[str, Any]]:
    """Legacy compatibility hook.

    Dashboard quick actions are no longer built from registry/preset codes. The
    active dashboard-card source is user_module_quick_actions via
    get_user_atom_card_quick_action_options().
    """

    return []


def get_atom_card_quick_action_options(
    user_context: Any,
    cabinet_context: dict[str, Any],
    module_code: str,
    selected_action_codes: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Legacy compatibility hook for preset-based atom card actions."""

    return []


def get_atom_card_quick_actions(
    user_context: Any,
    cabinet_context: dict[str, Any],
    module_code: str,
    selected_action_codes: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    return []


async def get_user_atom_card_quick_action_options(
    db: AsyncSession,
    user_context: Any,
    module_code: str,
    cabinet_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return user-pinned quick actions for a dashboard module card.

    The source of truth is user_module_quick_actions. Registry defaults,
    dashboard presets, and role defaultQuickActionCodes are intentionally not
    consulted here.
    """

    user_id = _current_user_uuid(user_context)
    canonical_module_code = get_canonical_module_code(module_code) or module_code
    if user_id is None or not can_access_module(user_context, canonical_module_code):
        return []

    actions = await _load_pinned_user_actions(db, user_id, canonical_module_code)
    permission_context = {**_context_dict(user_context), **(cabinet_context or {})}
    options: list[dict[str, Any]] = []
    for action in actions:
        if not _is_dashboard_visible_action(action, user_id, canonical_module_code, user_context, permission_context):
            continue
        options.append(_dashboard_action_from_user_action(action))
        if len(options) >= ATOM_CARD_QUICK_ACTION_LIMIT:
            break
    return options


async def get_user_atom_card_quick_actions(
    db: AsyncSession,
    user_context: Any,
    module_code: str,
    cabinet_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return await get_user_atom_card_quick_action_options(
        db,
        user_context,
        module_code,
        cabinet_context=cabinet_context,
    )


async def _load_pinned_user_actions(
    db: AsyncSession,
    user_id: UUID,
    module_code: str,
) -> list[UserModuleQuickAction]:
    result = await db.execute(
        select(UserModuleQuickAction)
        .where(
            UserModuleQuickAction.user_id == user_id,
            UserModuleQuickAction.source_module_code == module_code,
            UserModuleQuickAction.is_pinned_to_atom_card.is_(True),
            UserModuleQuickAction.status == ACTIVE_STATUS,
        )
        .order_by(UserModuleQuickAction.atom_card_order.asc(), UserModuleQuickAction.order.asc())
        .limit(ATOM_CARD_QUICK_ACTION_LIMIT)
    )
    return list(result.scalars().all())


def _is_dashboard_visible_action(
    action: UserModuleQuickAction,
    user_id: UUID,
    module_code: str,
    user_context: Any,
    permission_context: dict[str, Any],
) -> bool:
    action_module_code = get_canonical_module_code(action.source_module_code) or action.source_module_code
    if str(action.user_id) != str(user_id):
        return False
    if action_module_code != module_code:
        return False
    if not action.is_pinned_to_atom_card or action.status != ACTIVE_STATUS:
        return False
    if not can_access_module(user_context, action_module_code):
        return False
    return _can_use_user_action(user_context, action, permission_context)


def _can_use_user_action(
    user_context: Any,
    action: UserModuleQuickAction,
    permission_context: dict[str, Any],
) -> bool:
    module_code = get_canonical_module_code(action.source_module_code) or action.source_module_code
    action_code = _action_permission_code(action)
    if can(user_context, module_code, action_code, AccessScope.GLOBAL):
        return True

    allowed_action_codes = set(str(item) for item in _list_value(permission_context.get("allowedActionCodes")))
    if allowed_action_codes:
        return action_code in allowed_action_codes or action.action_key in allowed_action_codes
    return False


def _action_permission_code(action: UserModuleQuickAction) -> str:
    snapshot = action.config_snapshot if isinstance(action.config_snapshot, dict) else {}
    return str(
        snapshot.get("permissionKey")
        or snapshot.get("permission_key")
        or snapshot.get("requiredActionCode")
        or snapshot.get("required_action_code")
        or action.action_key
    )


def _dashboard_action_from_user_action(action: UserModuleQuickAction) -> dict[str, Any]:
    return {
        "quickActionId": str(action.id),
        "actionCode": action.action_key,
        "actionKey": action.action_key,
        "label": action.title,
        "title": action.title,
        "href": action.deep_link or action.route or "#",
        "icon": action.icon or "*",
        "moduleCode": action.source_module_code,
        "sourceModuleCode": action.source_module_code,
        "featureCode": action.feature_code,
        "contextCode": None,
        "maxSurface": "MODULE_CARD",
        "cabinetTypes": ("ADMIN",),
        "requiresConfirmation": _requires_confirmation(action),
        "mock": False,
        "isSelected": True,
        "placement": "ATOM_CARD",
        "atomCardOrder": action.atom_card_order,
        "atomCardAccent": action.atom_card_accent or "cyan",
        "status": action.status,
    }


def _requires_confirmation(action: UserModuleQuickAction) -> bool:
    snapshot = action.config_snapshot if isinstance(action.config_snapshot, dict) else {}
    return bool(snapshot.get("requiresConfirmation") or snapshot.get("requires_confirmation"))


def _current_user_uuid(context: Any) -> UUID | None:
    data = _context_dict(context)
    value = data.get("id") or data.get("userId") or data.get("user_id")
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _context_dict(context: Any) -> dict[str, Any]:
    if context is None:
        return {}
    if hasattr(context, "to_template_dict"):
        return context.to_template_dict()
    if hasattr(context, "__dict__") and not isinstance(context, dict):
        return dict(context.__dict__)
    if isinstance(context, dict):
        return context
    return {}


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []
