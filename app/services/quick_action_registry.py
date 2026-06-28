from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.system_roles import LEGACY_ADMIN_ROLE_CODES
from app.services.dashboard_module_registry import get_canonical_module_code
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, DASHBOARD_ADMIN_SOURCE_MODULE


QUICK_ACTION_STATUSES: tuple[str, ...] = ("ACTIVE", "DRAFT", "PLANNED", "DISABLED")
ACTIVE_QUICK_ACTION_STATUSES = {"ACTIVE"}
PREVIEW_QUICK_ACTION_STATUSES = {"DRAFT", "PLANNED", "DISABLED"}
QUICK_ACTION_PREVIEW_ROLE_CODES = {"SUPER_ADMIN", "PLATFORM_ADMIN", *LEGACY_ADMIN_ROLE_CODES}

QUICK_ACTION_REGISTRY_LAYER = "module03_quick_action_registry"
QUICK_ACTION_REGISTRY_NOTE = (
    "QuickActionRegistry is a Module 03 metadata and permission layer. "
    "Module 08 may later recommend which actions are relevant for an active cabinet. "
    "Owning modules still execute business operations and must call requirePermission()."
)


@dataclass(frozen=True)
class QuickActionRegistryItemDefinition:
    id: str
    quickActionCode: str
    title: str
    sourceModuleCode: str
    requiredActionCode: str
    requiredAccessLevel: str
    requiredScope: str
    status: str
    isSystem: bool
    order: int
    description: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    widgetCode: str | None = None
    allowedRoles: list[str] = field(default_factory=list)
    allowedCabinetTypes: list[str] = field(default_factory=list)
    route: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    registryLayer: str = QUICK_ACTION_REGISTRY_LAYER
    compatibilityNote: str = QUICK_ACTION_REGISTRY_NOTE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_quick_action_registry() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _quick_action_registry_definitions()]


def get_quick_action_registry_item(quick_action_code: str | None) -> QuickActionRegistryItemDefinition | None:
    if not quick_action_code:
        return None
    return next(
        (
            item
            for item in _quick_action_registry_definitions()
            if item.quickActionCode == quick_action_code
        ),
        None,
    )


def get_available_quick_action_registry_items(user_profile: Any, context: Any | None = None) -> list[dict[str, Any]]:
    from app.services.quick_action_permission import can_use_quick_action

    effective_context = context or user_profile
    return [
        item.to_dict()
        for item in _quick_action_registry_definitions()
        if can_use_quick_action(user_profile, item.quickActionCode, effective_context)
    ]


def get_preview_quick_action_registry_items(user_profile: Any) -> list[dict[str, Any]]:
    data = _profile_dict(user_profile)
    if data.get("authMode") not in {"mock", "dev"}:
        return []
    role_code = (data.get("effectiveRoleCode") or data.get("roleCode") or "").upper()
    if role_code not in QUICK_ACTION_PREVIEW_ROLE_CODES:
        return []
    return [
        item.to_dict()
        for item in _quick_action_registry_definitions()
        if item.status in PREVIEW_QUICK_ACTION_STATUSES
    ]


