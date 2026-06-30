from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


PENDING_ACCESS_DISTRIBUTION = "PENDING_DISTRIBUTION"
DISTRIBUTED_ACCESS = "DISTRIBUTED"
NOT_ACTIVE_ACCESS = "NOT_ACTIVE"

MODULE_ITEM_KIND = "module"
WIDGET_ITEM_KIND = "widget"


@dataclass(frozen=True)
class AccessDistributionItem:
    itemKind: str
    type: str
    title: str
    code: str
    status: str
    statusLabel: str
    registeredAt: str
    reason: str
    actionLabel: str = "Распределить доступ"
    actionTarget: str = "#users"
    highlight: str = "new"
    moduleCode: str | None = None
    canonicalModuleCode: str | None = None
    widgetCode: str | None = None
    sourceModuleCode: str | None = None
    featureCode: str | None = None
    description: str | None = None
    route: str | None = None
    icon: str | None = None
    isSystemCritical: bool = False
    isBillingEligible: bool = False
    isDashboardEligible: bool = True
    allowedDashboardZones: list[str] = field(default_factory=list)
    moduleOwnedWidgets: list[str] = field(default_factory=list)
    accessDistributionStatus: str = PENDING_ACCESS_DISTRIBUTION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def register_module_for_access_system(
    *,
    moduleCode: str,
    title: str,
    description: str | None = None,
    status: str = "DRAFT",
    route: str | None = None,
    icon: str | None = None,
    canonicalModuleCode: str | None = None,
    isSystemCritical: bool = False,
    isBillingEligible: bool = False,
    moduleOwnedWidgets: list[str] | tuple[str, ...] | None = None,
    registeredAt: str | None = None,
    isAccessDistributed: bool = False,
) -> dict[str, Any]:
    active = _is_active_module_status(status)
    return {
        "moduleCode": moduleCode,
        "canonicalModuleCode": canonicalModuleCode or moduleCode,
        "title": title,
        "description": description,
        "status": _module_status(status),
        "route": route,
        "icon": icon,
        "isSystemCritical": bool(isSystemCritical),
        "isBillingEligible": bool(isBillingEligible),
        "moduleOwnedWidgets": list(moduleOwnedWidgets or []),
        "dashboardWidgets": list(moduleOwnedWidgets or []),
        "createdAt": registeredAt,
        "registeredAt": registeredAt,
        "isAccessDistributed": bool(isAccessDistributed),
        "requiresAccessDistribution": active and not isAccessDistributed,
        "accessDistributionStatus": _distribution_status(active=active, is_access_distributed=isAccessDistributed),
    }


def register_widget_for_access_system(
    *,
    widgetCode: str,
    sourceModuleCode: str,
    title: str,
    description: str | None = None,
    status: str = "DRAFT",
    canonicalModuleCode: str | None = None,
    featureCode: str | None = None,
    isDashboardEligible: bool = True,
    allowedDashboardZones: list[str] | tuple[str, ...] | None = None,
    isBillingEligible: bool = False,
    registeredAt: str | None = None,
    isAccessDistributed: bool = False,
) -> dict[str, Any]:
    active = _is_active_widget_status(status)
    return {
        "widgetCode": widgetCode,
        "sourceModuleCode": sourceModuleCode,
        "canonicalModuleCode": canonicalModuleCode or sourceModuleCode,
        "featureCode": featureCode,
        "title": title,
        "description": description,
        "status": _widget_status(status),
        "isDashboardEligible": bool(isDashboardEligible),
        "allowedDashboardZones": list(allowedDashboardZones or []),
        "isBillingEligible": bool(isBillingEligible),
        "createdAt": registeredAt,
        "registeredAt": registeredAt,
        "isAccessDistributed": bool(isAccessDistributed),
        "requiresAccessDistribution": active and bool(isDashboardEligible) and not isAccessDistributed,
        "accessDistributionStatus": _distribution_status(active=active, is_access_distributed=isAccessDistributed),
    }


