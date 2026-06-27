from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.dashboard_module_registry import (
    ACTIVE_STATUS,
    get_canonical_module_code,
    get_dashboard_module_registry_item,
    resolve_module_route,
)
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, DASHBOARD_ADMIN_SOURCE_MODULE
from app.services.dashboard_widget_config import WIDGET_SIZES, WIDGET_TYPES


WIDGET_STATUSES = {
    "available",
    "planned",
    "disabled",
    "requires_module",
    "requires_permission",
    "mock_only",
}


@dataclass(frozen=True)
class DashboardWidgetRegistryItem:
    widgetCode: str
    title: str
    type: str
    sourceModuleCode: str
    defaultSize: str
    isEnabledByDefault: bool
    componentKey: str
    status: str
    description: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    contextCode: str | None = None
    legacyModuleCode: str | None = None
    requiredModuleCode: str | None = None
    requiredPermissions: list[str] = field(default_factory=list)
    allowedSizes: list[str] = field(default_factory=lambda: ["small", "medium", "large"])
    defaultSettings: dict[str, Any] = field(default_factory=dict)
    availableSettings: dict[str, Any] = field(default_factory=dict)
    mockDataProvider: str | None = None
    routeToSourceModule: str | None = None
    requiredModuleStatus: str | None = None
    plannedReason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _widget_item(
    *,
    widget_code: str,
    title: str,
    widget_type: str,
    source_module_code: str,
    component_key: str,
    status: str,
    default_size: str = "medium",
    description: str | None = None,
    feature_code: str | None = None,
    context_code: str | None = None,
    required_module_code: str | None = None,
    required_permissions: list[str] | None = None,
    allowed_sizes: list[str] | None = None,
    default_settings: dict[str, Any] | None = None,
    available_settings: dict[str, Any] | None = None,
    mock_data_provider: str | None = None,
    route_to_source_module: str | None = None,
    required_module_status: str | None = None,
    planned_reason: str | None = None,
) -> DashboardWidgetRegistryItem:
    normalized_type = widget_type if widget_type in WIDGET_TYPES else "STATUS"
    normalized_size = default_size if default_size in WIDGET_SIZES else "medium"
    normalized_status = status if status in WIDGET_STATUSES else "disabled"
    canonical_code = get_canonical_module_code(source_module_code) or source_module_code
    legacy_code = source_module_code if source_module_code != canonical_code else None
    route = route_to_source_module or resolve_module_route(source_module_code)
    return DashboardWidgetRegistryItem(
        widgetCode=widget_code,
        title=title,
        description=description or "",
        type=normalized_type,
        sourceModuleCode=canonical_code,
        canonicalModuleCode=canonical_code,
        featureCode=feature_code,
        contextCode=context_code,
        legacyModuleCode=legacy_code,
        requiredModuleCode=required_module_code or canonical_code,
        requiredPermissions=required_permissions or [],
        defaultSize=normalized_size,
        allowedSizes=allowed_sizes or ["small", "medium", "large"],
        defaultSettings=default_settings or {},
        availableSettings=available_settings or {},
        isEnabledByDefault=normalized_status in {"available", "mock_only"},
        componentKey=component_key,
        mockDataProvider=mock_data_provider,
        routeToSourceModule=route,
        status=normalized_status,
        requiredModuleStatus=required_module_status,
        plannedReason=planned_reason,
    )


