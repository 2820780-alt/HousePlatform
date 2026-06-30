from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_cabinet_types import (
    CONSTRUCTION_COMPANY,
    CUSTOMER,
    MATERIAL_SUPPLIER,
    SPECIALIST,
    normalize_cabinet_type,
)


@dataclass(frozen=True)
class BlockPermissionRequirement:
    moduleCode: str
    actionCode: str = "VIEW"
    scope: str = "LIMITED"
    featureCode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CabinetBlockDefinition:
    blockCode: str
    sourceModuleCode: str
    featureCode: str
    userTitle: str
    description: str
    allowedCabinetTypes: list[str] = field(default_factory=list)
    allowedBusinessRoles: list[str] = field(default_factory=list)
    requiresPermission: BlockPermissionRequirement | None = None
    isFuture: bool = False
    isPremiumFeature: bool = False
    sourceContextModuleCode: str = MODULE_08_PARTNER_PORTAL
    status: str = "ACTIVE"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["requiresPermission"] = (
            self.requiresPermission.to_dict()
            if self.requiresPermission
            else None
        )
        return data


def get_cabinet_block_catalog(*, include_future: bool = True) -> list[dict[str, Any]]:
    return [
        item.to_dict()
        for item in CABINET_BLOCK_CATALOG
        if include_future or not item.isFuture
    ]


def get_cabinet_block_definitions(*, include_future: bool = True) -> tuple[CabinetBlockDefinition, ...]:
    if include_future:
        return CABINET_BLOCK_CATALOG
    return tuple(item for item in CABINET_BLOCK_CATALOG if not item.isFuture)


def get_cabinet_block_definition(block_code: str | None) -> CabinetBlockDefinition | None:
    if not block_code:
        return None
    normalized = str(block_code).upper()
    return next(
        (
            item
            for item in CABINET_BLOCK_CATALOG
            if item.blockCode == normalized
        ),
        None,
    )


def get_blocks_for_cabinet_type(
    cabinet_type: str | None,
    *,
    business_role: str | None = None,
    include_future: bool = False,
) -> list[dict[str, Any]]:
    normalized_type = normalize_cabinet_type(cabinet_type)
    normalized_role = str(business_role).upper() if business_role else None
    blocks: list[dict[str, Any]] = []
    for item in CABINET_BLOCK_CATALOG:
        if item.isFuture and not include_future:
            continue
        if normalized_type and item.allowedCabinetTypes and normalized_type not in item.allowedCabinetTypes:
            continue
        if normalized_role and item.allowedBusinessRoles and normalized_role not in item.allowedBusinessRoles:
            continue
        blocks.append(item.to_dict())
    return blocks


def _requires(
    module_code: str,
    *,
    feature_code: str | None = None,
    action_code: str = "VIEW",
    scope: str = "LIMITED",
) -> BlockPermissionRequirement:
    return BlockPermissionRequirement(
        moduleCode=module_code,
        featureCode=feature_code,
        actionCode=action_code,
        scope=scope,
    )


