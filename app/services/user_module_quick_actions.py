from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models.user_module_quick_action import (
    ATOM_CARD_ACCENTS,
    AddUserQuickActionRequest,
    QuickActionRunResult,
    UpdateUserQuickActionRequest,
    UserModuleQuickAction,
)


MAX_MODULE_QUICK_ACTIONS = 9
MAX_ATOM_CARD_PINNED_ACTIONS = 3
ACTIVE_STATUS = "ACTIVE"
LOADING_STATUS = "LOADING"
ERROR_STATUS = "ERROR"
FORBIDDEN_CONFIG_KEYS = {
    "businessPayload",
    "business_payload",
    "resultPayload",
    "result_payload",
    "rawData",
    "raw_data",
    "sourceRows",
    "source_rows",
    "rows",
    "password",
    "token",
}


async def getUserModuleQuickActions(
    db: AsyncSession,
    userId: str | UUID,
    sourceModuleCode: str,
    context: Any | None = None,
) -> list[UserModuleQuickAction]:
    _require_same_user(userId, context)
    _require_module_boundary(sourceModuleCode, context)
    result = await db.execute(
        select(UserModuleQuickAction)
        .where(
            UserModuleQuickAction.user_id == _uuid(userId, "userId"),
            UserModuleQuickAction.source_module_code == sourceModuleCode,
        )
        .order_by(UserModuleQuickAction.order.asc(), UserModuleQuickAction.created_at.asc())
    )
    return list(result.scalars().all())


async def addUserModuleQuickAction(
    db: AsyncSession,
    request: AddUserQuickActionRequest | dict[str, Any],
    context: Any | None = None,
) -> UserModuleQuickAction:
    data = _dict_value(request)
    user_id = _required(data, "userId")
    source_module_code = _required(data, "sourceModuleCode")
    action_key = _required(data, "actionKey")
    title = _required(data, "title")
    _require_same_user(user_id, context)
    _require_module_boundary(source_module_code, context, require_owner_context=True)
    _ensure_safe_config(data.get("configSnapshot"))

    active_count = await _active_count(db, user_id, source_module_code)
    if active_count >= MAX_MODULE_QUICK_ACTIONS:
        raise ValidationError("В этом модуле уже добавлено 9 быстрых действий. Уберите одно действие, чтобы добавить новое.")

    pin_to_atom_card = bool(data.get("pinToAtomCard"))
    if pin_to_atom_card:
        pinned_count = await _pinned_count(db, user_id, source_module_code)
        if pinned_count >= MAX_ATOM_CARD_PINNED_ACTIONS:
            raise ValidationError("На карточке модуля можно закрепить не более 3 быстрых действий.")

    action = UserModuleQuickAction(
        user_id=_uuid(user_id, "userId"),
        workspace_id=_optional_uuid(data.get("workspaceId"), "workspaceId"),
        active_region_code=_string_or_none(data.get("activeRegionCode")),
        source_module_code=source_module_code,
        feature_code=_string_or_none(data.get("featureCode")),
        action_key=action_key,
        title=title,
        description=_string_or_none(data.get("description")),
        icon=_string_or_none(data.get("icon")),
        route=_string_or_none(data.get("route")),
        deep_link=_string_or_none(data.get("deepLink")),
        saved_config_ref=_string_or_none(data.get("savedConfigRef")),
        config_snapshot=data.get("configSnapshot"),
        order=await _next_order(db, user_id, source_module_code),
        is_visible_in_module_bar=True,
        is_pinned_to_atom_card=pin_to_atom_card,
        atom_card_order=await _next_atom_card_order(db, user_id, source_module_code) if pin_to_atom_card else None,
        atom_card_accent=_string_or_none(data.get("atomCardAccent")),
        status=ACTIVE_STATUS,
    )
    _validate_atom_accent(action.atom_card_accent)
    db.add(action)
    await db.flush()
    await db.refresh(action)
    return action


async def removeUserModuleQuickAction(
    db: AsyncSession,
    quickActionId: str | UUID,
    context: Any | None = None,
) -> None:
    action = await _get_action(db, quickActionId)
    _require_same_user(action.user_id, context)
    _require_module_boundary(action.source_module_code, context, require_owner_context=True)
    action.is_pinned_to_atom_card = False
    action.atom_card_order = None
    await db.delete(action)
    await db.flush()
    await _compact_module_order(db, action.user_id, action.source_module_code)
    await _compact_pinned_order(db, action.user_id, action.source_module_code)