def build_pending_access_distribution_items(
    modules: list[Any] | tuple[Any, ...],
    widgets: list[Any] | tuple[Any, ...],
    *,
    distributedModuleCodes: set[str] | None = None,
    distributedWidgetCodes: set[str] | None = None,
) -> list[dict[str, Any]]:
    distributed_modules = distributedModuleCodes or set()
    distributed_widgets = distributedWidgetCodes or set()
    items: list[AccessDistributionItem] = []

    for module in modules:
        if not _module_requires_distribution(module, distributed_modules):
            continue
        module_code = str(_value(module, "moduleCode", "module_code") or "")
        canonical = str(_value(module, "canonicalModuleCode", "canonical_module_code") or module_code)
        items.append(
            AccessDistributionItem(
                itemKind=MODULE_ITEM_KIND,
                type="модуль",
                title=str(_value(module, "title") or module_code),
                code=module_code,
                moduleCode=module_code,
                canonicalModuleCode=canonical,
                description=_optional_text(_value(module, "description")),
                status=str(_value(module, "status") or "ACTIVE"),
                statusLabel="новое",
                registeredAt=_registered_at(module),
                route=_optional_text(_value(module, "route")),
                icon=_optional_text(_value(module, "icon")),
                isSystemCritical=bool(_value(module, "isSystemCritical", "is_system_critical")),
                isBillingEligible=bool(_value(module, "isBillingEligible", "is_billing_eligible")),
                moduleOwnedWidgets=_list_value(
                    _value(module, "moduleOwnedWidgets", "module_owned_widgets", "dashboardWidgets", "widgetCodes")
                ),
                reason="Новый ACTIVE модуль зарегистрирован и требует распределения доступа.",
                actionTarget="#access-matrix",
            )
        )

    for widget in widgets:
        if not _widget_requires_distribution(widget, distributed_widgets):
            continue
        widget_code = str(_value(widget, "widgetCode", "widget_code") or "")
        source_module_code = str(_value(widget, "sourceModuleCode", "source_module_code") or "")
        canonical = str(_value(widget, "canonicalModuleCode", "canonical_module_code") or source_module_code)
        items.append(
            AccessDistributionItem(
                itemKind=WIDGET_ITEM_KIND,
                type="виджет",
                title=str(_value(widget, "title") or widget_code),
                code=widget_code,
                widgetCode=widget_code,
                sourceModuleCode=source_module_code,
                canonicalModuleCode=canonical,
                featureCode=_optional_text(_value(widget, "featureCode", "feature_code")),
                description=_optional_text(_value(widget, "description")),
                status=str(_value(widget, "status") or "ACTIVE"),
                statusLabel="новое",
                registeredAt=_registered_at(widget),
                isBillingEligible=bool(_value(widget, "isBillingEligible", "is_billing_eligible")),
                isDashboardEligible=bool(_value(widget, "isDashboardEligible", "is_dashboard_eligible", default=True)),
                allowedDashboardZones=_list_value(_value(widget, "allowedDashboardZones", "allowed_dashboard_zones")),
                reason="Новый ACTIVE виджет зарегистрирован и требует распределения доступа.",
                actionTarget="#access-matrix",
            )
        )

    return [
        item.to_dict()
        for item in sorted(items, key=lambda value: (value.itemKind != MODULE_ITEM_KIND, value.title, value.code))
    ]


def _module_requires_distribution(module: Any, distributed_codes: set[str]) -> bool:
    module_code = str(_value(module, "moduleCode", "module_code") or "")
    if module_code in distributed_codes:
        return False
    if not _is_active_module_status(_value(module, "status")):
        return False
    if _value(module, "requiresAccessDistribution", "requires_access_distribution") is not None:
        return bool(_value(module, "requiresAccessDistribution", "requires_access_distribution"))
    status = str(_value(module, "accessDistributionStatus", "access_distribution_status") or "").upper()
    if status:
        return status == PENDING_ACCESS_DISTRIBUTION
    if _value(module, "isAccessDistributed", "is_access_distributed") is not None:
        return not bool(_value(module, "isAccessDistributed", "is_access_distributed"))
    return False


def _widget_requires_distribution(widget: Any, distributed_codes: set[str]) -> bool:
    widget_code = str(_value(widget, "widgetCode", "widget_code") or "")
    if widget_code in distributed_codes:
        return False
    if not _is_active_widget_status(_value(widget, "status")):
        return False
    if not bool(_value(widget, "isDashboardEligible", "is_dashboard_eligible", default=True)):
        return False
    if _value(widget, "requiresAccessDistribution", "requires_access_distribution") is not None:
        return bool(_value(widget, "requiresAccessDistribution", "requires_access_distribution"))
    status = str(_value(widget, "accessDistributionStatus", "access_distribution_status") or "").upper()
    if status:
        return status == PENDING_ACCESS_DISTRIBUTION
    if _value(widget, "isAccessDistributed", "is_access_distributed") is not None:
        return not bool(_value(widget, "isAccessDistributed", "is_access_distributed"))
    return False


def _distribution_status(*, active: bool, is_access_distributed: bool) -> str:
    if not active:
        return NOT_ACTIVE_ACCESS
    return DISTRIBUTED_ACCESS if is_access_distributed else PENDING_ACCESS_DISTRIBUTION


def _is_active_module_status(status: Any) -> bool:
    return str(status or "").lower() == "active"


def _is_active_widget_status(status: Any) -> bool:
    return str(status or "").upper() == "ACTIVE"


def _module_status(status: Any) -> str:
    return str(status or "DRAFT").lower()


def _widget_status(status: Any) -> str:
    return str(status or "DRAFT").upper()


def _registered_at(item: Any) -> str:
    return str(_value(item, "registeredAt", "registered_at", "createdAt", "created_at") or "не задано")


def _optional_text(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _list_value(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)]


def _value(source: Any, *field_names: str, default: Any = None) -> Any:
    if source is None:
        return default
    for field_name in field_names:
        if isinstance(source, dict) and field_name in source:
            return source.get(field_name)
        if hasattr(source, field_name):
            return getattr(source, field_name)
    return default