CABINET_BLOCK_CATALOG: tuple[CabinetBlockDefinition, ...] = (
    CabinetBlockDefinition(
        blockCode="MY_OBJECTS_BLOCK",
        sourceModuleCode="MODULE_07_DIGITAL_HOUSE",
        featureCode="CUSTOMER_OBJECTS",
        userTitle="Мои объекты",
        description="Список объектов заказчика. Объекты и их состояние остаются в Module 7.",
        allowedCabinetTypes=[CUSTOMER],
        allowedBusinessRoles=["CUSTOMER"],
        requiresPermission=_requires("MODULE_07_DIGITAL_HOUSE", feature_code="CUSTOMER_OBJECTS"),
    ),
    CabinetBlockDefinition(
        blockCode="OBJECT_IMAGE_BLOCK",
        sourceModuleCode="MODULE_07_DIGITAL_HOUSE",
        featureCode="HOUSE_PROFILE",
        userTitle="Образ объекта",
        description="Краткий контекст активного дома или квартиры. Данные объекта остаются в Module 7.",
        allowedCabinetTypes=[CUSTOMER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "CONTRACTOR", "ENGINEER_DESIGNER", "ESTIMATOR"],
        requiresPermission=_requires("MODULE_07_DIGITAL_HOUSE", feature_code="HOUSE_PROFILE"),
    ),
    CabinetBlockDefinition(
        blockCode="ESTIMATES_BLOCK",
        sourceModuleCode="MODULE_05_ESTIMATE_ENGINE",
        featureCode="ESTIMATE_ENGINE",
        userTitle="Сметы",
        description="Сводка по сметам и переход к расчетам. Module 8 не считает сметы.",
        allowedCabinetTypes=[CUSTOMER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "CONTRACTOR", "ESTIMATOR"],
        requiresPermission=_requires("MODULE_05_ESTIMATE_ENGINE", feature_code="ESTIMATE_ENGINE"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="MATERIALS_BLOCK",
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        featureCode="MATERIALS",
        userTitle="Материалы",
        description="Материалы и краткие переходы к Material Hub. Данные материалов остаются в Module 1.",
        allowedCabinetTypes=[SPECIALIST, CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["ESTIMATOR", "PROCUREMENT_ENGINEER", "DESIGNER", "ENGINEER_DESIGNER", "PTO_ENGINEER"],
        requiresPermission=_requires("MODULE_01_MATERIAL_HUB", feature_code="MATERIALS"),
    ),
    CabinetBlockDefinition(
        blockCode="ESTIMATE_AUDIT_BLOCK",
        sourceModuleCode="MODULE_06_ESTIMATE_AUDIT",
        featureCode="ESTIMATE_AUDIT",
        userTitle="Проверка смет",
        description="Риски, расхождения и предупреждения по сметам. Выводы формирует Module 6.",
        allowedCabinetTypes=[CUSTOMER, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "ESTIMATOR", "ANALYST"],
        requiresPermission=_requires("MODULE_06_ESTIMATE_AUDIT", feature_code="ESTIMATE_AUDIT"),
    ),
    CabinetBlockDefinition(
        blockCode="OBJECT_STORAGE_BLOCK",
        sourceModuleCode="MODULE_07_DIGITAL_HOUSE",
        featureCode="HOUSE_STORAGE",
        userTitle="Склад объекта",
        description="Остатки, поступления и нехватки материалов по объекту. Источник данных: Module 7.",
        allowedCabinetTypes=[CUSTOMER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "CONTRACTOR", "FOREMAN"],
        requiresPermission=_requires("MODULE_07_DIGITAL_HOUSE", feature_code="HOUSE_STORAGE"),
    ),
    CabinetBlockDefinition(
        blockCode="PROCUREMENT_BLOCK",
        sourceModuleCode="MODULE_09_PROCUREMENT",
        featureCode="PROCUREMENT_REQUESTS",
        userTitle="Закупки",
        description="Заявки, КП и закупочная потребность. Процессом владеет Module 9.",
        allowedCabinetTypes=[CUSTOMER, MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "SUPPLIER", "CONTRACTOR", "PROCUREMENT_ENGINEER"],
        requiresPermission=_requires("MODULE_09_PROCUREMENT", feature_code="PROCUREMENT_REQUESTS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="DOCUMENTS_BLOCK",
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        featureCode="DOCUMENTS",
        userTitle="Документы материалов",
        description="Сертификаты, техлисты и ссылки на документы. Документами материалов владеет Module 1.",
        allowedCabinetTypes=[CUSTOMER, MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=[
            "CUSTOMER",
            "SUPPLIER",
            "CONTRACTOR",
            "KNOWLEDGE_MANAGER",
            "ENGINEER_DESIGNER",
            "DESIGNER",
            "PTO_ENGINEER",
            "ESTIMATOR",
            "ANALYST",
        ],
        requiresPermission=_requires("MODULE_01_MATERIAL_HUB", feature_code="DOCUMENTS"),
    ),
    CabinetBlockDefinition(
        blockCode="CABINET_DOCUMENTS_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="CABINET_DOCUMENTS",
        userTitle="Документы",
        description="Документы участника, компании или кабинета. Не смешивать с документами материалов Module 1.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=[
            "SUPPLIER",
            "SUPPLIER_OWNER",
            "SUPPLIER_ADMIN",
            "CONTRACTOR",
            "COMPANY_OWNER",
            "COMPANY_ADMIN",
            "PTO_ENGINEER",
            "DESIGNER",
            "ENGINEER_DESIGNER",
        ],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="CABINET_DOCUMENTS"),
    ),
    CabinetBlockDefinition(
        blockCode="TECHNOLOGY_KNOWLEDGE_BLOCK",
        sourceModuleCode="MODULE_02_KNOWLEDGE_BASE",
        featureCode="TECHNOLOGY_KNOWLEDGE",
        userTitle="База знаний",
        description="Технологии, правила и справочные материалы. Источник: Module 2.",
        allowedCabinetTypes=[CUSTOMER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "CONTRACTOR", "KNOWLEDGE_MANAGER", "ENGINEER_DESIGNER", "ESTIMATOR"],
        requiresPermission=_requires("MODULE_02_KNOWLEDGE_BASE", feature_code="TECHNOLOGY_KNOWLEDGE"),
    ),
    CabinetBlockDefinition(
        blockCode="PRICE_ANALYTICS_BLOCK",
        sourceModuleCode="MODULE_11_ANALYTICS",
        featureCode="PRICE_DYNAMICS",
        userTitle="Аналитика цен",
        description="Динамика стоимости и ценовые сигналы. Аналитику формирует Module 11.",
        allowedCabinetTypes=[CUSTOMER, MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "SUPPLIER", "CONTRACTOR", "ANALYST", "ESTIMATOR"],
        requiresPermission=_requires("MODULE_11_ANALYTICS", feature_code="PRICE_DYNAMICS"),
        isPremiumFeature=True,
    ),
    CabinetBlockDefinition(
        blockCode="SUPPLIER_PRICE_LIST_BLOCK",
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        featureCode="SUPPLIER_PRICE_LIST",
        userTitle="Прайс-листы",
        description="Прайсы поставщика и статусы загрузки. Данные цен остаются в Module 1.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER],
        allowedBusinessRoles=["SUPPLIER"],
        requiresPermission=_requires("MODULE_01_MATERIAL_HUB", feature_code="SUPPLIER_PRICE_LIST"),
    ),
    CabinetBlockDefinition(
        blockCode="SUPPLIER_REQUESTS_BLOCK",
        sourceModuleCode="MODULE_09_PROCUREMENT",
        featureCode="SUPPLIER_REQUESTS",
        userTitle="Заявки поставщику",
        description="Входящие заявки и ответы поставщика. Процессом владеет Module 9.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER],
        allowedBusinessRoles=["SUPPLIER"],
        requiresPermission=_requires("MODULE_09_PROCUREMENT", feature_code="SUPPLIER_REQUESTS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="SUPPLY_REGIONS_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="SUPPLY_REGIONS",
        userTitle="Регионы поставки",
        description="Регионы и зоны присутствия поставщика. Module 8 хранит настройки контекста, не логистику.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER],
        allowedBusinessRoles=["SUPPLIER", "SUPPLIER_OWNER", "SUPPLIER_ADMIN", "SALES_MANAGER"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="SUPPLY_REGIONS"),
    ),
    CabinetBlockDefinition(
        blockCode="SUPPLIER_ACTIVE_OBJECTS_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="SUPPLIER_ACTIVE_OBJECTS",
        userTitle="Объекты в работе",
        description="Связанные объекты и видимость для поставщика. Данные объектов остаются в Module 7.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER],
        allowedBusinessRoles=["SUPPLIER", "SUPPLIER_OWNER", "SUPPLIER_ADMIN", "SALES_MANAGER"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="SUPPLIER_ACTIVE_OBJECTS"),
    ),
    CabinetBlockDefinition(
        blockCode="DEMAND_ANALYTICS_BLOCK",
        sourceModuleCode="MODULE_11_ANALYTICS",
        featureCode="DEMAND_ANALYTICS",
        userTitle="Аналитика спроса",
        description="Спрос и рыночные сигналы для поставщика. Аналитику формирует Module 11.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER],
        allowedBusinessRoles=["SUPPLIER", "SUPPLIER_OWNER", "SUPPLIER_ADMIN", "SALES_MANAGER"],
        requiresPermission=_requires("MODULE_11_ANALYTICS", feature_code="DEMAND_ANALYTICS"),
        isPremiumFeature=True,
    ),
    CabinetBlockDefinition(
        blockCode="MARKETPLACE_BLOCK",
        sourceModuleCode="MODULE_10_MARKETPLACE",
        featureCode="MARKETPLACE_OFFERS",
        userTitle="Marketplace",
        description="Предложения поставщика в витрине. Marketplace остается в Module 10.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER],
        allowedBusinessRoles=["SUPPLIER", "SUPPLIER_OWNER", "SUPPLIER_ADMIN", "SALES_MANAGER"],
        requiresPermission=_requires("MODULE_10_MARKETPLACE", feature_code="MARKETPLACE_OFFERS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="COMPANY_PROJECTS_BLOCK",
        sourceModuleCode="MODULE_13_PROJECT_COLLABORATION",
        featureCode="PROJECTS",
        userTitle="Проекты компании",
        description="Проектная активность компании. Источник будущих данных: Module 13.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["CONTRACTOR"],
        requiresPermission=_requires("MODULE_13_PROJECT_COLLABORATION", feature_code="PROJECTS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="COMPANY_OBJECTS_BLOCK",
        sourceModuleCode="MODULE_07_DIGITAL_HOUSE",
        featureCode="COMPANY_OBJECTS",
        userTitle="Объекты",
        description="Объекты компании и ссылки на рабочие объекты. Данные объектов остаются в Module 7.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=[
            "CONTRACTOR",
            "COMPANY_OWNER",
            "COMPANY_ADMIN",
            "FOREMAN",
            "PROCUREMENT_ENGINEER",
            "ESTIMATOR",
            "PROJECT_SALES_MANAGER",
            "PTO_ENGINEER",
            "STOREKEEPER",
        ],
        requiresPermission=_requires("MODULE_07_DIGITAL_HOUSE", feature_code="COMPANY_OBJECTS"),
    ),
    CabinetBlockDefinition(
        blockCode="COMPANY_EMPLOYEES_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="COMPANY_EMPLOYEES",
        userTitle="Сотрудники компании",
        description="Состав участников кабинета и рабочие роли. Это контекст Module 8, не RBAC Module 3.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["CONTRACTOR"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="COMPANY_EMPLOYEES"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="COMPANY_REQUESTS_BLOCK",
        sourceModuleCode="MODULE_09_PROCUREMENT",
        featureCode="COMPANY_REQUESTS",
        userTitle="Заявки",
        description="Заявки компании и входящие запросы. Процессом владеет Module 9.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=[
            "CONTRACTOR",
            "COMPANY_OWNER",
            "COMPANY_ADMIN",
            "FOREMAN",
            "PROCUREMENT_ENGINEER",
            "PROJECT_SALES_MANAGER",
        ],
        requiresPermission=_requires("MODULE_09_PROCUREMENT", feature_code="COMPANY_REQUESTS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="CONTRACTS_BLOCK",
        sourceModuleCode="MODULE_15_CONTRACTS",
        featureCode="CONTRACTS_PENDING",
        userTitle="Договоры",
        description="Договоры и согласования. Источник будущих данных: Module 15.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["CONTRACTOR", "COMPANY_OWNER", "COMPANY_ADMIN", "PROJECT_SALES_MANAGER"],
        requiresPermission=_requires("MODULE_15_CONTRACTS", feature_code="CONTRACTS_PENDING"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="FINANCE_BLOCK",
        sourceModuleCode="MODULE_17_FINANCE_PAYMENTS",
        featureCode="FINANCE_BUDGET",
        userTitle="Финансы",
        description="Бюджет и платежные сигналы. Источник будущих данных: Module 17.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["CONTRACTOR", "COMPANY_OWNER", "COMPANY_ADMIN", "PROJECT_SALES_MANAGER"],
        requiresPermission=_requires("MODULE_17_FINANCE_PAYMENTS", feature_code="FINANCE_BUDGET"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="QUALITY_CONTROL_BLOCK",
        sourceModuleCode="MODULE_18_QUALITY_CONTROL",
        featureCode="QUALITY_CONTROL_ISSUES",
        userTitle="Контроль качества",
        description="Замечания и проверки качества. Источник будущих данных: Module 18.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["CONTRACTOR", "COMPANY_OWNER", "COMPANY_ADMIN", "FOREMAN", "PTO_ENGINEER"],
        requiresPermission=_requires("MODULE_18_QUALITY_CONTROL", feature_code="QUALITY_CONTROL_ISSUES"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="SPECIALIST_SPECIFICATIONS_BLOCK",
        sourceModuleCode="MODULE_02_KNOWLEDGE_BASE",
        featureCode="SPECIALIST_SPECIFICATIONS",
        userTitle="Спецификации",
        description="Профессиональные спецификации и экспертные заготовки. Источник правил: Module 2.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["ESTIMATOR", "PROCUREMENT_ENGINEER", "PTO_ENGINEER", "DESIGNER", "ENGINEER_DESIGNER", "KNOWLEDGE_MANAGER"],
        requiresPermission=_requires("MODULE_02_KNOWLEDGE_BASE", feature_code="SPECIALIST_SPECIFICATIONS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="SPECIALIST_OBJECTS_BLOCK",
        sourceModuleCode="MODULE_07_DIGITAL_HOUSE",
        featureCode="SPECIALIST_OBJECTS",
        userTitle="Объекты",
        description="Объекты, к которым специалист привязан через кабинетный контекст. Объекты остаются в Module 7.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["FOREMAN", "PROCUREMENT_ENGINEER", "ESTIMATOR", "PTO_ENGINEER", "DESIGNER", "ENGINEER_DESIGNER"],
        requiresPermission=_requires("MODULE_07_DIGITAL_HOUSE", feature_code="SPECIALIST_OBJECTS"),
    ),
    CabinetBlockDefinition(
        blockCode="SPECIALIST_TASKS_BLOCK",
        sourceModuleCode="MODULE_13_PROJECT_COLLABORATION",
        featureCode="SPECIALIST_TASKS",
        userTitle="Задачи",
        description="Рабочие задачи специалиста. Источник будущих задач: Module 13.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["FOREMAN", "PROCUREMENT_ENGINEER", "ESTIMATOR", "PTO_ENGINEER", "DESIGNER", "ENGINEER_DESIGNER"],
        requiresPermission=_requires("MODULE_13_PROJECT_COLLABORATION", feature_code="SPECIALIST_TASKS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="PROCUREMENT_SUPPLIERS_BLOCK",
        sourceModuleCode="MODULE_09_PROCUREMENT",
        featureCode="PROCUREMENT_SUPPLIERS",
        userTitle="Поставщики",
        description="Поставщики в контексте закупочной работы. Процессом владеет Module 9.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["PROCUREMENT_ENGINEER"],
        requiresPermission=_requires("MODULE_09_PROCUREMENT", feature_code="PROCUREMENT_SUPPLIERS"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="ESTIMATE_EXPORT_BLOCK",
        sourceModuleCode="MODULE_05_ESTIMATE_ENGINE",
        featureCode="ESTIMATE_EXPORT",
        userTitle="Экспорт",
        description="Экспорт сметных данных. Module 8 только рекомендует блок, экспорт выполняет Module 5.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["ESTIMATOR"],
        requiresPermission=_requires("MODULE_05_ESTIMATE_ENGINE", feature_code="ESTIMATE_EXPORT"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="VOLUMES_BLOCK",
        sourceModuleCode="MODULE_05_ESTIMATE_ENGINE",
        featureCode="WORK_VOLUMES",
        userTitle="Объемы",
        description="Объемы работ и связанный контекст. Источник расчетных данных: Module 5.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["PTO_ENGINEER"],
        requiresPermission=_requires("MODULE_05_ESTIMATE_ENGINE", feature_code="WORK_VOLUMES"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="AS_BUILT_INFO_BLOCK",
        sourceModuleCode="MODULE_13_PROJECT_COLLABORATION",
        featureCode="AS_BUILT_INFO",
        userTitle="Исполнительная информация",
        description="Исполнительная информация для ПТО. Источник будущих данных: Module 13.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["PTO_ENGINEER"],
        requiresPermission=_requires("MODULE_13_PROJECT_COLLABORATION", feature_code="AS_BUILT_INFO"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="PROJECT_DATA_BLOCK",
        sourceModuleCode="MODULE_19_CONSTRUCTOR_LITE",
        featureCode="PROJECT_DATA",
        userTitle="Проектные данные",
        description="Проектные данные и будущие проектные структуры. Источник будущих данных: Module 19.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["DESIGNER", "ENGINEER_DESIGNER"],
        requiresPermission=_requires("MODULE_19_CONSTRUCTOR_LITE", feature_code="PROJECT_DATA"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="OBJECT_PLAN_BLOCK",
        sourceModuleCode="MODULE_19_CONSTRUCTOR_LITE",
        featureCode="OBJECT_PLAN",
        userTitle="План объекта",
        description="План объекта для будущего конструктора. Источник будущих данных: Module 19.",
        allowedCabinetTypes=[SPECIALIST],
        allowedBusinessRoles=["DESIGNER", "ENGINEER_DESIGNER"],
        requiresPermission=_requires("MODULE_19_CONSTRUCTOR_LITE", feature_code="OBJECT_PLAN"),
        isFuture=True,
    ),
    CabinetBlockDefinition(
        blockCode="WORKS_BLOCK",
        sourceModuleCode="MODULE_04_WORKS_COSTS",
        featureCode="WORKS_COSTS",
        userTitle="Работы",
        description="Работы и расценки. Источник данных: Module 4.",
        allowedCabinetTypes=[CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CONTRACTOR", "FOREMAN", "ESTIMATOR", "ENGINEER_DESIGNER"],
        requiresPermission=_requires("MODULE_04_WORKS_COSTS", feature_code="WORKS_COSTS"),
    ),
    CabinetBlockDefinition(
        blockCode="CONTACTS_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="PARTNER_CONTACTS",
        userTitle="Контакты",
        description="Контакты участника кабинета. Это профильный контекст Module 8.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["SUPPLIER", "CONTRACTOR", "SPECIALIST", "ESTIMATOR", "ENGINEER_DESIGNER"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="PARTNER_CONTACTS"),
    ),
    CabinetBlockDefinition(
        blockCode="BRANCHES_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="PARTNER_BRANCHES",
        userTitle="Филиалы",
        description="Филиалы и точки присутствия участника. Это профильный контекст Module 8.",
        allowedCabinetTypes=[MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["SUPPLIER", "CONTRACTOR"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="PARTNER_BRANCHES"),
    ),
    CabinetBlockDefinition(
        blockCode="OFFER_SETTINGS_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="OFFER_SETTINGS",
        userTitle="Настройки предложений",
        description="Правила показа предложений и участия в заявках. Module 8 хранит только настройки видимости.",
        allowedCabinetTypes=[CUSTOMER, MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY],
        allowedBusinessRoles=["CUSTOMER", "SUPPLIER", "CONTRACTOR"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="OFFER_SETTINGS"),
    ),
    CabinetBlockDefinition(
        blockCode="VISIBILITY_SETTINGS_BLOCK",
        sourceModuleCode=MODULE_08_PARTNER_PORTAL,
        featureCode="VISIBILITY_SETTINGS",
        userTitle="Настройки видимости",
        description="Настройки видимости кабинета, объекта и предложений без копирования бизнес-данных других модулей.",
        allowedCabinetTypes=[CUSTOMER, MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST],
        allowedBusinessRoles=["CUSTOMER", "SUPPLIER", "CONTRACTOR", "SPECIALIST", "ESTIMATOR", "ENGINEER_DESIGNER"],
        requiresPermission=_requires(MODULE_08_PARTNER_PORTAL, feature_code="VISIBILITY_SETTINGS"),
    ),
)


__all__ = [
    "BlockPermissionRequirement",
    "CabinetBlockDefinition",
    "CABINET_BLOCK_CATALOG",
    "get_cabinet_block_catalog",
    "get_cabinet_block_definitions",
    "get_cabinet_block_definition",
    "get_blocks_for_cabinet_type",
]