def _quick_action_registry_definitions() -> tuple[QuickActionRegistryItemDefinition, ...]:
    return (
        _item(
            quickActionCode="MATERIAL_CREATE",
            title="Добавить материал",
            description="Переход к созданию или карточке материала. Бизнес-создание проверяет Module 1.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="MATERIAL_CREATE",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "KNOWLEDGE_MANAGER"],
            allowedCabinetTypes=["ADMIN", "KNOWLEDGE_MANAGER"],
            route="/api/v1/admin/material-hub/view/materials",
            order=10,
            settings={"icon": "+", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="SUPPLIER_PRICE_UPLOAD",
            title="Загрузить прайс",
            description=(
                "Безопасный переход к экрану загрузки прайса. "
                "Сам upload должен проверять CREATE/UPLOAD внутри Module 1."
            ),
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="UPLOAD_SUPPLIER_FILE",
            requiredActionCode="VIEW",
            requiredAccessLevel=AccessLevel.VIEW,
            requiredScope=AccessScope.LIMITED,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "SUPPLIER"],
            allowedCabinetTypes=["ADMIN", "SUPPLIER"],
            route="/api/v1/admin/material-hub/view",
            order=20,
            settings={"icon": "⇧", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="SOURCE_TASK_CREATE",
            title="Запустить анализ источника",
            description="Переход к задачам анализа источников. Запуск задачи проверяется в Module 1.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="SOURCE_TASK_CREATE",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN"],
            allowedCabinetTypes=["ADMIN"],
            route="/api/v1/admin/material-hub/view",
            order=30,
            settings={"icon": "▶", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="MATERIAL_MODERATION_OPEN",
            title="Открыть модерацию",
            description="Переход к очереди модерации материалов.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="MODERATION",
            requiredActionCode="APPROVE",
            requiredAccessLevel=AccessLevel.APPROVE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "MODERATOR"],
            allowedCabinetTypes=["ADMIN", "MODERATOR"],
            route="/api/v1/admin/material-hub/view/moderation",
            order=40,
            settings={"icon": "!", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="SOURCE_ERRORS_OPEN",
            title="Проверить ошибки сбора",
            description="Переход к ошибкам и задачам сбора источников.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="SOURCE_TASK_ERRORS",
            requiredActionCode="VIEW",
            requiredAccessLevel=AccessLevel.VIEW,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "MODERATOR", "ANALYST"],
            allowedCabinetTypes=["ADMIN", "MODERATOR", "ANALYST"],
            route="/api/v1/admin/material-hub/view/tasks",
            order=50,
            settings={"icon": "×", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="SOURCE_CREATE",
            title="Добавить источник",
            description="Переход к источникам. Создание источника остается операцией Module 1.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="SOURCE_CREATE",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN"],
            allowedCabinetTypes=["ADMIN"],
            route="/api/v1/admin/material-hub/view/sources",
            order=60,
            settings={"icon": "+", "payloadOwner": "MODULE_01_MATERIAL_HUB", "mock": True},
        ),
        _item(
            quickActionCode="DOCUMENT_LIST_OPEN",
            title="Открыть документы",
            description="Переход к документам Material Hub.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="DOCUMENTS",
            requiredActionCode="VIEW",
            requiredAccessLevel=AccessLevel.VIEW,
            requiredScope=AccessScope.LIMITED,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "KNOWLEDGE_MANAGER", "ENGINEER_DESIGNER", "ANALYST"],
            allowedCabinetTypes=["ADMIN", "KNOWLEDGE_MANAGER", "ENGINEER_DESIGNER", "ANALYST"],
            route="/api/v1/admin/material-hub/view/documents",
            order=70,
            settings={"icon": "□", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="MATERIAL_APPROVE",
            title="Подтвердить материал",
            description="Модераторский переход к подтверждению материалов.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="MODERATION",
            requiredActionCode="APPROVE",
            requiredAccessLevel=AccessLevel.APPROVE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "MODERATOR"],
            allowedCabinetTypes=["ADMIN", "MODERATOR"],
            route="/api/v1/admin/material-hub/view/moderation",
            order=80,
            settings={"icon": "✓", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="MATERIAL_CLASSIFICATION_FIX",
            title="Исправить классификацию",
            description="Переход к ручной классификации материалов.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="CLASSIFICATION",
            requiredActionCode="APPROVE",
            requiredAccessLevel=AccessLevel.APPROVE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "MODERATOR"],
            allowedCabinetTypes=["ADMIN", "MODERATOR"],
            route="/api/v1/admin/material-hub/view/moderation",
            order=90,
            settings={"icon": "↻", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="MATERIAL_RECHECK_SEND",
            title="Отправить на повторную проверку",
            description="Переход к повторной проверке материалов.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="MODERATION",
            requiredActionCode="APPROVE",
            requiredAccessLevel=AccessLevel.APPROVE,
            requiredScope=AccessScope.GLOBAL,
            allowedRoles=["SUPER_ADMIN", "PLATFORM_ADMIN", "ADMIN", "MODERATOR"],
            allowedCabinetTypes=["ADMIN", "MODERATOR"],
            route="/api/v1/admin/material-hub/view/moderation",
            order=100,
            settings={"icon": "↺", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="SUPPLIER_PRICE_UPDATE",
            title="Обновить цену",
            description="Будущая операция поставщика. Пока только planned metadata.",
            sourceModuleCode="MODULE_01_MATERIAL_HUB",
            featureCode="SUPPLIER_PRICE_UPDATE",
            requiredActionCode="VIEW",
            requiredAccessLevel=AccessLevel.VIEW,
            requiredScope=AccessScope.LIMITED,
            allowedRoles=["SUPPLIER"],
            allowedCabinetTypes=["SUPPLIER"],
            route="/api/v1/admin/material-hub/view",
            status="PLANNED",
            order=110,
            settings={"icon": "↗", "payloadOwner": "MODULE_01_MATERIAL_HUB"},
        ),
        _item(
            quickActionCode="SUPPLIER_OFFER_CREATE",
            title="Предложить товар",
            description="Будущая операция витрины/поставщика. Не активна в MVP.",
            sourceModuleCode="MODULE_10_MARKETPLACE",
            featureCode="SUPPLIER_OFFER",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.OWN,
            allowedRoles=["SUPPLIER"],
            allowedCabinetTypes=["SUPPLIER"],
            route="/modules/marketplace",
            status="PLANNED",
            order=120,
            settings={"icon": "+", "payloadOwner": "MODULE_10_MARKETPLACE"},
        ),
        _item(
            quickActionCode="CUSTOMER_OBJECT_CREATE",
            title="Создать объект",
            description="Будущая операция Module 7. Не активна до готовности Digital House.",
            sourceModuleCode="MODULE_07_DIGITAL_HOUSE",
            featureCode="HOUSE_PROFILE",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.OWN,
            allowedRoles=["CUSTOMER"],
            allowedCabinetTypes=["CUSTOMER"],
            route="/modules/digital-house",
            status="PLANNED",
            order=130,
            settings={"icon": "+", "payloadOwner": "MODULE_07_DIGITAL_HOUSE"},
        ),
        _item(
            quickActionCode="CUSTOMER_ESTIMATE_REQUEST",
            title="Получить смету",
            description="Будущая операция Module 5. Не активна до готовности Estimate Engine.",
            sourceModuleCode="MODULE_05_ESTIMATE_ENGINE",
            featureCode="ESTIMATE_REQUEST",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.OWN,
            allowedRoles=["CUSTOMER"],
            allowedCabinetTypes=["CUSTOMER"],
            route="/modules/estimates",
            status="PLANNED",
            order=140,
            settings={"icon": "₽", "payloadOwner": "MODULE_05_ESTIMATE_ENGINE"},
        ),
        _item(
            quickActionCode="CUSTOMER_PROCUREMENT_REQUEST",
            title="Отправить заявку",
            description="Будущая операция Module 9. Не активна до готовности Procurement.",
            sourceModuleCode="MODULE_09_PROCUREMENT",
            featureCode="PROCUREMENT_REQUEST",
            requiredActionCode="CREATE",
            requiredAccessLevel=AccessLevel.CREATE,
            requiredScope=AccessScope.OWN,
            allowedRoles=["CUSTOMER"],
            allowedCabinetTypes=["CUSTOMER"],
            route="/modules/procurement",
            status="PLANNED",
            order=150,
            settings={"icon": "→", "payloadOwner": "MODULE_09_PROCUREMENT"},
        ),
        _item(
            quickActionCode="DASHBOARD_CONFIGURE",
            title="Настроить Dashboard",
            description="Переход к настройке существующего Dashboard.",
            sourceModuleCode=DASHBOARD_ADMIN_SOURCE_MODULE,
            featureCode="DASHBOARD_PERSONALIZE",
            requiredActionCode="VIEW",
            requiredAccessLevel=AccessLevel.VIEW,
            requiredScope=AccessScope.LIMITED,
            allowedRoles=[
                "SUPER_ADMIN",
                "PLATFORM_ADMIN",
                "ADMIN",
                "MODERATOR",
                "KNOWLEDGE_MANAGER",
                "ESTIMATOR",
                "ENGINEER_DESIGNER",
                "SUPPLIER",
                "CONTRACTOR",
                "CUSTOMER",
                "ANALYST",
            ],
            allowedCabinetTypes=[
                "ADMIN",
                "MODERATOR",
                "KNOWLEDGE_MANAGER",
                "ESTIMATOR",
                "ENGINEER_DESIGNER",
                "SUPPLIER",
                "CONTRACTOR",
                "CUSTOMER",
                "ANALYST",
            ],
            route="#dashboard-config",
            order=900,
            settings={
                "icon": "⚙",
                "contextCode": DASHBOARD_ADMIN_CONTEXT,
                "payloadOwner": DASHBOARD_ADMIN_CONTEXT,
            },
        ),
    )


def _item(**data: Any) -> QuickActionRegistryItemDefinition:
    source_module_code = data["sourceModuleCode"]
    canonical_module_code = get_canonical_module_code(source_module_code) or source_module_code
    return QuickActionRegistryItemDefinition(
        id=data.get("id") or data["quickActionCode"],
        quickActionCode=data["quickActionCode"],
        title=data["title"],
        description=data.get("description"),
        sourceModuleCode=source_module_code,
        canonicalModuleCode=data.get("canonicalModuleCode") or canonical_module_code,
        featureCode=data.get("featureCode"),
        widgetCode=data.get("widgetCode"),
        requiredActionCode=str(data["requiredActionCode"]),
        requiredAccessLevel=str(data["requiredAccessLevel"]),
        requiredScope=str(data["requiredScope"]),
        allowedRoles=list(data.get("allowedRoles") or []),
        allowedCabinetTypes=list(data.get("allowedCabinetTypes") or []),
        route=data.get("route"),
        status=data.get("status", "ACTIVE"),
        isSystem=data.get("isSystem", True),
        order=data.get("order", 1000),
        settings=dict(data.get("settings") or {}),
    )


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
