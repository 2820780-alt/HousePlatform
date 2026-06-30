from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.partner_portal_adapter import getCabinetDashboardContext


router = APIRouter(prefix="/partner-portal/settings", tags=["partner-portal-settings"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def partner_portal_settings_view(request: Request):
    context = _settings_context()
    cabinet_context = getCabinetDashboardContext(context["activeCabinetId"], context)
    return templates.TemplateResponse(
        request,
        "partner_portal_settings.html",
        {
            "context": context,
            "cabinet_context": cabinet_context,
            "sections": _settings_sections(context),
            "atom_topbar_cabinet": "Кабинет заказчика / Customer",
            "atom_topbar_region_code": context["activeRegionCode"],
            "atom_topbar_region_name": "Краснодарский край",
            "atom_topbar_current_block": "Кабинеты участников",
            "atom_topbar_profile_name": "Администратор",
        },
    )


def _settings_context() -> dict:
    return {
        "userId": "module8-preview-user",
        "roleCode": "CUSTOMER",
        "workspaceId": "workspace-customer-preview",
        "activeRegionCode": "KRASNODAR_KRAI",
        "activeCabinetId": "cabinet-customer-preview",
        "permissions": {
            "allowedModuleCodes": [
                "MODULE_07_DIGITAL_HOUSE",
                "MODULE_05_ESTIMATE_ENGINE",
                "MODULE_06_ESTIMATE_AUDIT",
                "MODULE_09_PROCUREMENT",
                "MODULE_10_MARKETPLACE",
                "MODULE_11_ANALYTICS",
                "MODULE_08_PARTNER_PORTAL",
            ],
            "allowedFeatureCodes": [
                "CUSTOMER_OBJECTS",
                "ESTIMATE_ENGINE",
                "ESTIMATE_AUDIT",
                "HOUSE_STORAGE",
                "PROCUREMENT_REQUESTS",
                "VISIBILITY_SETTINGS",
                "OFFER_SETTINGS",
                "PARTNER_CONTACTS",
                "PARTNER_BRANCHES",
                "SUPPLY_REGIONS",
                "CABINET_DOCUMENTS",
            ],
            "allowedWidgetCodes": [
                "atom-map",
                "digital-house-status",
                "estimate-summary",
                "estimate-audit-risk",
                "procurement-requests",
                "price-dynamics",
            ],
            "allowedQuickActionCodes": [
                "CUSTOMER_OBJECT_CREATE",
                "CUSTOMER_ESTIMATE_REQUEST",
                "CUSTOMER_PROCUREMENT_REQUEST",
                "DASHBOARD_CONFIGURE",
            ],
        },
        "availableCabinets": [
            {
                "cabinetId": "cabinet-customer-preview",
                "cabinetType": "CUSTOMER",
                "title": "Кабинет заказчика",
                "businessRole": "CUSTOMER",
                "workspaceId": "workspace-customer-preview",
                "isActive": True,
            },
            {
                "cabinetId": "cabinet-supplier-preview",
                "cabinetType": "MATERIAL_SUPPLIER",
                "title": "Кабинет поставщика",
                "businessRole": "SUPPLIER",
                "workspaceId": "workspace-supplier-preview",
            },
        ],
        "linkedObjects": [
            {
                "cabinetId": "cabinet-customer-preview",
                "objectId": "object-house-120",
                "relationType": "OWNER",
                "visibilityScope": "PRIVATE",
                "sourceModuleCode": "MODULE_07_DIGITAL_HOUSE",
            }
        ],
        "objectVisibilitySettings": [
            {
                "cabinetId": "cabinet-customer-preview",
                "objectId": "object-house-120",
                "visibilityScope": "PRIVATE",
                "showRegion": True,
                "showExactAddress": False,
                "showCustomerContacts": False,
                "showEstimate": False,
            }
        ],
    }


def _settings_sections(context: dict) -> list[dict]:
    active_cabinet_id = context["activeCabinetId"]
    return [
        {
            "code": "profile",
            "title": "Профиль кабинета",
            "description": "Название, тип кабинета, бизнес-роль и статус проверки.",
            "rows": [
                ("Тип", "CUSTOMER"),
                ("Бизнес-роль", context["roleCode"]),
                ("Verification", "DRAFT / NOT_VERIFIED"),
            ],
        },
        {
            "code": "create",
            "title": "Создание кабинета",
            "description": "Мастер создания нового кабинета без создания второго Dashboard.",
            "rows": [
                ("Доступно", "Customer, Supplier, Construction Company, Specialist"),
                ("Источник прав", "MODULE_03_USERS_ROLES"),
            ],
        },
        {
            "code": "switch",
            "title": "Переключение кабинета",
            "description": "Выбор активного кабинета пользователя.",
            "rows": [
                ("Активный кабинет", active_cabinet_id),
                ("Доступно кабинетов", str(len(context["availableCabinets"]))),
            ],
        },
        {
            "code": "employees",
            "title": "Сотрудники",
            "description": "Бизнес-роли сотрудников кабинета. Права остаются в Module №3.",
            "rows": [
                ("CabinetEmployee", "готово"),
                ("CabinetMembership", "готово"),
            ],
        },
        {
            "code": "contacts",
            "title": "Контакты",
            "description": "Контакты участника, отделов и ответственных лиц.",
            "rows": [("Контакты", "Module 8 profile context")],
        },
        {
            "code": "branches",
            "title": "Филиалы",
            "description": "Офисы, склады, точки присутствия и зоны обслуживания.",
            "rows": [("Филиалы", "CabinetBranch")],
        },
        {
            "code": "regions",
            "title": "Регионы",
            "description": "Регионы работы, поставки и доставки. Без hardcode бизнес-условий.",
            "rows": [("activeRegionCode", context["activeRegionCode"])],
        },
        {
            "code": "documents",
            "title": "Документы",
            "description": "Документы кабинета / компании. Не документы материалов Module №1.",
            "rows": [("featureCode", "CABINET_DOCUMENTS")],
        },
        {
            "code": "objects",
            "title": "Связанные объекты",
            "description": "Ссылки на объекты из Module №7 и visibility context.",
            "rows": [("CabinetObjectLink", "OWNER / INVITED / OFFER_ALLOWED")],
        },
        {
            "code": "visibility",
            "title": "Настройки видимости",
            "description": "Privacy-first доступность объекта, адреса, сметы и контактов.",
            "rows": [
                ("Точный адрес", "скрыт по умолчанию"),
                ("Контакты", "скрыты по умолчанию"),
                ("Смета", "скрыта по умолчанию"),
            ],
        },
        {
            "code": "offers",
            "title": "Настройки предложений",
            "description": "Opt-in получение предложений без создания сделки, КП или закупки.",
            "rows": [
                ("canReceiveOffers", "false by default"),
                ("offerContactPolicy", "HIDDEN"),
            ],
        },
        {
            "code": "workspace",
            "title": "Настройки рабочего экрана",
            "description": "Cabinet presets, blocks, widget preferences и quick actions.",
            "rows": [
                ("Preset", "CustomerDashboardPreset"),
                ("Dashboard", "только отображает"),
            ],
        },
    ]