async def updateUserModuleQuickAction(
    db: AsyncSession,
    quickActionId: str | UUID,
    payload: UpdateUserQuickActionRequest | dict[str, Any],
    context: Any | None = None,
) -> UserModuleQuickAction:
    action = await _get_action(db, quickActionId)
    data = _dict_value(payload)
    _require_same_user(action.user_id, context)
    _require_module_boundary(action.source_module_code, context, require_owner_context=True)

    if "title" in data and data["title"] is not None:
        action.title = str(data["title"])
    if "order" in data and data["order"] is not None:
        action.order = int(data["order"])
    if "isVisibleInModuleBar" in data and data["isVisibleInModuleBar"] is not None:
        action.is_visible_in_module_bar = bool(data["isVisibleInModuleBar"])
    if "atomCardAccent" in data:
        _validate_atom_accent(data["atomCardAccent"])
        action.atom_card_accent = _string_or_none(data["atomCardAccent"])
    if "atomCardOrder" in data:
        action.atom_card_order = int(data["atomCardOrder"]) if data["atomCardOrder"] is not None else None
    if "isPinnedToAtomCard" in data and data["isPinnedToAtomCard"] is not None:
        if data["isPinnedToAtomCard"]:
            await _ensure_can_pin(db, action)
            action.is_pinned_to_atom_card = True
            if action.atom_card_order is None:
                action.atom_card_order = await _next_atom_card_order(db, action.user_id, action.source_module_code)
        else:
            action.is_pinned_to_atom_card = False
            action.atom_card_order = None

    db.add(action)
    await db.flush()
    await db.refresh(action)
    return action


async def reorderUserModuleQuickActions(
    db: AsyncSession,
    sourceModuleCode: str,
    orderedIds: list[str | UUID],
    context: Any | None = None,
) -> list[UserModuleQuickAction]:
    user_id = _context_user_id(context)
    if not user_id:
        raise ValidationError("userId is required in context for reorderUserModuleQuickActions.")
    _require_module_boundary(sourceModuleCode, context, require_owner_context=True)
    actions = await getUserModuleQuickActions(db, user_id, sourceModuleCode, context)
    by_id = {str(action.id): action for action in actions}
    missing = [str(item) for item in orderedIds if str(item) not in by_id]
    if missing:
        raise ValidationError(f"Unknown quick action ids for module: {', '.join(missing)}")
    for index, action_id in enumerate(orderedIds):
        by_id[str(action_id)].order = index + 1
        db.add(by_id[str(action_id)])
    await db.flush()
    return await getUserModuleQuickActions(db, user_id, sourceModuleCode, context)


async def pinQuickActionToAtomCard(
    db: AsyncSession,
    quickActionId: str | UUID,
    context: Any | None = None,
) -> UserModuleQuickAction:
    action = await _get_action(db, quickActionId)
    _require_same_user(action.user_id, context)
    _require_module_boundary(action.source_module_code, context, require_owner_context=True)
    await _ensure_can_pin(db, action)
    action.is_pinned_to_atom_card = True
    if action.atom_card_order is None:
        action.atom_card_order = await _next_atom_card_order(db, action.user_id, action.source_module_code)
    db.add(action)
    await db.flush()
    await db.refresh(action)
    return action


async def unpinQuickActionFromAtomCard(
    db: AsyncSession,
    quickActionId: str | UUID,
    context: Any | None = None,
) -> UserModuleQuickAction:
    action = await _get_action(db, quickActionId)
    _require_same_user(action.user_id, context)
    _require_module_boundary(action.source_module_code, context, require_owner_context=True)
    action.is_pinned_to_atom_card = False
    action.atom_card_order = None
    db.add(action)
    await db.flush()
    await _compact_pinned_order(db, action.user_id, action.source_module_code)
    await db.refresh(action)
    return action


async def resetUserModuleQuickActions(
    db: AsyncSession,
    userId: str | UUID,
    sourceModuleCode: str,
    context: Any | None = None,
) -> int:
    _require_same_user(userId, context)
    _require_module_boundary(sourceModuleCode, context, require_owner_context=True)
    actions = await getUserModuleQuickActions(db, userId, sourceModuleCode, context)
    for action in actions:
        action.is_pinned_to_atom_card = False
        action.atom_card_order = None
        await db.delete(action)
    await db.flush()
    return len(actions)


