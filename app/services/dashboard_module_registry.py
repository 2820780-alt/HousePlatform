from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_SOURCE_MODULE
from app.services.platform_region_registry import is_known_platform_region_code


MERGED_STATUS = "merged"
ACTIVE_STATUS = "active"
PLANNED_STATUSES = {"planned", "draft"}
HIDDEN_ACTIVE_STATUSES = {"disabled", "deprecated", "archived", "merged"}


@dataclass(frozen=True)
class DashboardModuleRegistryItem:
    id: str
    moduleCode: str
    title: str
    displayOrder: int
    status: str
    isSystem: bool
    isVisibleInSidebar: bool
    isVisibleOnAtomMap: bool
    isAvailableForDashboard: bool
    canonicalModuleCode: str | None = None
    shortTitle: str | None = None
    description: str | None = None
    legacyNumber: int | None = None
    displayNumber: int | None = None
    visualNumber: int | None = None
    mergedIntoModuleCode: str | None = None
    legacyCodes: list[str] = field(default_factory=list)
    featureCodes: list[str] = field(default_factory=list)
    expectedFeatureCodes: list[str] = field(default_factory=list)
    plannedReason: str | None = None
    icon: str | None = None
    color: str | None = None
    route: str | None = None
    redirectRoute: str | None = None
    requiredPermissions: list[str] = field(default_factory=list)
    widgetCodes: list[str] = field(default_factory=list)
    createdAt: str | None = None
    updatedAt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _registry_item(
    module_code: str,
    title: str,
    *,
    number: int | None,
    order: int,
    route: str | None,
    status: str = ACTIVE_STATUS,
    canonical_module_code: str | None = None,
    short_title: str | None = None,
    description: str | None = None,
    icon: str | None = None,
    color: str | None = None,
    visible_sidebar: bool = True,
    visible_atom: bool = True,
    available_dashboard: bool = True,
    merged_into: str | None = None,
    legacy_codes: list[str] | None = None,
    feature_codes: list[str] | None = None,
    expected_feature_codes: list[str] | None = None,
    planned_reason: str | None = None,
    redirect_route: str | None = None,
    widget_codes: list[str] | None = None,
) -> DashboardModuleRegistryItem:
    return DashboardModuleRegistryItem(
        id=module_code.lower().replace("_", "-"),
        moduleCode=module_code,
        canonicalModuleCode=canonical_module_code,
        title=title,
        shortTitle=short_title,
        description=description,
        legacyNumber=number,
        displayNumber=number,
        visualNumber=number,
        displayOrder=order,
        status=status,
        mergedIntoModuleCode=merged_into,
        legacyCodes=legacy_codes or [],
        featureCodes=feature_codes or [],
        expectedFeatureCodes=expected_feature_codes or [],
        plannedReason=planned_reason,
        icon=icon,
        color=color,
        route=route,
        redirectRoute=redirect_route,
        isSystem=True,
        isVisibleInSidebar=visible_sidebar,
        isVisibleOnAtomMap=visible_atom,
        isAvailableForDashboard=available_dashboard,
        widgetCodes=widget_codes or [],
    )


def _planned_registry_item(
    module_code: str,
    title: str,
    *,
    order: int,
    short_title: str,
    description: str,
    expected_feature_codes: list[str],
    planned_reason: str,
    icon: str,
    color: str,
    status: str = "planned",
    canonical_module_code: str | None = None,
    legacy_codes: list[str] | None = None,
) -> DashboardModuleRegistryItem:
    return _registry_item(
        module_code,
        title,
        number=None,
        order=order,
        route=None,
        status=status,
        canonical_module_code=canonical_module_code,
        short_title=short_title,
        description=description,
        icon=icon,
        color=color,
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        legacy_codes=legacy_codes,
        expected_feature_codes=expected_feature_codes,
        planned_reason=planned_reason,
    )


