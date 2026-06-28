from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, DASHBOARD_ADMIN_SOURCE_MODULE
from app.services.quick_action_permission import can_use_quick_action
from app.services.quick_action_registry import get_quick_action_registry

ATOM_CARD_QUICK_ACTION_LIMIT = 3


@dataclass(frozen=True)
class DashboardQuickAction:
    actionCode: str
    label: str
    href: str
    icon: str
    moduleCode: str
    featureCode: str | None = None
    contextCode: str | None = None
    cabinetTypes: tuple[str, ...] = ("ADMIN",)
    requiresConfirmation: bool = False
    mock: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dashboard_quick_action_registry() -> tuple[DashboardQuickAction, ...]:
    return tuple(
        _dashboard_action_from_registry(item)
        for item in get_quick_action_registry()
        if item["status"] == "ACTIVE"
    )


QUICK_ACTION_REGISTRY: tuple[DashboardQuickAction, ...]

DEFAULT_ATOM_CARD_ACTION_CODES: dict[str, tuple[str, ...]] = {
    "MODULE_01_MATERIAL_HUB": (
        "MATERIAL_CREATE",
        "SUPPLIER_PRICE_UPLOAD",
        "MATERIAL_MODERATION_OPEN",
    ),
    DASHBOARD_ADMIN_SOURCE_MODULE: (
        "DASHBOARD_CONFIGURE",
    ),
}


def get_quick_actions_for_dashboard(user_context: Any, cabinet_context: dict[str, Any]) -> list[dict[str, Any]]:
    preset_action_codes = set((cabinet_context.get("cabinetDashboardPreset") or {}).get("quickActionCodes") or [])
    permission_context = {**_context_dict(user_context), **cabinet_context}
    actions: list[dict[str, Any]] = []
    for action in _dashboard_quick_action_registry():
        if action.actionCode not in preset_action_codes:
            continue
        if not can_use_quick_action(user_context, action.actionCode, permission_context):
            continue
        actions.append(action.to_dict())
    return actions


def get_atom_card_quick_action_options(
    user_context: Any,
    cabinet_context: dict[str, Any],
    module_code: str,
    selected_action_codes: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    available_actions = [
        action
        for action in get_quick_actions_for_dashboard(user_context, cabinet_context)
        if action["moduleCode"] == module_code
    ]
    selected_codes = _selected_atom_action_codes(module_code, selected_action_codes, available_actions)
    options: list[dict[str, Any]] = []
    for action in available_actions:
        option = dict(action)
        option["isSelected"] = action["actionCode"] in selected_codes
        option["placement"] = "ATOM_CARD"
        options.append(option)
    selected_order = {code: index for index, code in enumerate(selected_codes)}
    return sorted(
        options,
        key=lambda action: (
            0 if action["isSelected"] else 1,
            selected_order.get(action["actionCode"], len(selected_order)),
            action["label"],
        ),
    )


def get_atom_card_quick_actions(
    user_context: Any,
    cabinet_context: dict[str, Any],
    module_code: str,
    selected_action_codes: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    return [
        action
        for action in get_atom_card_quick_action_options(
            user_context,
            cabinet_context,
            module_code,
            selected_action_codes=selected_action_codes,
        )
        if action["isSelected"]
    ][:ATOM_CARD_QUICK_ACTION_LIMIT]


def _selected_atom_action_codes(
    module_code: str,
    selected_action_codes: list[str] | tuple[str, ...] | None,
    available_actions: list[dict[str, Any]],
) -> list[str]:
    available_codes = {action["actionCode"] for action in available_actions}
    configured_codes = list(selected_action_codes or DEFAULT_ATOM_CARD_ACTION_CODES.get(module_code, ()))
    selected_codes = [code for code in configured_codes if code in available_codes]
    if not selected_codes:
        selected_codes = [action["actionCode"] for action in available_actions]
    return selected_codes[:ATOM_CARD_QUICK_ACTION_LIMIT]


def _dashboard_action_from_registry(item: dict[str, Any]) -> DashboardQuickAction:
    settings = item.get("settings") or {}
    return DashboardQuickAction(
        actionCode=item["quickActionCode"],
        label=item["title"],
        href=item.get("route") or "#",
        icon=settings.get("icon") or "•",
        moduleCode=item["sourceModuleCode"],
        featureCode=item.get("featureCode"),
        contextCode=settings.get("contextCode"),
        cabinetTypes=tuple(item.get("allowedCabinetTypes") or ("ADMIN",)),
        requiresConfirmation=bool(settings.get("requiresConfirmation")),
        mock=bool(settings.get("mock")),
    )


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


QUICK_ACTION_REGISTRY = _dashboard_quick_action_registry()