async def resetAtomCardPinnedQuickActions(
    db: AsyncSession,
    userId: str | UUID,
    sourceModuleCode: str,
    context: Any | None = None,
) -> int:
    _require_same_user(userId, context)
    _require_module_boundary(sourceModuleCode, context, require_owner_context=True)
    actions = await getAtomCardPinnedActions(db, userId, sourceModuleCode, context)
    for action in actions:
        action.is_pinned_to_atom_card = False
        action.atom_card_order = None
        db.add(action)
    await db.flush()
    return len(actions)


async def getAtomCardPinnedActions(
    db: AsyncSession,
    userId: str | UUID,
    sourceModuleCode: str,
    context: Any | None = None,
) -> list[UserModuleQuickAction]:
    _require_same_user(userId, context)
    _require_module_boundary(sourceModuleCode, context)
    result = await db.execute(
        select(UserModuleQuickAction)
        .where(
            UserModuleQuickAction.user_id == _uuid(userId, "userId"),
            UserModuleQuickAction.source_module_code == sourceModuleCode,
            UserModuleQuickAction.is_pinned_to_atom_card.is_(True),
        )
        .order_by(UserModuleQuickAction.atom_card_order.asc(), UserModuleQuickAction.order.asc())
    )
    return list(result.scalars().all())[:MAX_ATOM_CARD_PINNED_ACTIONS]


async def getAtomCardPinnedActionPayloads(
    db: AsyncSession,
    userId: str | UUID,
    sourceModuleCode: str,
    context: Any | None = None,
) -> list[dict[str, Any]]:
    actions = await getAtomCardPinnedActions(db, userId, sourceModuleCode, context)
    return [_atom_card_payload(action) for action in actions]


async def validateQuickActionBeforeRun(
    db: AsyncSession,
    quickActionId: str | UUID,
    context: Any | None = None,
) -> QuickActionRunResult:
    action = await _get_action(db, quickActionId)
    _require_same_user(action.user_id, context)
    _require_module_boundary(action.source_module_code, context)
    context_data = _dict_value(context)

    if action.status == LOADING_STATUS:
        return _loading(action)
    if action.status != ACTIVE_STATUS:
        return _blocked(action, state=action.status, message=_state_message(action.status))
    disabled_modules = set(_list_value(context_data.get("disabledModuleCodes")))
    if action.source_module_code in disabled_modules:
        return _blocked(action, state="MODULE_DISABLED", message="Модуль-владелец отключен.")
    available_keys = set(_list_value(context_data.get("availableActionKeys")))
    if available_keys and action.action_key not in available_keys:
        return _blocked(action, state="NO_LONGER_AVAILABLE", message="Это действие больше недоступно в модуле.")
    broken_refs = set(_list_value(context_data.get("brokenConfigRefs")))
    if action.saved_config_ref and action.saved_config_ref in broken_refs:
        return _blocked(action, state="BROKEN_CONFIG", message="Настройки этого быстрого действия устарели.")

    return QuickActionRunResult(
        status="READY",
        quickActionId=str(action.id),
        sourceModuleCode=action.source_module_code,
        actionKey=action.action_key,
        route=action.route,
        deepLink=action.deep_link,
        message="Быстрое действие готово к передаче в модуль-владелец.",
        state=ACTIVE_STATUS,
    )


async def runUserQuickAction(
    db: AsyncSession,
    quickActionId: str | UUID,
    context: Any | None = None,
) -> QuickActionRunResult:
    validation = await validateQuickActionBeforeRun(db, quickActionId, context)
    if validation.status != "READY":
        return validation
    return QuickActionRunResult(
        status="OPEN_MODULE_HANDLER",
        quickActionId=validation.quickActionId,
        sourceModuleCode=validation.sourceModuleCode,
        actionKey=validation.actionKey,
        route=validation.route,
        deepLink=validation.deepLink,
        message="Передано в модуль-владелец. Dashboard/Module 03 не выполняет бизнес-операцию.",
        state=ACTIVE_STATUS,
        requiresModuleHandler=True,
    )


async def _get_action(db: AsyncSession, quick_action_id: str | UUID) -> UserModuleQuickAction:
    action = await db.get(UserModuleQuickAction, _uuid(quick_action_id, "quickActionId"))
    if not action:
        raise NotFoundError("Quick action not found.")
    return action