DASHBOARD_MODULE_REGISTRY: tuple[DashboardModuleRegistryItem, ...] = (
    _registry_item(
        "MODULE_01_MATERIAL_HUB",
        "База материалов",
        number=1,
        order=10,
        route="/api/v1/admin/cabinet/view/modules/1",
        short_title="Материалы",
        description="Сбор, нормализация и хранение данных о материалах.",
        icon="database",
        color="#18d7f2",
        feature_codes=["CONSTRUCTION_APPLICABILITY"],
        widget_codes=["materials-kpi", "classification-queue"],
    ),
    _registry_item(
        "MODULE_02_KNOWLEDGE_BASE",
        "База знаний",
        number=2,
        order=20,
        route="/api/v1/admin/cabinet/view/modules/2",
        short_title="Знания",
        description="Технологии, нормы, документы и правила применения.",
        icon="file-text",
        color="#22c55e",
        feature_codes=["TECHNOLOGY_CONSTRUCTION_GROUPS"],
    ),
    _registry_item(
        "MODULE_03_USERS_ROLES",
        "Пользователи и доступ",
        number=3,
        order=30,
        route="/api/v1/admin/users-roles/view",
        short_title="Доступ",
        description="Пользователи, роли, workspace и права.",
        icon="users",
        color="#38bdf8",
    ),
    _registry_item(
        "MODULE_04_WORKS_COSTS",
        "Работы и стоимости",
        number=4,
        order=40,
        route="/api/v1/admin/cabinet/view/modules/4",
        short_title="Работы",
        description="Работы, трудозатраты и стоимость выполнения.",
        icon="hammer",
        color="#f59e0b",
    ),
    _registry_item(
        "MODULE_05_ESTIMATES",
        "Сметы",
        number=5,
        order=50,
        route="/api/v1/admin/cabinet/view/modules/5",
        short_title="Сметы",
        description="Расчет стоимости и состава будущих смет.",
        icon="calculator",
        color="#0ea5e9",
    ),
    _registry_item(
        "MODULE_06_ESTIMATE_AUDIT",
        "Проверка смет",
        number=6,
        order=60,
        route="/api/v1/admin/cabinet/view/modules/6",
        short_title="Аудит смет",
        description="Контроль ошибок, отклонений и спорных строк.",
        icon="check-square",
        color="#14b8a6",
    ),
    _registry_item(
        "MODULE_07_DIGITAL_OBJECT",
        "Цифровой объект",
        number=7,
        order=70,
        route="/api/v1/admin/cabinet/view/modules/7",
        status=MERGED_STATUS,
        canonical_module_code="MODULE_07_DIGITAL_HOUSE",
        short_title="Объект",
        description="Legacy-код цифрового объекта. Канонический модуль: Образ объекта.",
        icon="home",
        color="#60a5fa",
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        merged_into="MODULE_07_DIGITAL_HOUSE",
        redirect_route="/modules/digital-house",
    ),
    _registry_item(
        "MODULE_08_PROCUREMENT",
        "Закупки",
        number=8,
        order=80,
        route="/api/v1/admin/cabinet/view/modules/8",
        short_title="Закупки",
        description="Поставки, комплектация и потребности проекта.",
        icon="package",
        color="#a855f7",
    ),
    _registry_item(
        "MODULE_09_TENDERS",
        "Тендеры",
        number=9,
        order=90,
        route="/api/v1/admin/cabinet/view/modules/9",
        short_title="Тендеры",
        description="Сбор предложений рынка и сравнение условий.",
        icon="trophy",
        color="#ec4899",
    ),
    _registry_item(
        "MODULE_10_MARKETPLACE",
        "Маркетплейс",
        number=10,
        order=100,
        route="/api/v1/admin/cabinet/view/modules/10",
        short_title="Маркет",
        description="Витрина материалов, предложений и поставщиков.",
        icon="store",
        color="#f97316",
    ),
    _registry_item(
        "MODULE_11_ANALYTICS",
        "Аналитика",
        number=11,
        order=110,
        route="/api/v1/admin/cabinet/view/modules/11",
        short_title="Аналитика",
        description="Сводные показатели, графики и динамика цен.",
        icon="chart-no-axes-combined",
        color="#06b6d4",
        feature_codes=["PRICE_DYNAMICS"],
        widget_codes=["price-dynamics", "market-index"],
    ),
    _registry_item(
        "MODULE_12_AI_ASSISTANT",
        "AI-помощник",
        number=12,
        order=120,
        route="/api/v1/admin/cabinet/view/modules/12",
        short_title="AI",
        description="Помощь в поиске, анализе и рекомендациях.",
        icon="sparkles",
        color="#8b5cf6",
    ),
    _registry_item(
        "MODULE_13_AUDIT",
        "Журнал событий",
        number=13,
        order=130,
        route="/api/v1/admin/cabinet/view/modules/13",
        short_title="Аудит",
        description="История действий, изменений и системных событий.",
        icon="clock",
        color="#64748b",
    ),
    _registry_item(
        "MODULE_14_PRICE_HISTORY",
        "История цен",
        number=14,
        order=140,
        route="/modules/price-history",
        status=MERGED_STATUS,
        canonical_module_code="MODULE_11_ANALYTICS",
        short_title="Цены",
        description="Legacy-раздел динамики цен внутри аналитики.",
        icon="chart-no-axes-combined",
        color="#8b5cf6",
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        merged_into="MODULE_11_ANALYTICS",
        legacy_codes=["MODULE_14_PRICE_DYNAMICS"],
        feature_codes=["PRICE_DYNAMICS"],
        redirect_route="/modules/analytics?section=price-dynamics",
    ),
    _registry_item(
        "MODULE_15_CONSTRUCTION_GROUPS",
        "Группы строительства",
        number=15,
        order=150,
        route="/modules/construction-groups",
        status="deprecated",
        canonical_module_code="MODULE_01_MATERIAL_HUB",
        short_title="Группы",
        description="Deprecated feature alias: construction groups are handled by Material Hub / CONSTRUCTION_APPLICABILITY, with related technology rules in Knowledge Base.",
        icon="network",
        color="#f43f5e",
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        feature_codes=["CONSTRUCTION_APPLICABILITY"],
        redirect_route="/api/v1/admin/material-hub/view?feature=construction-applicability",
    ),
    _registry_item(
        "MODULE_16_ADMIN_CABINET",
        "Кабинет администратора",
        number=16,
        order=160,
        route="/api/v1/admin/cabinet/view",
        status="deprecated",
        canonical_module_code=DASHBOARD_ADMIN_SOURCE_MODULE,
        short_title="Legacy admin",
        description="Deprecated/internal alias: административный экран является системным Dashboard context, не бизнес-модулем.",
        icon="settings",
        color="#18d7f2",
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        redirect_route="/api/v1/admin/cabinet/view",
    ),
    _registry_item(
        "MODULE_18_QUALITY_CONTROL",
        "Контроль качества",
        number=18,
        order=180,
        route=None,
        status="planned",
        short_title="Качество",
        description="Будущий модуль контроля качества работ и материалов.",
        icon="shield-check",
        color="#fb7185",
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        planned_reason="Будущий модуль платформы.",
    ),
    _planned_registry_item(
        "MODULE_05_ESTIMATE_ENGINE",
        "Сметный движок",
        order=500,
        short_title="Сметы",
        description="Будущий движок расчета смет, сценариев и стоимости строительства.",
        expected_feature_codes=["ESTIMATE_ENGINE", "ESTIMATE_SCENARIOS", "ESTIMATE_EXPORT"],
        planned_reason="Будущий модуль расчета и управления сметами.",
        icon="calculator",
        color="#0ea5e9",
        legacy_codes=["MODULE_05_ESTIMATES_ENGINE"],
    ),
    _planned_registry_item(
        "MODULE_07_DIGITAL_HOUSE",
        "Образ дома",
        order=700,
        short_title="Дом",
        description="Цифровой объект строительства: проект, характеристики, сметы, закупки, склад, расходы и история изменений.",
        expected_feature_codes=[
            "HOUSE_PROFILE",
            "HOUSE_ESTIMATES",
            "HOUSE_PURCHASES",
            "HOUSE_STORAGE",
            "HOUSE_EXPENSES",
            "HOUSE_HISTORY",
        ],
        planned_reason="Будущий модуль цифрового объекта строительства.",
        icon="home",
        color="#60a5fa",
        legacy_codes=["MODULE_07_DIGITAL_OBJECT_V2"],
    ),
    _planned_registry_item(
        "MODULE_08_PARTNER_PORTAL",
        "Кабинеты партнеров",
        order=800,
        short_title="Партнеры",
        description="Кабинеты поставщиков, подрядчиков и участников закупок.",
        expected_feature_codes=["PARTNER_PROFILE", "PARTNER_OFFERS", "PARTNER_DOCUMENTS"],
        planned_reason="Будущий модуль партнерских кабинетов.",
        icon="briefcase",
        color="#a855f7",
    ),
    _planned_registry_item(
        "MODULE_09_PROCUREMENT",
        "Закупки и тендеры",
        order=900,
        short_title="Закупки",
        description="Единый контур заявок, закупок, тендеров и выбора поставщиков.",
        expected_feature_codes=["PROCUREMENT_REQUESTS", "TENDER_COMPARE", "SUPPLIER_SELECTION"],
        planned_reason="Будущий объединенный модуль закупок и тендеров.",
        icon="shopping-bag",
        color="#ec4899",
        legacy_codes=["MODULE_08_PROCUREMENT_V2", "MODULE_09_TENDERS_V2"],
    ),
    _planned_registry_item(
        "MODULE_13_PROJECT_COLLABORATION",
        "Комната проекта",
        order=1300,
        short_title="Проект",
        description="Совместная работа участников проекта, задачи, обсуждения и файлы.",
        expected_feature_codes=["PROJECT_ROOM", "PROJECT_TASKS", "PROJECT_MESSAGES", "PROJECT_FILES"],
        planned_reason="Будущий модуль совместной работы по объекту.",
        icon="messages-square",
        color="#38bdf8",
    ),
    _registry_item(
        "MODULE_14_CONSTRUCTOR_LITE",
        "Конструктор Lite",
        number=14,
        order=1400,
        route="/modules/constructor-lite",
        status="deprecated",
        canonical_module_code="MODULE_19_CONSTRUCTOR_LITE",
        short_title="Конструктор",
        description="Deprecated alias будущего конструктора. Канонический модуль: MODULE_19_CONSTRUCTOR_LITE.",
        icon="blocks",
        color="#8b5cf6",
        visible_sidebar=False,
        visible_atom=False,
        available_dashboard=False,
        legacy_codes=["MODULE_14_CONSTRUCTOR"],
        expected_feature_codes=["CONSTRUCTOR_SCENARIOS", "HOUSE_OPTIONS", "SOLUTION_COMPARE"],
        planned_reason="Legacy alias: номер 14 занят историей цен, будущий Constructor Lite использует MODULE_19_CONSTRUCTOR_LITE.",
        redirect_route="/modules/constructor-lite",
    ),
    _planned_registry_item(
        "MODULE_19_CONSTRUCTOR_LITE",
        "Конструктор Lite",
        order=1900,
        short_title="Конструктор",
        description="Легкий подбор типовых решений, состава дома и сценариев строительства.",
        expected_feature_codes=["CONSTRUCTOR_SCENARIOS", "HOUSE_OPTIONS", "SOLUTION_COMPARE"],
        planned_reason="Будущий модуль быстрого подбора решений.",
        icon="blocks",
        color="#8b5cf6",
        legacy_codes=["MODULE_14_CONSTRUCTOR_LITE"],
    ),
    _planned_registry_item(
        "MODULE_15_CONTRACTS",
        "Договоры",
        order=1500,
        short_title="Договоры",
        description="Договоры, приложения, этапы оплаты и история согласований.",
        expected_feature_codes=["CONTRACT_DRAFTS", "CONTRACT_APPROVAL", "PAYMENT_STAGES"],
        planned_reason="Будущий модуль договорного контура.",
        icon="file-signature",
        color="#f43f5e",
    ),
    _planned_registry_item(
        "MODULE_16_LOGISTICS_DELIVERY",
        "Логистика",
        order=1600,
        short_title="Логистика",
        description="Доставка, зоны обслуживания, маршруты и статусы поставок.",
        expected_feature_codes=["DELIVERY_ZONES", "ROUTES", "SHIPMENT_STATUS"],
        planned_reason="Будущий модуль логистики и доставки.",
        icon="truck",
        color="#22c55e",
    ),
    _planned_registry_item(
        "MODULE_17_FINANCE_PAYMENTS",
        "Финансы",
        order=1700,
        short_title="Финансы",
        description="Платежи, счета, взаиморасчеты и финансовая аналитика.",
        expected_feature_codes=["PAYMENTS", "INVOICES", "BALANCE", "FINANCE_REPORTS"],
        planned_reason="Будущий модуль финансов и платежей.",
        icon="wallet",
        color="#f59e0b",
    ),
)


