from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.services.dashboard_auth_adapters import can_use_action


@dataclass(frozen=True)
class DashboardQuickAction:
    actionCode: str
    label: str
    href: str
    icon: str
    moduleCode: str
    featureCode: str | None = None
    cabinetTypes: tuple[str, ...] = ("ADMIN",)
    requiresConfirmation: bool = False
    mock: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


QUICK_ACTION_REGISTRY: tuple[DashboardQuickAction, ...] = (
    DashboardQuickAction(
        actionCode="SUPPLIER_PRICE_UPLOAD",
        label="Загрузить прайс",
        href="/api/v1/admin/material-hub/view",
        icon="⇧",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="UPLOAD_SUPPLIER_FILE",
        cabinetTypes=("ADMIN", "SUPPLIER"),
    ),
    DashboardQuickAction(
        actionCode="SOURCE_TASK_CREATE",
        label="Запустить анализ источника",
        href="/api/v1/admin/material-hub/view",
        icon="▶",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="SOURCE_TASK_CREATE",
        cabinetTypes=("ADMIN",),
    ),
    DashboardQuickAction(
        actionCode="MATERIAL_MODERATION_OPEN",
        label="Открыть модерацию",
        href="/api/v1/admin/material-hub/view/moderation",
        icon="!",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="MODERATION",
        cabinetTypes=("ADMIN",),
    ),
    DashboardQuickAction(
        actionCode="SOURCE_ERRORS_OPEN",
        label="Проверить ошибки сбора",
        href="/api/v1/admin/material-hub/view/tasks",
        icon="×",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="SOURCE_TASK_ERRORS",
        cabinetTypes=("ADMIN",),
    ),
    DashboardQuickAction(
        actionCode="SOURCE_CREATE",
        label="Добавить источник",
        href="/api/v1/admin/material-hub/view/sources",
        icon="+",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="SOURCE_CREATE",
        cabinetTypes=("ADMIN",),
        mock=True,
    ),
    DashboardQuickAction(
        actionCode="MATERIAL_CREATE",
        label="Добавить материал",
        href="/api/v1/admin/material-hub/view/materials",
        icon="+",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="MATERIAL_CREATE",
        cabinetTypes=("ADMIN",),
    ),
    DashboardQuickAction(
        actionCode="DOCUMENT_LIST_OPEN",
        label="Открыть документы",
        href="/api/v1/admin/material-hub/view/documents",
        icon="□",
        moduleCode="MODULE_01_MATERIAL_HUB",
        featureCode="DOCUMENTS",
        cabinetTypes=("ADMIN",),
    ),
    DashboardQuickAction(
        actionCode="DASHBOARD_CONFIGURE",
        label="Настроить Dashboard",
        href="#dashboard-config",
        icon="⚙",
        moduleCode="MODULE_16_ADMIN_CABINET",
        featureCode="DASHBOARD_PERSONALIZE",
        cabinetTypes=("ADMIN", "CUSTOMER", "SUPPLIER", "ESTIMATOR"),
    ),
)


def get_quick_actions_for_dashboard(user_context: Any, cabinet_context: dict[str, Any]) -> list[dict[str, Any]]:
    cabinet_type = cabinet_context.get("activeCabinetType")
    preset_action_codes = set((cabinet_context.get("cabinetDashboardPreset") or {}).get("quickActionCodes") or [])
    actions: list[dict[str, Any]] = []
    for action in QUICK_ACTION_REGISTRY:
        if action.actionCode not in preset_action_codes:
            continue
        if cabinet_type not in action.cabinetTypes:
            continue
        if not can_use_action(user_context, action.actionCode):
            continue
        actions.append(action.to_dict())
    return actions