async def _active_count(db: AsyncSession, user_id: str | UUID, source_module_code: str) -> int:
    result = await db.execute(
        select(func.count(UserModuleQuickAction.id)).where(
            UserModuleQuickAction.user_id == _uuid(user_id, "userId"),
            UserModuleQuickAction.source_module_code == source_module_code,
            UserModuleQuickAction.status == ACTIVE_STATUS,
        )
    )
    return int(result.scalar() or 0)


async def _pinned_count(
    db: AsyncSession,
    user_id: str | UUID,
    source_module_code: str,
    *,
    exclude_id: str | UUID | None = None,
) -> int:
    statement = select(func.count(UserModuleQuickAction.id)).where(
        UserModuleQuickAction.user_id == _uuid(user_id, "userId"),
        UserModuleQuickAction.source_module_code == source_module_code,
        UserModuleQuickAction.is_pinned_to_atom_card.is_(True),
    )
    if exclude_id:
        statement = statement.where(UserModuleQuickAction.id != _uuid(exclude_id, "quickActionId"))
    result = await db.execute(statement)
    return int(result.scalar() or 0)


async def _next_order(db: AsyncSession, user_id: str | UUID, source_module_code: str) -> int:
    result = await db.execute(
        select(func.max(UserModuleQuickAction.order)).where(
            UserModuleQuickAction.user_id == _uuid(user_id, "userId"),
            UserModuleQuickAction.source_module_code == source_module_code,
        )
    )
    return int(result.scalar() or 0) + 1


async def _next_atom_card_order(db: AsyncSession, user_id: str | UUID, source_module_code: str) -> int:
    result = await db.execute(
        select(func.max(UserModuleQuickAction.atom_card_order)).where(
            UserModuleQuickAction.user_id == _uuid(user_id, "userId"),
            UserModuleQuickAction.source_module_code == source_module_code,
            UserModuleQuickAction.is_pinned_to_atom_card.is_(True),
        )
    )
    return int(result.scalar() or 0) + 1


async def _ensure_can_pin(db: AsyncSession, action: UserModuleQuickAction) -> None:
    if action.is_pinned_to_atom_card:
        return
    pinned_count = await _pinned_count(
        db,
        action.user_id,
        action.source_module_code,
        exclude_id=action.id,
    )
    if pinned_count >= MAX_ATOM_CARD_PINNED_ACTIONS:
        raise ValidationError("На карточке модуля можно закрепить не более 3 быстрых действий.")


async def _compact_module_order(db: AsyncSession, user_id: str | UUID, source_module_code: str) -> None:
    result = await db.execute(
        select(UserModuleQuickAction)
        .where(
            UserModuleQuickAction.user_id == _uuid(user_id, "userId"),
            UserModuleQuickAction.source_module_code == source_module_code,
        )
        .order_by(UserModuleQuickAction.order.asc(), UserModuleQuickAction.created_at.asc())
    )
    for index, action in enumerate(result.scalars().all(), start=1):
        action.order = index
        db.add(action)
    await db.flush()


async def _compact_pinned_order(db: AsyncSession, user_id: str | UUID, source_module_code: str) -> None:
    result = await db.execute(
        select(UserModuleQuickAction)
        .where(
            UserModuleQuickAction.user_id == _uuid(user_id, "userId"),
            UserModuleQuickAction.source_module_code == source_module_code,
            UserModuleQuickAction.is_pinned_to_atom_card.is_(True),
        )
        .order_by(UserModuleQuickAction.atom_card_order.asc(), UserModuleQuickAction.order.asc())
    )
    for index, action in enumerate(result.scalars().all(), start=1):
        action.atom_card_order = index
        db.add(action)
    await db.flush()


def _blocked(action: UserModuleQuickAction, *, state: str, message: str) -> QuickActionRunResult:
    return QuickActionRunResult(
        status="BLOCKED",
        quickActionId=str(action.id),
        sourceModuleCode=action.source_module_code,
        actionKey=action.action_key,
        route=action.route,
        deepLink=action.deep_link,
        message=message,
        state=state,
    )