def get_dashboard_module_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in DASHBOARD_MODULE_REGISTRY]


def get_planned_dashboard_modules(user_profile: Any) -> list[dict[str, Any]]:
    if not _can_see_planned_modules(_profile_dict(user_profile)):
        return []
    planned_modules = [
        item
        for item in DASHBOARD_MODULE_REGISTRY
        if item.status in PLANNED_STATUSES and not item.isAvailableForDashboard
    ]
    return [item.to_dict() for item in sorted(planned_modules, key=lambda module: module.displayOrder)]


def get_dashboard_module_registry_item(module_code: str | None) -> DashboardModuleRegistryItem | None:
    if not module_code:
        return None
    for item in DASHBOARD_MODULE_REGISTRY:
        if module_code == item.moduleCode or module_code in item.legacyCodes:
            return item
    return None


def get_dashboard_module_registry_item_by_number(number: int | None) -> DashboardModuleRegistryItem | None:
    if number is None:
        return None
    for item in DASHBOARD_MODULE_REGISTRY:
        if number in {item.legacyNumber, item.displayNumber, item.visualNumber}:
            return item
    return None


def get_canonical_module_code(module_code: str | None) -> str | None:
    item = get_dashboard_module_registry_item(module_code)
    if not item:
        return module_code
    return item.canonicalModuleCode or item.mergedIntoModuleCode or item.moduleCode


