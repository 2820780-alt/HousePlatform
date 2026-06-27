from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CabinetDashboardPreset:
    presetCode: str
    title: str
    topbar: dict[str, Any] = field(default_factory=dict)
    widgetZones: dict[str, Any] = field(default_factory=dict)
    quickActionCodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CurrentCabinetContext:
    activeCabinetId: str
    activeCabinetType: str
    activeCabinetTitle: str
    currentBlock: str
    businessRole: str | None = None
    activeObjectLabel: str | None = None
    availableCabinets: list[dict[str, str]] = field(default_factory=list)
    cabinetDashboardPreset: dict[str, Any] = field(default_factory=dict)
    allowedActionCodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DashboardCabinetContextAdapter:
    @staticmethod
    def get_current_cabinet_context(user_context: Any) -> CurrentCabinetContext:
        data = _context_dict(user_context)
        cabinet_type = data.get("activeCabinetType") or "ADMIN"
        cabinet_id = data.get("activeCabinetId") or "cabinet-admin-mock"
        role_code = data.get("roleCode") or "ADMIN"
        allowed_actions = data.get("allowedActionCodes") or []
        preset = _admin_cabinet_preset()
        return CurrentCabinetContext(
            activeCabinetId=cabinet_id,
            activeCabinetType=cabinet_type,
            activeCabinetTitle="Кабинет: Администратор",
            currentBlock="Главная",
            businessRole=role_code,
            activeObjectLabel=None,
            availableCabinets=[
                {
                    "id": cabinet_id,
                    "type": cabinet_type,
                    "title": "Администратор",
                }
            ],
            cabinetDashboardPreset=preset.to_dict(),
            allowedActionCodes=allowed_actions,
        )


def get_current_cabinet_context(user_context: Any) -> CurrentCabinetContext:
    return DashboardCabinetContextAdapter.get_current_cabinet_context(user_context)


def _admin_cabinet_preset() -> CabinetDashboardPreset:
    return CabinetDashboardPreset(
        presetCode="ADMIN_CABINET_DEFAULT",
        title="Административный Dashboard",
        topbar={
            "showCabinet": True,
            "showRegion": True,
            "showCurrentBlock": True,
            "showSearchCommand": True,
            "showGlobalPeriod": False,
            "showProjectSelector": False,
        },
        widgetZones={
            "atomMap": "ATOM_MAP",
            "analytics": "RIGHT_RAIL",
            "adminWidgets": "BOTTOM_WIDGET_GRID",
            "rightRailEnabled": False,
            "rightRailRoleCodes": ["ANALYST"],
            "bottomWidgetGrid": {
                "zoneCode": "BOTTOM_WIDGET_GRID",
                "title": "Нижние виджеты",
                "maxVisibleWidgets": 8,
            },
        },
        quickActionCodes=[
            "MATERIAL_CREATE",
            "SUPPLIER_PRICE_UPLOAD",
            "SOURCE_TASK_CREATE",
            "MATERIAL_MODERATION_OPEN",
            "SOURCE_ERRORS_OPEN",
            "SOURCE_CREATE",
            "MATERIAL_CREATE",
            "DOCUMENT_LIST_OPEN",
            "DASHBOARD_CONFIGURE",
        ],
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