def _loading(action: UserModuleQuickAction) -> QuickActionRunResult:
    return QuickActionRunResult(
        status=LOADING_STATUS,
        quickActionId=str(action.id),
        sourceModuleCode=action.source_module_code,
        actionKey=action.action_key,
        route=action.route,
        deepLink=action.deep_link,
        message=_state_message(LOADING_STATUS),
        state=LOADING_STATUS,
        warnings=["Action state is loading; module owner should revalidate before run."],
    )


def _atom_card_payload(action: UserModuleQuickAction) -> dict[str, Any]:
    return {
        "quickActionId": str(action.id),
        "sourceModuleCode": action.source_module_code,
        "featureCode": action.feature_code,
        "actionKey": action.action_key,
        "title": action.title,
        "icon": action.icon,
        "route": action.route,
        "deepLink": action.deep_link,
        "savedConfigRef": action.saved_config_ref,
        "atomCardOrder": action.atom_card_order,
        "atomCardAccent": action.atom_card_accent or "cyan",
        "status": action.status,
        "isDisabled": action.status != ACTIVE_STATUS,
        "isLoading": action.status == LOADING_STATUS,
        "isError": action.status == ERROR_STATUS,
        "placement": "ATOM_CARD",
        "tooltip": _atom_card_tooltip(action),
    }


def _atom_card_tooltip(action: UserModuleQuickAction) -> str:
    if action.status != ACTIVE_STATUS:
        return _state_message(action.status)
    return action.title


def _state_message(status: str | None) -> str:
    messages = {
        "DISABLED": "Быстрое действие временно отключено.",
        "BROKEN_CONFIG": "Настройки этого быстрого действия устарели. Откройте модуль и настройте действие заново.",
        "MODULE_DISABLED": "Модуль-владелец отключен.",
        "NO_LONGER_AVAILABLE": "Это действие больше недоступно в модуле. Вы можете убрать его из быстрых действий.",
        "LOADING": "Быстрое действие обновляется. Попробуйте еще раз через несколько секунд.",
        "ERROR": "Не удалось подготовить быстрое действие. Откройте модуль и проверьте действие заново.",
    }
    return messages.get(str(status), "Быстрое действие сейчас недоступно.")


def _require_same_user(user_id: str | UUID, context: Any | None) -> None:
    context_user_id = _context_user_id(context)
    if context_user_id and str(_uuid(context_user_id, "context.userId")) != str(_uuid(user_id, "userId")):
        raise ForbiddenError("Quick action belongs to another user.")


def _require_module_boundary(
    source_module_code: str,
    context: Any | None,
    *,
    require_owner_context: bool = False,
) -> None:
    context_data = _dict_value(context)
    context_module = (
        context_data.get("sourceModuleCode")
        or context_data.get("currentModuleCode")
        or context_data.get("ownerModuleCode")
    )
    allowed_modules = set(_list_value(context_data.get("allowedSourceModuleCodes")))
    if require_owner_context and not context_module and not allowed_modules:
        raise ForbiddenError("Module owner context is required to change quick actions.")
    if context_module and str(context_module) != source_module_code:
        raise ForbiddenError("Cannot create or change quick action for another module.")
    if allowed_modules and source_module_code not in allowed_modules:
        raise ForbiddenError("sourceModuleCode is not allowed for this quick action context.")


def _ensure_safe_config(config: Any) -> None:
    if config is None:
        return
    if not isinstance(config, dict):
        raise ValidationError("configSnapshot must be an object.")
    forbidden = _find_forbidden_config_keys(config)
    if forbidden:
        raise ValidationError(f"configSnapshot must not store business/raw payload: {', '.join(sorted(forbidden))}.")


def _find_forbidden_config_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in FORBIDDEN_CONFIG_KEYS:
                found.add(str(key))
            found.update(_find_forbidden_config_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_find_forbidden_config_keys(child))
    return found


def _validate_atom_accent(value: Any) -> None:
    if value is None:
        return
    if str(value) not in set(ATOM_CARD_ACCENTS):
        raise ValidationError("Unsupported atomCardAccent.")


def _context_user_id(context: Any | None) -> str | None:
    data = _dict_value(context)
    value = data.get("userId") or data.get("user_id")
    return str(value) if value else None


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _required(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if value is None or str(value) == "":
        raise ValidationError(f"{key} is required.")
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []


def _uuid(value: str | UUID, field_name: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be UUID.") from exc


def _optional_uuid(value: Any, field_name: str) -> UUID | None:
    if value in (None, ""):
        return None
    return _uuid(value, field_name)