def resolve_module_route(module_code: str | None) -> str | None:
    item = get_dashboard_module_registry_item(module_code)
    if not item:
        return None
    if item.status in {MERGED_STATUS, "deprecated"} and item.redirectRoute:
        return item.redirectRoute
    return item.route or item.redirectRoute


def is_module_available_for_dashboard(module_code: str | None) -> bool:
    item = get_dashboard_module_registry_item(module_code)
    if not item:
        return False
    return item.isAvailableForDashboard and item.status not in HIDDEN_ACTIVE_STATUSES | PLANNED_STATUSES


def get_visible_dashboard_modules(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    allowed = {get_canonical_module_code(code) for code in data.get("allowedModuleCodes", [])}
    allowed.update(get_canonical_module_code(code) for code in data.get("allowedModules", []))
    allowed.discard(None)
    can_see_planned = _can_see_planned_modules(data)

    modules: list[DashboardModuleRegistryItem] = []
    for item in DASHBOARD_MODULE_REGISTRY:
        canonical = get_canonical_module_code(item.moduleCode)
        if canonical not in allowed and item.moduleCode not in allowed:
            continue
        if item.status in HIDDEN_ACTIVE_STATUSES:
            continue
        if item.status in PLANNED_STATUSES and not can_see_planned:
            continue
        if not item.isAvailableForDashboard:
            continue
        modules.append(item)
    return [item.to_dict() for item in sorted(modules, key=lambda module: module.displayOrder)]


def get_atom_map_modules(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    favorites = [get_canonical_module_code(code) for code in data.get("favoriteModuleCodes", [])]
    favorites.extend(get_canonical_module_code(code) for code in data.get("favoriteModules", []))
    favorite_order = {code: index for index, code in enumerate(code for code in favorites if code)}

    modules = [
        item
        for item in get_visible_dashboard_modules(data)
        if item.get("isVisibleOnAtomMap")
    ]
    return sorted(
        modules,
        key=lambda item: (
            favorite_order.get(get_canonical_module_code(item["moduleCode"]), 999),
            item["displayOrder"],
        ),
    )


def normalize_dashboard_layout(layout: Any) -> Any:
    normalized = deepcopy(layout)
    if not isinstance(normalized, dict):
        return normalized

    for key in ("favoriteModules", "favoriteModuleCodes", "allowedModules", "allowedModuleCodes"):
        if isinstance(normalized.get(key), list):
            normalized[key] = _normalize_module_code_list(normalized[key])

    atom_map = normalized.get("atomMap")
    if isinstance(atom_map, dict):
        for key in ("favoriteModules", "favoriteModuleCodes", "allowedModules", "allowedModuleCodes"):
            if isinstance(atom_map.get(key), list):
                atom_map[key] = _normalize_module_code_list(atom_map[key])

    widgets = normalized.get("widgets")
    if isinstance(widgets, list):
        normalized["widgets"] = [_normalize_widget_layout(widget) for widget in widgets]

    return normalized


def get_active_region(user_profile: Any) -> dict[str, str | None]:
    data = _profile_dict(user_profile)
    return {
        "activeRegionCode": data.get("activeRegionCode"),
        "activeRegionName": data.get("activeRegionName"),
    }


def is_region_available_for_dashboard(active_region_code: str | None, user_profile: Any | None = None) -> bool:
    if not active_region_code:
        return False
    data = _profile_dict(user_profile)
    available = data.get("availableRegionCodes") or []
    if available:
        return active_region_code in available
    return is_known_platform_region_code(active_region_code)


def _normalize_widget_layout(widget: Any) -> Any:
    if not isinstance(widget, dict):
        return widget
    normalized = dict(widget)
    normalized.pop("sourceModuleNumber", None)
    module_code = normalized.get("sourceModuleCode") or normalized.get("moduleCode")
    if not module_code and normalized.get("moduleNumberLegacy") is not None:
        item = get_dashboard_module_registry_item_by_number(normalized.get("moduleNumberLegacy"))
        module_code = item.moduleCode if item else None
    if module_code:
        canonical = get_canonical_module_code(module_code)
        if canonical and canonical != module_code:
            normalized.setdefault("legacyModuleCode", module_code)
        normalized["sourceModuleCode"] = canonical
        normalized["moduleCode"] = canonical
        normalized["canonicalModuleCode"] = canonical
    if "widgetCode" not in normalized:
        widget_type = normalized.get("type", "STATUS")
        title = normalized.get("title", "widget")
        normalized["widgetCode"] = f"{normalized.get('canonicalModuleCode', 'DASHBOARD')}.{widget_type}.{title}"
    return normalized


def _normalize_module_code_list(module_codes: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    seen: set[Any] = set()
    for module_code in module_codes:
        canonical = get_canonical_module_code(module_code) if isinstance(module_code, str) else module_code
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


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


def _can_see_planned_modules(profile: dict[str, Any]) -> bool:
    role_code = profile.get("roleCode") or profile.get("role")
    auth_mode = profile.get("authMode")
    return auth_mode in {"mock", "dev"} and role_code in {"ADMIN", "SUPER_ADMIN", "DEV_ADMIN"}


getCanonicalModuleCode = get_canonical_module_code
getVisibleDashboardModules = get_visible_dashboard_modules
getAtomMapModules = get_atom_map_modules
resolveModuleRoute = resolve_module_route
normalizeDashboardLayout = normalize_dashboard_layout
isModuleAvailableForDashboard = is_module_available_for_dashboard
getActiveRegion = get_active_region
isRegionAvailableForDashboard = is_region_available_for_dashboard