DASHBOARD_WIDGET_REGISTRY: tuple[DashboardWidgetRegistryItem, ...] = (
    _widget_item(
        widget_code="materials-kpi",
        title="Материалы",
        description="Количество материалов и новые позиции.",
        widget_type="KPI",
        source_module_code="MODULE_01_MATERIAL_HUB",
        component_key="MaterialsKpiWidget",
        status="available",
        default_size="small",
        mock_data_provider="materialHubSummary",
    ),
    _widget_item(
        widget_code="classification-queue",
        title="Требует классификации",
        description="Очередь материалов, которым нужна ручная проверка.",
        widget_type="TASK_QUEUE",
        source_module_code="MODULE_01_MATERIAL_HUB",
        component_key="ClassificationQueueWidget",
        status="available",
        default_size="medium",
    ),
    _widget_item(
        widget_code="price-dynamics",
        title="Динамика цен",
        description="Изменение цен и индекс стоимости.",
        widget_type="CHART",
        source_module_code="MODULE_11_ANALYTICS",
        feature_code="PRICE_DYNAMICS",
        component_key="PriceDynamicsWidget",
        status="mock_only",
        default_size="large",
        default_settings={"period": "month"},
        available_settings={"period": ["week", "month", "quarter", "year"]},
        mock_data_provider="priceDynamicsSummary",
    ),
    _widget_item(
        widget_code="source-health",
        title="Источники данных",
        description="Состояние активных источников сбора.",
        widget_type="STATUS",
        source_module_code="MODULE_01_MATERIAL_HUB",
        component_key="SourceHealthWidget",
        status="available",
        default_size="medium",
    ),
    _widget_item(
        widget_code="system-alerts",
        title="Уведомления",
        description="Ошибки, предупреждения и события платформы.",
        widget_type="ALERTS",
        source_module_code=DASHBOARD_ADMIN_SOURCE_MODULE,
        context_code=DASHBOARD_ADMIN_CONTEXT,
        component_key="SystemAlertsWidget",
        status="mock_only",
        default_size="medium",
        mock_data_provider="systemEvents",
    ),
    _widget_item(
        widget_code="quick-actions",
        title="Действия карточек АТОМа",
        description="Legacy-запись: быстрые действия теперь выбираются на карточках модулей.",
        widget_type="ACTIONS",
        source_module_code=DASHBOARD_ADMIN_SOURCE_MODULE,
        context_code=DASHBOARD_ADMIN_CONTEXT,
        component_key="AtomCardActionsConfig",
        status="disabled",
        default_size="medium",
    ),
    _widget_item(
        widget_code="atom-map",
        title="Атомная карта",
        description="Избранные модули вокруг центра управления.",
        widget_type="ATOM_MAP",
        source_module_code=DASHBOARD_ADMIN_SOURCE_MODULE,
        context_code=DASHBOARD_ADMIN_CONTEXT,
        component_key="AtomMapWidget",
        status="available",
        default_size="large",
        default_settings={"maxVisibleModules": 8},
    ),
    _widget_item(
        widget_code="digital-house-status",
        title="Образ дома",
        description="Состояние цифрового объекта строительства.",
        widget_type="STATUS",
        source_module_code="MODULE_07_DIGITAL_HOUSE",
        feature_code="HOUSE_PROFILE",
        component_key="DigitalHouseStatusWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет Module 07 после реализации цифрового объекта.",
    ),
    _widget_item(
        widget_code="estimate-summary",
        title="Сводка сметы",
        description="Итоговая стоимость, изменения и отклонения.",
        widget_type="KPI",
        source_module_code="MODULE_05_ESTIMATE_ENGINE",
        component_key="EstimateSummaryWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет сметного модуля.",
    ),
    _widget_item(
        widget_code="estimate-audit-risk",
        title="Риски сметы",
        description="Проверка ошибок, дублей и подозрительных строк.",
        widget_type="ALERTS",
        source_module_code="MODULE_06_ESTIMATE_AUDIT",
        component_key="EstimateAuditRiskWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет аудита смет.",
    ),
    _widget_item(
        widget_code="procurement-requests",
        title="Закупки",
        description="Заявки, поставки и комплектация.",
        widget_type="LIST",
        source_module_code="MODULE_09_PROCUREMENT",
        component_key="ProcurementRequestsWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет закупок.",
    ),
    _widget_item(
        widget_code="marketplace-cart",
        title="Маркетплейс",
        description="Корзина, подборки и предложения.",
        widget_type="LIST",
        source_module_code="MODULE_10_MARKETPLACE",
        component_key="MarketplaceCartWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет marketplace.",
    ),
    _widget_item(
        widget_code="partner-tender-invites",
        title="Приглашения партнеров",
        description="Тендеры и входящие приглашения.",
        widget_type="TASK_QUEUE",
        source_module_code="MODULE_08_PARTNER_PORTAL",
        component_key="PartnerTenderInvitesWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет кабинетов партнеров.",
    ),
    _widget_item(
        widget_code="project-collaboration-activity",
        title="Комната проекта",
        description="Активность участников и проектные события.",
        widget_type="LIST",
        source_module_code="MODULE_13_PROJECT_COLLABORATION",
        component_key="ProjectCollaborationActivityWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет проектного взаимодействия.",
    ),
    _widget_item(
        widget_code="constructor-changes",
        title="Конструктор Lite",
        description="Последние изменения модели и комплектаций.",
        widget_type="LIST",
        source_module_code="MODULE_19_CONSTRUCTOR_LITE",
        component_key="ConstructorChangesWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет конструктора.",
    ),
    _widget_item(
        widget_code="contracts-pending",
        title="Договоры",
        description="Договоры на согласовании и подписании.",
        widget_type="TASK_QUEUE",
        source_module_code="MODULE_15_CONTRACTS",
        component_key="ContractsPendingWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет договоров.",
    ),
    _widget_item(
        widget_code="ai-recommendations",
        title="AI-рекомендации",
        description="Рекомендации и подсказки AI-помощника.",
        widget_type="LIST",
        source_module_code="MODULE_12_AI_ASSISTANT",
        component_key="AIRecommendationsWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет AI-помощника.",
    ),
    _widget_item(
        widget_code="logistics-delivery",
        title="Логистика",
        description="Доставки, зоны и статусы отгрузок.",
        widget_type="STATUS",
        source_module_code="MODULE_16_LOGISTICS_DELIVERY",
        component_key="LogisticsDeliveryWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет логистики.",
    ),
    _widget_item(
        widget_code="finance-budget",
        title="Финансы",
        description="Бюджет, платежи и кассовый план.",
        widget_type="KPI",
        source_module_code="MODULE_17_FINANCE_PAYMENTS",
        component_key="FinanceBudgetWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет финансов.",
    ),
    _widget_item(
        widget_code="quality-control-issues",
        title="Контроль качества",
        description="Замечания, проверки и статусы качества.",
        widget_type="ALERTS",
        source_module_code="MODULE_18_QUALITY_CONTROL",
        component_key="QualityControlIssuesWidget",
        status="planned",
        default_size="medium",
        required_module_status="ACTIVE",
        planned_reason="Будущий виджет контроля качества.",
    ),
)


def get_dashboard_widget_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in DASHBOARD_WIDGET_REGISTRY]


def get_dashboard_widget_registry_item(widget_code: str) -> DashboardWidgetRegistryItem | None:
    return next((item for item in DASHBOARD_WIDGET_REGISTRY if item.widgetCode == widget_code), None)


def get_available_dashboard_widgets(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    allowed_modules = {
        get_canonical_module_code(code) or code
        for code in data.get("allowedModuleCodes") or []
    }
    allowed_widgets = set(data.get("allowedWidgetCodes") or [])
    return [
        item.to_dict()
        for item in DASHBOARD_WIDGET_REGISTRY
        if _is_widget_available_for_profile(item, allowed_modules, allowed_widgets)
    ]


def get_planned_dashboard_widgets(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    if data.get("roleCode") not in {"ADMIN", "SUPER_ADMIN", "DEV_ADMIN"} or data.get("authMode") not in {"mock", "dev"}:
        return []
    return [
        item.to_dict()
        for item in DASHBOARD_WIDGET_REGISTRY
        if item.status in {"planned", "requires_module", "disabled"}
    ]


def _is_widget_available_for_profile(
    item: DashboardWidgetRegistryItem,
    allowed_modules: set[str],
    allowed_widgets: set[str],
) -> bool:
    if item.status not in {"available", "mock_only"}:
        return False
    if item.requiredModuleCode and item.requiredModuleCode not in allowed_modules:
        return False
    if allowed_widgets and item.widgetCode not in allowed_widgets:
        return False
    module_item = get_dashboard_module_registry_item(item.requiredModuleCode or item.sourceModuleCode)
    return module_item is None or module_item.status == ACTIVE_STATUS


def _profile_dict(user_profile: Any) -> dict[str, Any]:
    if user_profile is None:
        return {}
    if hasattr(user_profile, "to_template_dict"):
        return user_profile.to_template_dict()
    if hasattr(user_profile, "__dict__") and not isinstance(user_profile, dict):
        return dict(user_profile.__dict__)
    if isinstance(user_profile, dict):
        return user_profile
    return {}
