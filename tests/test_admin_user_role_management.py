import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from jinja2 import Environment, FileSystemLoader

from app.main import app
from app.api.v1.admin_users_roles_view import router as admin_users_roles_router
from app.core.exceptions import ForbiddenError, ValidationError
from app.models import AuditLog, ModuleAccess, Role, User, UserRoleAssignment, Workspace, WorkspaceMember
from app.models.enums import UserRole, UserStatus
from app.services.audit_log_service import AuditLogType, MOCK_AUDIT_EVENTS, clear_mock_audit_events
from app.services.admin_user_role_management import (
    ACCESS_DENY_REASONS,
    ACCESS_REASON_CATEGORIES,
    ACCESS_RESOLUTION_SOURCES,
    ADMIN_UI_STATE_LEGEND,
    COMPANY_ADMIN_ROLE_CODE,
    DISABLE_CONFIRMATION,
    MONETIZATION_READY_FIELDS,
    access_distribution_panel_summary,
    access_matrix_for_subject,
    admin_scope_for_actor,
    active_permissions_for_user,
    active_role_codes_for_user,
    apply_company_context_to_user_summary,
    audit_panel_summary,
    audit_log_summary,
    can_assign_company_admin,
    can_assign_role_code,
    can_company_admin_open_employee_module,
    can_company_admin_open_employee_widget,
    can_disable_user,
    can_manage_company_employee,
    can_open_user_role_admin,
    company_module_is_open,
    company_widget_is_open,
    change_history_for_admin_panel,
    module3_audit_log_entry,
    module3_quick_actions,
    module3_quick_action_settings,
    module_registry_overview_summary,
    pending_access_distribution_items,
    require_can_assign_role,
    require_can_disable_user,
    quick_action_rows_for_user,
    role_group_panel_summary,
    save_user_type_access_matrix_changes,
    settings_panel_summary,
    system_user_cards,
    user_type_access_matrix_view_model,
    user_directory_filter_options,
    user_directory_rows,
    user_directory_summary_chips,
    user_profile_card_summary,
    user_summary,
    user_type_summary_widgets,
    widget_access_rows_for_user,
    widget_registry_overview_summary,
    workspace_panel_summary,
)
from app.services.access_distribution_registry import (
    build_pending_access_distribution_items,
    register_module_for_access_system,
    register_widget_for_access_system,
)
from app.services.module8_cabinet_admin_preview import get_module8_cabinet_admin_preview


def _user(role=UserRole.ADMIN) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        role=role,
    )


def _user_with_assignment(role_code: str) -> User:
    user = _user(UserRole.CUSTOMER)
    role = Role(role_key=role_code, name=role_code, is_system=True)
    user.role_assignments = [
        UserRoleAssignment(
            id=uuid.uuid4(),
            user_id=user.id,
            role_id=uuid.uuid4(),
            role=role,
            status="ACTIVE",
        )
    ]
    return user


def _company_workspace() -> Workspace:
    return Workspace(
        id=uuid.uuid4(),
        name=f"Компания {uuid.uuid4()}",
        slug=f"company-{uuid.uuid4()}",
        workspace_type="CONTRACTOR",
        status="ACTIVE",
        is_active=True,
    )


def _workspace_member(user: User, workspace: Workspace, role_code: str) -> WorkspaceMember:
    member = WorkspaceMember(
        id=uuid.uuid4(),
        user_id=user.id,
        workspace_id=workspace.id,
        role_key=role_code,
        role_code=role_code,
        status="ACTIVE",
    )
    member.user = user
    member.workspace = workspace
    return member


def test_legacy_admin_is_platform_admin_not_super_admin():
    actor = _user(UserRole.ADMIN)

    assert active_role_codes_for_user(actor) == {"PLATFORM_ADMIN"}
    assert can_open_user_role_admin(actor)
    assert can_assign_role_code(actor, "MODERATOR")
    assert not can_assign_role_code(actor, "SUPER_ADMIN")

    with pytest.raises(ForbiddenError):
        require_can_assign_role(actor, "SUPER_ADMIN")


def test_super_admin_can_assign_protected_roles():
    actor = _user_with_assignment("SUPER_ADMIN")

    assert active_role_codes_for_user(actor) == {"CUSTOMER", "SUPER_ADMIN"}
    assert can_open_user_role_admin(actor)
    assert can_assign_role_code(actor, "SUPER_ADMIN")
    require_can_assign_role(actor, "SUPER_ADMIN")


def test_platform_admin_cannot_disable_super_admin():
    actor = _user(UserRole.ADMIN)
    target = _user_with_assignment("SUPER_ADMIN")

    assert not can_disable_user(actor, target)
    with pytest.raises(ForbiddenError):
        require_can_disable_user(actor, target, DISABLE_CONFIRMATION)


def test_disable_user_requires_explicit_confirmation():
    actor = _user_with_assignment("SUPER_ADMIN")
    target = _user(UserRole.SUPPLIER)

    with pytest.raises(ValidationError):
        require_can_disable_user(actor, target, "yes")
    require_can_disable_user(actor, target, DISABLE_CONFIRMATION)


def test_company_admin_role_is_company_scoped_and_cannot_escape_company_access():
    platform_admin = _user(UserRole.ADMIN)
    company_admin = _user(UserRole.CUSTOMER)
    employee = _user(UserRole.SUPPLIER)
    other_employee = _user(UserRole.SUPPLIER)
    company = _company_workspace()
    other_company = _company_workspace()

    company_admin_member = _workspace_member(company_admin, company, COMPANY_ADMIN_ROLE_CODE)
    employee_member = _workspace_member(employee, company, "SUPPLIER")
    other_employee_member = _workspace_member(other_employee, other_company, "SUPPLIER")
    company_admin.workspace_members = [company_admin_member]
    company.members = [company_admin_member, employee_member]
    other_company.members = [other_employee_member]

    admin_scope = admin_scope_for_actor(company_admin)

    assert can_open_user_role_admin(company_admin)
    assert admin_scope["isCompanyAdminMode"] is True
    assert admin_scope["companyWorkspaceIds"] == [str(company.id)]
    assert admin_scope["canSeeRegistryDiagnostics"] is False
    assert admin_scope["canSeeSystemCriticalModules"] is False
    assert can_assign_company_admin(platform_admin, company)
    assert not can_assign_company_admin(company_admin, company)
    assert can_manage_company_employee(company_admin, company, employee_member)
    assert not can_manage_company_employee(company_admin, other_company, other_employee_member)

    company.module_access = [
        ModuleAccess(
            workspace_id=company.id,
            module_code="MODULE_01_MATERIAL_HUB",
            canonical_module_code="MODULE_01_MATERIAL_HUB",
            access_level="NO_ACCESS",
            access_scope="GLOBAL",
            status="ACTIVE",
        )
    ]

    assert not company_module_is_open(company, "MODULE_01_MATERIAL_HUB")
    assert not can_company_admin_open_employee_module(
        company_admin,
        company,
        employee_member,
        "MODULE_01_MATERIAL_HUB",
    )


def test_company_admin_access_matrix_hides_system_critical_modules():
    company_admin = _user(UserRole.CUSTOMER)
    company = _company_workspace()
    company_admin_member = _workspace_member(company_admin, company, COMPANY_ADMIN_ROLE_CODE)
    company_admin.workspace_members = [company_admin_member]
    company.members = [company_admin_member]
    admin_scope = admin_scope_for_actor(company_admin)

    matrix = access_matrix_for_subject(
        {
            "id": str(company_admin.id),
            "roleCodes": ["CUSTOMER"],
            "workspaces": [{"workspaceId": str(company.id)}],
        },
        workspaces=[company],
        roles=[],
        permissions=[],
        include_system_critical=admin_scope["canSeeSystemCriticalModules"],
    )

    module_codes = {row["moduleCode"] for row in matrix["rows"]}
    assert "MODULE_03_USERS_ROLES" not in module_codes


def test_company_admin_cannot_open_widget_when_source_module_is_closed_for_company():
    company_admin = _user(UserRole.CUSTOMER)
    employee = _user(UserRole.SUPPLIER)
    company = _company_workspace()
    company_admin_member = _workspace_member(company_admin, company, COMPANY_ADMIN_ROLE_CODE)
    employee_member = _workspace_member(employee, company, "SUPPLIER")
    company_admin.workspace_members = [company_admin_member]
    company.members = [company_admin_member, employee_member]
    company.module_access = [
        ModuleAccess(
            workspace_id=company.id,
            module_code="MODULE_11_ANALYTICS",
            canonical_module_code="MODULE_11_ANALYTICS",
            access_level="NO_ACCESS",
            access_scope="GLOBAL",
            status="ACTIVE",
        )
    ]

    assert not company_widget_is_open(company, "price-dynamics")
    assert not can_company_admin_open_employee_widget(company_admin, company, employee_member, "price-dynamics")


def test_access_matrix_uses_visible_reasons_without_inheritance_ui_and_revokes_widgets():
    company = _company_workspace()
    company.module_access = [
        ModuleAccess(
            workspace_id=company.id,
            module_code="MODULE_11_ANALYTICS",
            canonical_module_code="MODULE_11_ANALYTICS",
            access_level="NO_ACCESS",
            access_scope="GLOBAL",
            status="ACTIVE",
        )
    ]

    matrix = access_matrix_for_subject(
        {
            "id": "user-1",
            "roleCodes": ["SUPPLIER"],
            "workspaces": [{"workspaceId": str(company.id)}],
        },
        workspaces=[company],
        roles=[],
        permissions=[],
    )

    assert matrix["noInheritanceUi"] is True
    assert "ROLE_DEFAULT" in ACCESS_RESOLUTION_SOURCES
    assert "USER_OVERRIDE" in ACCESS_RESOLUTION_SOURCES
    assert ACCESS_DENY_REASONS["PLATFORM_ADMIN_DENY"] == "Закрыто администратором платформы"
    assert set(ACCESS_DENY_REASONS) == {
        "PLATFORM_ADMIN_DENY",
        "COMPANY_ADMIN_DENY",
        "TARIFF_LIMIT",
        "SYSTEM_LIMIT",
        "MODULE_DISABLED",
        "MODULE_PLANNED",
        "MODULE_DRAFT",
        "WIDGET_DISABLED",
        "WIDGET_REVOKED_BY_MODULE_DENY",
        "USER_BLOCKED",
        "COMPANY_BLOCKED",
    }
    assert ACCESS_REASON_CATEGORIES["PLATFORM_ADMIN_DENY"] == "manual_platform"
    assert ACCESS_REASON_CATEGORIES["COMPANY_ADMIN_DENY"] == "manual_company"
    assert ACCESS_REASON_CATEGORIES["TARIFF_LIMIT"] == "tariff"
    assert tuple(matrix["monetizationReadyFields"]) == MONETIZATION_READY_FIELDS

    analytics = next(row for row in matrix["rows"] if row["moduleCode"] == "MODULE_11_ANALYTICS")
    assert analytics["company"]["label"] == "закрыто"
    assert analytics["company"]["reason"] == "Закрыто администратором платформы"
    assert analytics["company"]["reasonCategory"] == "manual_platform"
    assert analytics["employee"]["label"] == "закрыто"
    assert analytics["revokedWidgetCount"] >= 1

    price_widget = next(widget for widget in analytics["widgets"] if widget["widgetCode"] == "price-dynamics")
    assert price_widget["stateCode"] == "WIDGET_REVOKED_BY_MODULE_DENY"
    assert price_widget["reason"] == "Недоступно: виджет закрыт вместе с модулем"
    assert price_widget["monetization"]["isBillingRestricted"] is False

    planned = next(row for row in matrix["rows"] if row["status"] == "planned")
    assert planned["user"]["stateCode"] == "MODULE_PLANNED"
    assert planned["user"]["reason"] == "Недоступно: модуль еще не активен"


def test_active_module_and_widget_registration_requires_access_distribution():
    module = register_module_for_access_system(
        moduleCode="MODULE_TEST_AUTO_ACCESS",
        canonicalModuleCode="MODULE_TEST_AUTO_ACCESS",
        title="Auto Access Module",
        description="Future module metadata only.",
        status="ACTIVE",
        route="/modules/auto-access",
        icon="box",
        isSystemCritical=True,
        isBillingEligible=True,
        moduleOwnedWidgets=["auto-access-status"],
        registeredAt="2026-06-30",
    )
    widget = register_widget_for_access_system(
        widgetCode="auto-access-status",
        sourceModuleCode="MODULE_TEST_AUTO_ACCESS",
        title="Auto access status",
        description="Future widget metadata only.",
        status="ACTIVE",
        featureCode="AUTO_ACCESS_STATUS",
        isDashboardEligible=True,
        allowedDashboardZones=["TOP"],
        isBillingEligible=True,
        registeredAt="2026-06-30",
    )

    items = build_pending_access_distribution_items([module], [widget])

    assert [item["itemKind"] for item in items] == ["module", "widget"]
    assert {item["code"] for item in items} == {"MODULE_TEST_AUTO_ACCESS", "auto-access-status"}
    assert all(item["statusLabel"] == "новое" for item in items)
    assert all(item["actionLabel"] == "Распределить доступ" for item in items)
    assert all(item["actionTarget"] == "#access-matrix" for item in items)
    assert items[0]["isSystemCritical"] is True
    assert items[0]["isBillingEligible"] is True
    assert items[0]["moduleOwnedWidgets"] == ["auto-access-status"]
    assert items[1]["sourceModuleCode"] == "MODULE_TEST_AUTO_ACCESS"
    assert items[1]["allowedDashboardZones"] == ["TOP"]

    panel = access_distribution_panel_summary(items)
    assert panel["summary"] == {"total": 2, "modules": 1, "widgets": 1}
    assert panel["hasPendingItems"] is True
    assert panel["actionTarget"] == "#access-matrix"
    assert panel["emptyState"] == "Новых модулей и виджетов для распределения нет."
    assert panel["dashboardRewriteRequired"] is False
    assert "Dashboard не переписывается" in panel["dashboardNote"]


def test_user_type_access_matrix_view_model_has_hierarchical_rows_and_dependency_cells():
    matrix = user_type_access_matrix_view_model()

    assert [column["label"] for column in matrix["columns"]] == [
        "Заказчики",
        "Поставщики",
        "Строительные компании",
        "Самостоятельные инженеры",
    ]
    assert matrix["saveAction"] == "/api/v1/admin/users-roles/view/access-matrix"
    assert matrix["saveState"]["dirty"] == "Есть несохраненные изменения"
    assert "AccessMatrixRow / AccessMatrixCell" in matrix["viewModelNote"]

    module_row = next(row for row in matrix["rows"] if row["type"] == "MODULE" and row["moduleCode"] == "MODULE_01_MATERIAL_HUB")
    widget_row = next(row for row in matrix["rows"] if row["type"] == "WIDGET" and row["parentId"] == module_row["id"])
    supplier_module_cell = next(cell for cell in module_row["cells"] if cell["userTypeCode"] == "SUPPLIER")
    customer_module_cell = next(cell for cell in module_row["cells"] if cell["userTypeCode"] == "CUSTOMER")
    customer_widget_cell = next(cell for cell in widget_row["cells"] if cell["userTypeCode"] == "CUSTOMER")

    assert module_row["id"] == "module:MODULE_01_MATERIAL_HUB"
    assert widget_row["parentId"] == module_row["id"]
    assert supplier_module_cell["allowed"] is True
    assert customer_module_cell["allowed"] is False
    assert customer_widget_cell["allowed"] is False
    assert customer_widget_cell["disabled"] is True
    assert customer_widget_cell["inheritedFromModule"] is True
    assert customer_widget_cell["reason"] == "Виджет недоступен, потому что модуль выключен для этого типа пользователя."


@pytest.mark.asyncio
async def test_saving_user_type_access_matrix_writes_history_without_replacing_permissions():
    clear_mock_audit_events()

    await save_user_type_access_matrix_changes(
        None,
        actor={"id": uuid.uuid4()},
        matrix_payload={
            "rows": [{"id": "module:MODULE_01_MATERIAL_HUB", "type": "MODULE"}],
            "changes": [{"rowId": "module:MODULE_01_MATERIAL_HUB", "userTypeCode": "SUPPLIER", "allowed": False}],
        },
    )

    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.MODULE_ACCESS_CHANGED
    assert MOCK_AUDIT_EVENTS[-1]["moduleCode"] == "MODULE_03_USERS_ROLES"
    assert MOCK_AUDIT_EVENTS[-1]["reason"] == "User type access matrix saved from Module 03 UI adapter."
    assert MOCK_AUDIT_EVENTS[-1]["metadata"]["viewModelOnly"] is True
    assert MOCK_AUDIT_EVENTS[-1]["metadata"]["permissionModelReplaced"] is False
    assert MOCK_AUDIT_EVENTS[-1]["metadata"]["historyWritten"] is True
    assert MOCK_AUDIT_EVENTS[-1]["metadata"]["changeCount"] == 1


def test_admin_users_roles_template_renders_module_overview_widgets():
    template = Environment(loader=FileSystemLoader("templates")).get_template("admin_users_roles.html")
    overview = {
        "adminScope": {"isCompanyAdminMode": False},
        "summary": {
            "usersTotal": 0,
            "companiesTotal": 0,
            "blockedUsersTotal": 0,
            "blockedCompaniesTotal": 0,
            "pendingAccessDistributionTotal": 1,
            "historyTotal": 0,
        },
        "userTypeSummaryWidgets": [
            {"userTypeCode": "COMPANY", "title": "Компании", "description": "Юридические лица.", "total": 3, "active": 2, "blocked": 1, "onModeration": 1},
            {"userTypeCode": "SUPPLIER", "title": "Поставщики", "description": "Поставщики.", "total": 4, "active": 3, "blocked": 1, "onModeration": 0},
            {"userTypeCode": "CUSTOMER", "title": "Заказчики", "description": "Заказчики.", "total": 5, "active": 5, "blocked": 0},
            {"userTypeCode": "SPECIALIST", "title": "Специалисты", "description": "Специалисты.", "total": 6, "active": 5, "blocked": 1},
        ],
        "moduleRegistrySummary": {"total": 24, "active": 18, "inDevelopment": 4, "archived": 2},
        "widgetRegistrySummary": {"total": 156, "active": 132, "inDevelopment": 24, "archived": 0},
        "systemUsers": [
            {
                "login": "platform-admin",
                "displayName": "platform-admin",
                "email": "platform-admin@example.com",
                "roleTitle": "Администратор платформы",
                "purpose": "Рабочее управление пользователями.",
                "status": "active",
                "statusLabel": "Активен",
                "lastActivity": "2026-06-30 14:35",
                "isPlaceholder": False,
            },
            {
                "login": "super-admin",
                "displayName": "super-admin",
                "email": "",
                "roleTitle": "Супер администратор",
                "purpose": "Полный контроль платформы.",
                "status": "active",
                "statusLabel": "Активен",
                "lastActivity": "2026-06-30 14:10",
                "isPlaceholder": False,
            },
            {
                "login": "moderator",
                "displayName": "moderator",
                "email": "",
                "roleTitle": "Модератор",
                "purpose": "Модерация пользователей.",
                "status": "active",
                "statusLabel": "Активен",
                "lastActivity": "2026-06-30 13:55",
                "isPlaceholder": False,
            },
        ],
        "userDirectoryRows": [
            {
                "id": "user-1",
                "subjectKind": "user",
                "typeCode": "CUSTOMER",
                "typeLabel": "Заказчик",
                "displayName": "Иван Петров",
                "companyName": "ООО СтройПроект",
                "organizationLabel": "Менеджер",
                "contacts": ["ivan@example.com", "+7 900 000-00-00"],
                "status": "active",
                "statusLabel": "active",
                "moduleCount": 3,
                "widgetCount": 2,
                "moduleLabel": "3 модулей",
                "widgetLabel": "2 виджетов",
                "blocking": "not_blocked",
                "blockingLabel": "—",
                "activity": "has_activity",
                "lastActivity": "2026-06-30 14:35",
                "registeredAt": "2026-06-01 10:00",
                "region": "Краснодарский край",
                "moduleAccess": "has_modules",
                "sortName": "иван петров",
                "sortType": "заказчик",
                "cardUrl": "/api/v1/admin/users-roles/view/users/user-1",
                "searchBlob": "иван петров ivan@example.com ооо стройпроект",
            }
        ],
        "userDirectoryChips": [
            {"typeCode": "ALL", "label": "Все", "count": 1},
            {"typeCode": "COMPANY", "label": "Компании", "count": 0},
            {"typeCode": "SUPPLIER", "label": "Поставщики", "count": 0},
            {"typeCode": "CUSTOMER", "label": "Заказчики", "count": 1},
            {"typeCode": "SPECIALIST", "label": "Специалисты", "count": 0},
        ],
        "userDirectoryFilters": {
            "types": [{"value": "CUSTOMER", "label": "Заказчик"}],
            "statuses": [{"value": "active", "label": "active"}],
            "regions": [{"value": "Краснодарский край", "label": "Краснодарский край"}],
            "moduleAccess": [{"value": "has_modules", "label": "Есть доступ к модулям"}],
        },
        "accessDistributionPanel": {
            "description": "Новые ACTIVE элементы появляются автоматически.",
            "summary": {"total": 1, "modules": 1, "widgets": 0},
            "items": [
                {
                    "itemKind": "module",
                    "title": "Auto Access Module",
                    "statusLabel": "новое",
                    "type": "модуль",
                    "status": "ACTIVE",
                    "registeredAt": "2026-06-30",
                    "reason": "Новый ACTIVE модуль требует распределения доступа.",
                    "moduleCode": "MODULE_TEST_AUTO_ACCESS",
                    "widgetCode": None,
                    "sourceModuleCode": None,
                    "canonicalModuleCode": "MODULE_TEST_AUTO_ACCESS",
                    "featureCode": None,
                    "actionTarget": "#access-matrix",
                    "isSystemCritical": False,
                    "isBillingEligible": False,
                    "allowedDashboardZones": [],
                    "moduleOwnedWidgets": [],
                }
            ],
            "emptyState": "Новых модулей и виджетов для распределения нет.",
        },
        "userTypeAccessMatrix": user_type_access_matrix_view_model(),
        "recentAccessHistory": [
            {
                "id": "audit-1",
                "timestamp": "2026-06-30 14:35",
                "createdAt": "2026-06-30 14:35",
                "actorId": "platform-admin-id",
                "actorName": "platform-admin",
                "actor": "platform-admin",
                "action": "Создание пользователя",
                "actionType": "Создан пользователь",
                "objectTypeCode": "USER",
                "objectId": "user-1",
                "objectName": "ivan@example.com",
                "subjectLabel": "ivan@example.com",
                "objectType": "пользователь",
                "detailsText": "Стандартная регистрация",
                "reason": "Стандартная регистрация",
                "comment": "",
                "result": "SUCCESS",
            }
        ],
        "users": [],
        "companies": [],
        "roles": [],
        "groups": [],
        "companyEmployees": [],
        "roleGroupPanel": {"roles": [], "groups": [], "selectedRole": None, "selectedGroup": None},
        "workspacePanel": {
            "summary": {"total": 0, "active": 0, "companies": 0, "linkedUsers": 0},
            "workspaces": [],
            "selectedWorkspace": None,
        },
        "auditPanel": {
            "summary": {"total": 0, "success": 0, "failed": 0},
            "filters": {"authors": [], "dates": [], "actions": [], "objectTypes": [], "modules": []},
            "rows": [],
            "selectedRecord": None,
        },
        "settingsPanel": {
            "normalSettings": [],
            "superAdminMode": {"enabled": False, "description": "Системные инструменты скрыты."},
            "developerDiagnostics": [],
            "dangerZone": {"warning": "Опасные действия требуют подтверждения.", "actions": [], "confirmationText": "DISABLE_USER"},
        },
        "actorRoleCodes": ["SUPER_ADMIN"],
        "moduleQuickActions": module3_quick_actions(admin_scope={"isCompanyAdminMode": False}, detail_mode=False),
        "moduleQuickActionSettings": module3_quick_action_settings(
            admin_scope={"isCompanyAdminMode": False},
            detail_mode=False,
        ),
    }

    html = template.render(
        mode="list",
        overview=overview,
        detail=None,
        disable_confirmation="DISABLE_USER",
        atom_topbar_current_block="Пользователи и роли",
        atom_topbar_profile_name="Администратор",
    )

    assert 'data-user-type="COMPANY"' in html
    assert "Компании" in html
    assert "Поставщики" in html
    assert "Заказчики" in html
    assert "Специалисты" in html
    assert "История изменений" in html
    assert "Создание пользователя" in html
    assert "Модули в системе" in html
    assert "24" in html
    assert "Виджеты в системе" in html
    assert "156" in html
    assert "Системные пользователи" in html
    assert "platform-admin" in html
    assert "super-admin" in html
    assert "moderator" in html
    assert "Summary chips по типам пользователей" in html
    assert "Поиск по ФИО, компании, email, телефону, ИНН / ID" in html
    assert "Фильтр по типу пользователя" in html
    assert "Фильтр по блокировке" in html
    assert "Фильтр по активности" in html
    assert "Фильтр по региону" in html
    assert "Фильтр по доступу к модулю" in html
    assert "Сортировать по дате регистрации" in html
    assert "Единый список пользователей" in html
    assert "Наименование / ФИО" in html
    assert 'href="/api/v1/admin/users-roles/view/users/user-1"' in html
    assert "data-user-page-summary" in html
    assert 'data-access-type-matrix' in html
    assert "Строительные компании" in html
    assert "Самостоятельные инженеры" in html
    assert "Развернуть все" in html
    assert "Свернуть все" in html
    assert "Сохранить изменения" in html
    assert "Сбросить" in html


def test_pending_distribution_hides_inactive_or_already_distributed_items():
    planned_module = register_module_for_access_system(
        moduleCode="MODULE_TEST_PLANNED_ACCESS",
        title="Planned access module",
        status="PLANNED",
    )
    distributed_module = register_module_for_access_system(
        moduleCode="MODULE_TEST_DISTRIBUTED_ACCESS",
        title="Distributed module",
        status="ACTIVE",
        isAccessDistributed=True,
    )
    draft_widget = register_widget_for_access_system(
        widgetCode="draft-access-widget",
        sourceModuleCode="MODULE_TEST_PLANNED_ACCESS",
        title="Draft widget",
        status="DRAFT",
    )

    assert build_pending_access_distribution_items(
        [planned_module, distributed_module],
        [draft_widget],
    ) == []
    assert pending_access_distribution_items(
        modules=[distributed_module],
        widgets=[],
        distributed_module_codes={"MODULE_TEST_DISTRIBUTED_ACCESS"},
    ) == []


def test_change_history_exposes_filters_old_new_values_and_reason():
    audit = AuditLog(
        id=uuid.uuid4(),
        user_id=None,
        workspace_id=uuid.uuid4(),
        action_type="permission_changed",
        entity_type="ModuleAccess",
        entity_id=uuid.uuid4(),
        result="SUCCESS",
        created_at=datetime(2026, 6, 30, 10, 15, 0),
        details={
            "actorUserId": "actor-1",
            "targetUserId": "user-1",
            "workspaceId": "workspace-1",
            "moduleCode": "MODULE_11_ANALYTICS",
            "canonicalModuleCode": "MODULE_11_ANALYTICS",
            "widgetCode": "price-dynamics",
            "roleCode": "SUPPLIER",
            "oldValue": {"accessLevel": "VIEW"},
            "newValue": {"accessLevel": "NO_ACCESS"},
            "reason": "Закрыто администратором платформы",
            "entityType": "ModuleAccess",
        },
    )

    summary = audit_log_summary(audit)
    assert summary["objectType"] == "виджет"
    assert summary["objectTypeCode"] == "WIDGET"
    assert summary["moduleCode"] == "MODULE_11_ANALYTICS"
    assert summary["widgetCode"] == "price-dynamics"
    assert summary["oldValue"] == {"accessLevel": "VIEW"}
    assert summary["newValue"] == {"accessLevel": "NO_ACCESS"}
    assert summary["reason"] == "Закрыто администратором платформы"
    assert summary["actorId"] == "actor-1"
    assert summary["actorName"] == "system/dev"
    assert summary["action"] == "Изменение индивидуального доступа"
    assert summary["objectId"] == "price-dynamics"
    assert summary["objectName"] == "price-dynamics"
    assert "Старое значение" in summary["detailsText"]
    assert "Новое значение" in summary["detailsText"]
    assert summary["module3Entry"] == {
        "id": str(audit.id),
        "timestamp": "2026-06-30T10:15:00",
        "actorId": "actor-1",
        "actorName": "system/dev",
        "action": "Изменение индивидуального доступа",
        "objectType": "WIDGET",
        "objectId": "price-dynamics",
        "objectName": "price-dynamics",
        "details": summary["detailsText"],
    }

    history = change_history_for_admin_panel([audit], {"id": "user-1", "name": "User One"})
    assert history["filters"]["authors"] == ["system/dev"]
    assert history["filters"]["dates"] == ["2026-06-30"]
    assert history["filters"]["actions"] == ["permission_changed"]
    assert history["filters"]["objectTypes"] == ["виджет"]
    assert history["filters"]["modules"] == ["MODULE_11_ANALYTICS"]
    assert history["filters"]["widgets"] == ["price-dynamics"]
    assert history["bySubject"] == [{"label": "виджет", "count": 1}]
    assert history["notes"]["oldNewValuesVisible"] is True
    assert history["notes"]["reasonOptional"] is True
    assert history["notes"]["businessPayloadLogged"] is False

    panel = audit_panel_summary([audit])
    assert panel["summary"]["total"] == 1
    assert panel["summary"]["success"] == 1
    assert panel["filters"]["actions"] == ["permission_changed"]
    assert panel["filters"]["modules"] == ["MODULE_11_ANALYTICS"]
    assert panel["filters"]["widgets"] == ["price-dynamics"]
    assert panel["selectedRecord"]["oldValue"] == {"accessLevel": "VIEW"}
    assert panel["selectedRecord"]["newValue"] == {"accessLevel": "NO_ACCESS"}
    assert panel["selectedRecord"]["subjectLabel"] == "price-dynamics"
    assert panel["selectedRecord"]["module3Entry"]["objectType"] == "WIDGET"
    assert panel["notes"]["oldNewValuesVisible"] is True
    assert panel["notes"]["businessPayloadLogged"] is False


def test_module3_audit_log_entry_maps_required_actions_and_objects():
    entry = module3_audit_log_entry(
        {
            "id": "audit-1",
            "createdAt": "2026-06-30T12:00:00",
            "actorUserId": "actor-1",
            "actor": "platform-admin",
            "actionType": "module_access_changed",
            "moduleCode": "MODULE_01_MATERIAL_HUB",
            "subjectLabel": "База материалов",
            "oldValue": {"allowed": True},
            "newValue": {"allowed": False},
            "reason": "Массовое назначение доступа",
        }
    )

    assert entry == {
        "id": "audit-1",
        "timestamp": "2026-06-30T12:00:00",
        "actorId": "actor-1",
        "actorName": "platform-admin",
        "action": "Изменение доступа по типу пользователя",
        "objectType": "ACCESS",
        "objectId": "MODULE_01_MATERIAL_HUB",
        "objectName": "База материалов",
        "details": "Массовое назначение доступа; Старое значение: {'allowed': True}; Новое значение: {'allowed': False}",
    }


def test_active_permissions_are_role_matrix_based_and_code_first():
    actor = _user(UserRole.ADMIN)
    permissions = active_permissions_for_user(actor)

    module_codes = {permission["moduleCode"] for permission in permissions}
    assert "MODULE_03_USERS_ROLES" in module_codes
    assert "MODULE_14_PRICE_HISTORY" not in module_codes
    assert all("moduleNumber" not in permission for permission in permissions)


def test_role_group_panel_summary_exposes_cards_without_becoming_registry_debug():
    user = _user_with_assignment("SUPPLIER")
    company = _company_workspace()
    member = _workspace_member(user, company, "SUPPLIER")
    user.workspace_members = [member]
    company.members = [member]
    roles = [
        {
            "roleCode": "SUPPLIER",
            "title": "Поставщик",
            "description": "Работа с прайсами и заявками.",
            "isSystem": True,
            "isAssignable": True,
        }
    ]

    panel = role_group_panel_summary(
        roles,
        users=[user],
        workspaces=[company],
        recent_history=[],
        admin_scope={"canSeeSystemSettings": False, "canSeeSystemCriticalModules": False},
    )

    role = panel["selectedRole"]
    assert role["title"] == "Поставщик"
    assert role["memberCount"] == 1
    assert role["modules"]
    assert all("moduleCode" in item for item in role["modules"])
    assert "technicalDetails" in role
    assert panel["technicalDetailsVisible"] is False
    assert panel["groups"][0]["title"] == "Системные роли"


def test_workspace_panel_summary_exposes_workspace_cards_without_dashboard_layout_editor():
    user = _user_with_assignment("SUPPLIER")
    company = _company_workspace()
    member = _workspace_member(user, company, "SUPPLIER")
    user.workspace_members = [member]
    company.members = [member]

    panel = workspace_panel_summary([company], recent_history=[])

    workspace = panel["selectedWorkspace"]
    assert panel["summary"]["total"] == 1
    assert panel["summary"]["companies"] == 1
    assert workspace["title"] == company.title
    assert workspace["linkedUsers"][0]["email"] == user.email
    assert workspace["linkedCompanies"][0]["title"] == company.title
    assert panel["notes"]["dashboardLayoutEditor"] is False
    assert panel["notes"]["technicalDashboardPresetsHidden"] is True


def test_settings_panel_separates_regular_settings_from_debug_zones():
    regular = settings_panel_summary({"actorRoleCodes": ["PLATFORM_ADMIN"]})
    super_admin = settings_panel_summary({"actorRoleCodes": ["SUPER_ADMIN"]})

    assert regular["superAdminMode"]["enabled"] is False
    assert super_admin["superAdminMode"]["enabled"] is True
    assert regular["normalSettings"]
    assert regular["dangerZone"]["requiresConfirmation"] is True
    assert regular["dangerZone"]["confirmationText"] == "DISABLE_USER"
    assert regular["notes"]["registryDiagnosticsHiddenForRegularAdmin"] is True
    assert regular["notes"]["widgetDiagnosticsHiddenForRegularAdmin"] is True
    assert regular["notes"]["legacyAliasesHiddenForRegularAdmin"] is True
    assert regular["notes"]["uiStatesHiddenForRegularAdmin"] is True
    assert regular["notes"]["moduleLifecycleDiagnosticsHiddenForRegularAdmin"] is True
    assert regular["notes"]["widgetLifecycleDiagnosticsHiddenForRegularAdmin"] is True

    diagnostic_titles = {item["title"] for item in super_admin["developerDiagnostics"]}
    assert {
        "Registry diagnostics",
        "Widget diagnostics",
        "Legacy aliases",
        "UI states",
        "Module lifecycle diagnostics",
        "Widget lifecycle diagnostics",
    }.issubset(diagnostic_titles)


def test_module3_quick_actions_are_configured_for_shell_navigation():
    actions = module3_quick_actions(admin_scope={"isCompanyAdminMode": False}, detail_mode=False)
    labels = [action["label"] for action in actions]

    assert labels == [
        "Найти пользователя",
        "Открыть заблокированных",
        "Проверить доступ",
        "История изменений",
        "Пользователи без компании",
        "Пользователи без типа",
        "Системные пользователи",
        "Матрица доступов",
        "Экспортировать список пользователей",
    ]

    for action in actions:
        assert action["id"]
        assert action["quickActionCode"].startswith("MODULE_03_")
        assert action["sourceModuleCode"] == "MODULE_03_USERS_ROLES"
        assert action["permissionCode"]
        assert action["featureCode"]
        assert action["actionCode"]
        assert action["maxSurface"] == "BOTH"
        assert action["visible"] is True
        assert action["actionType"] == "navigate"
        assert str(action["target"]).startswith("#")

    assert len(actions) == 9
    assert actions[-1]["id"] == "export-users"
    assert actions[-1]["enabled"] is False
    assert actions[-1]["disabledReason"] == "Экспорт будет доступен после подключения сервиса экспорта."

    detail_actions = {
        action["id"]: action
        for action in module3_quick_actions(admin_scope={"isCompanyAdminMode": False}, detail_mode=True)
    }
    assert detail_actions["check-access"]["target"] == "#access-matrix-detail"
    assert detail_actions["access-matrix"]["target"] == "#access-matrix-detail"

    company_actions = module3_quick_actions(admin_scope={"isCompanyAdminMode": True}, detail_mode=False)
    company_labels = {action["label"] for action in company_actions}
    assert "Найти пользователя" in company_labels
    assert "Открыть заблокированных" in company_labels
    assert "Проверить доступ" in company_labels
    assert "История изменений" in company_labels
    assert "Матрица доступов" in company_labels
    assert "Экспортировать список пользователей" in company_labels
    assert "Пользователи без компании" not in company_labels
    assert "Пользователи без типа" not in company_labels
    assert "Системные пользователи" not in company_labels


def test_module3_quick_action_settings_view_model_supports_user_preferences_and_limits():
    settings = module3_quick_action_settings(
        admin_scope={"isCompanyAdminMode": False, "userId": "admin-user"},
        detail_mode=False,
    )

    assert settings["title"] == "Настроить быстрые действия"
    assert settings["sourceModuleCode"] == "MODULE_03_USERS_ROLES"
    assert settings["maxModuleActions"] == 9
    assert settings["maxDashboardCardActions"] == 3
    assert settings["storageLayer"] == "UserDashboardLayout.layout_settings.moduleQuickActions"
    assert settings["localStorageKey"] == "atom:module3:quickActionSettings:v1"
    assert len(settings["actions"]) == 9
    assert len(settings["preferences"]) == 9
    assert settings["preferences"][0]["userId"] == "admin-user"
    assert settings["preferences"][0]["sourceModuleCode"] == "MODULE_03_USERS_ROLES"

    export_action = next(
        action
        for action in settings["actions"]
        if action["quickActionCode"] == "MODULE_03_EXPORT_USERS"
    )
    assert export_action["canPin"] is False
    assert export_action["isModulePinnedByDefault"] is False
    assert export_action["unavailableReason"] == "Экспорт будет доступен после подключения сервиса экспорта."
    assert {action["sourceLabel"] for action in settings["actions"]} >= {
        "Пользователи",
        "Доступы",
        "Журнал изменений",
        "Системные пользователи",
    }


def test_module3_overview_widgets_summarize_user_types_registry_and_system_users():
    company = _company_workspace()
    supplier = _company_workspace()
    supplier.workspace_type = "SUPPLIER"
    supplier.status = "PENDING_REVIEW"
    supplier.is_active = True
    blocked_company = _company_workspace()
    blocked_company.status = "BLOCKED"
    blocked_company.is_active = False

    customer = _user(UserRole.CUSTOMER)
    customer.status = UserStatus.ACTIVE
    specialist = _user(UserRole.CONTRACTOR)
    specialist.status = UserStatus.BLOCKED
    platform_admin = _user(UserRole.ADMIN)
    platform_admin.email = "platform-admin@example.com"
    super_admin = _user_with_assignment("SUPER_ADMIN")
    super_admin.name = "super-admin"
    moderator = _user_with_assignment("MODERATOR")
    moderator.name = "moderator"

    widgets = user_type_summary_widgets(
        [customer, specialist, platform_admin, super_admin, moderator],
        [company, supplier, blocked_company],
    )
    by_code = {widget["userTypeCode"]: widget for widget in widgets}

    assert list(by_code) == ["COMPANY", "SUPPLIER", "CUSTOMER", "SPECIALIST"]
    assert by_code["COMPANY"]["total"] == 3
    assert by_code["COMPANY"]["active"] == 1
    assert by_code["COMPANY"]["blocked"] == 1
    assert by_code["COMPANY"]["onModeration"] == 1
    assert by_code["SUPPLIER"]["total"] == 1
    assert by_code["SUPPLIER"]["onModeration"] == 1
    assert by_code["CUSTOMER"]["active"] >= 1
    assert by_code["SPECIALIST"]["blocked"] == 1

    module_summary = module_registry_overview_summary()
    widget_summary = widget_registry_overview_summary()
    assert module_summary["total"] >= module_summary["active"]
    assert module_summary["inDevelopment"] >= 0
    assert widget_summary["total"] >= widget_summary["active"]
    assert widget_summary["inDevelopment"] >= 0

    system_cards = system_user_cards([platform_admin, super_admin, moderator], recent_history=[])
    system_logins = {card["login"] for card in system_cards}
    assert system_logins == {"platform-admin", "super-admin", "moderator"}
    assert all("roleTitle" in card for card in system_cards)


def test_user_directory_rows_expose_search_filter_sort_and_card_links():
    customer = _user(UserRole.CUSTOMER)
    customer.status = UserStatus.ACTIVE
    customer.name = "Иван Петров"
    customer.phone = "+7 900 000-00-00"
    company = _company_workspace()
    member = _workspace_member(customer, company, "CUSTOMER")
    customer.workspace_members = [member]
    company.members = [member]

    rows = user_directory_rows([customer], [company])
    user_row = next(row for row in rows if row["subjectKind"] == "user")
    company_row = next(row for row in rows if row["subjectKind"] == "company")

    assert user_row["typeCode"] == "CUSTOMER"
    assert user_row["displayName"] == "Иван Петров"
    assert user_row["companyName"] == company.title
    assert user_row["contacts"] == [customer.email, customer.phone]
    assert user_row["cardUrl"] == f"/api/v1/admin/users-roles/view/users/{customer.id}"
    assert "иван петров" in user_row["searchBlob"]
    assert user_row["moduleAccess"] in {"has_modules", "no_modules"}
    assert company_row["typeCode"] == "COMPANY"
    assert company_row["cardUrl"] == f"/api/v1/admin/users-roles/view/users/{customer.id}"

    chips = user_directory_summary_chips(rows)
    assert chips[0] == {"typeCode": "ALL", "label": "Все", "count": 2}
    assert next(chip for chip in chips if chip["typeCode"] == "COMPANY")["count"] == 1
    assert next(chip for chip in chips if chip["typeCode"] == "CUSTOMER")["count"] == 1

    filters = user_directory_filter_options(rows)
    assert any(option["value"] == "CUSTOMER" for option in filters["types"])
    assert any(option["value"] == "active" for option in filters["statuses"])
    assert {option["value"] for option in filters["moduleAccess"]} == {"has_modules", "no_modules"}


def test_user_profile_card_summary_exposes_company_roles_and_effective_access():
    company_admin = _user(UserRole.CUSTOMER)
    company_admin.name = "Сидоров Иван"
    company_admin.phone = "+7 861 111-22-33"
    company = _company_workspace()
    company.name = "ООО СтройПроект Юг"
    company.workspace_type = "CONTRACTOR"
    company.organization_id = "2312345678"
    company.settings = {
        "inn": "2312345678",
        "kpp": "231201001",
        "ogrn": "1232300045678",
        "legalAddress": "Краснодар, ул. Красная, д. 123",
        "region": "Краснодарский край",
        "city": "Краснодар",
        "assignedManager": "Сидоров И. И.",
    }
    engineer = _user(UserRole.CONTRACTOR)
    engineer.name = "Петрова Елена"
    buyer = _user(UserRole.SUPPLIER)
    buyer.name = "Кузнецов Андрей"
    admin_member = _workspace_member(company_admin, company, COMPANY_ADMIN_ROLE_CODE)
    engineer_member = _workspace_member(engineer, company, "ENGINEER_DESIGNER")
    buyer_member = _workspace_member(buyer, company, "PROCUREMENT_MANAGER")
    company_admin.workspace_members = [admin_member]
    company.members = [admin_member, engineer_member, buyer_member]
    company.module_access = [
        ModuleAccess(
            workspace_id=company.id,
            module_code="MODULE_11_ANALYTICS",
            canonical_module_code="MODULE_11_ANALYTICS",
            access_level="NO_ACCESS",
            access_scope="GLOBAL",
            status="ACTIVE",
        )
    ]

    user_data = user_summary(company_admin, include_permissions=True)
    apply_company_context_to_user_summary(user_data, [company])
    matrix = access_matrix_for_subject(
        user_data,
        workspaces=[company],
        roles=[],
        permissions=active_permissions_for_user(company_admin),
    )
    card = user_profile_card_summary(
        company_admin,
        user_data=user_data,
        workspaces=[company],
        access_matrix=matrix,
        history=[],
    )

    assert card["header"]["title"] == "ООО СтройПроект Юг"
    assert card["header"]["assignedManager"] == "Сидоров И. И."
    assert card["header"]["blockLabel"] == "Без блокировки"
    assert [action["label"] for action in card["header"]["actions"]] == [
        "Редактировать",
        "Заблокировать",
        "Назначить доступ",
    ]
    assert {field["label"]: field["value"] for field in card["companyInfo"]}["ИНН"] == "2312345678"
    assert {field["label"]: field["value"] for field in card["companyInfo"]}["Юридический адрес"] == "Краснодар, ул. Красная, д. 123"
    role_summary = {item["label"]: item["value"] for item in card["employeeRoles"]["summary"]}
    assert role_summary["Сотрудники"] == 3
    assert role_summary["Руководители"] == 1
    assert role_summary["Инженеры"] == 1
    assert role_summary["Менеджеры"] == 1
    assert {item["roleTitle"] for item in card["employeeRoles"]["recent"]} >= {"Администратор компании", "Инженер-проектировщик"}

    module_row = next(row for row in card["moduleAccessRows"] if row["moduleCode"] == "MODULE_11_ANALYTICS")
    assert module_row["subjectType"] == "USER"
    assert module_row["source"] in {"TYPE_TEMPLATE", "USER_OVERRIDE", "SYSTEM"}
    assert module_row["sourceLabel"] in {"По типу пользователя", "Индивидуально переопределен", "Системный"}
    analytics_widgets = next(group for group in card["widgetAccessGroups"] if group["moduleCode"] == "MODULE_11_ANALYTICS")
    assert analytics_widgets["moduleAllowed"] is False
    assert analytics_widgets["disabledReason"] == "Недоступно: виджет закрыт вместе с модулем"
    assert card["effectiveAccess"]["sources"] == [
        {"source": "TYPE_TEMPLATE", "label": "По типу пользователя"},
        {"source": "USER_OVERRIDE", "label": "Индивидуально переопределен"},
        {"source": "SYSTEM", "label": "Системный"},
    ]


def test_admin_users_roles_view_route_is_registered():
    paths = {route.path for route in admin_users_roles_router.routes}

    assert "/admin/users-roles/view" in paths
    assert "/admin/users-roles/view/users/{user_id}" in paths
    assert "/admin/users-roles/view/access-matrix" in paths
    assert "/admin/users-roles/view/users/{user_id}/company-admin" in paths
    assert "/admin/users-roles/view/users/{user_id}/company-admin/revoke" in paths


def test_legacy_module3_view_route_redirects_to_api_prefix():
    client = TestClient(app)

    response = client.get("/admin/users-roles/view/users/user-1?tab=access", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/v1/admin/users-roles/view/users/user-1?tab=access"


def test_admin_users_roles_template_has_sprint8_responsive_contracts():
    template = open("templates/admin_users_roles.html", encoding="utf-8").read()

    assert "width: 100%" in template
    assert "max-width: none" in template
    assert "grid-template-columns: clamp(248px, 15.5vw, 296px) minmax(0, 1fr)" in template
    assert "min-height: calc(100vh - 64px)" in template
    assert "top: 64px" in template
    assert ".control-main" in template
    assert "min-width: 0" in template
    assert "padding: 18px 28px 32px" in template
    assert ".table-wrap" in template
    assert "max-width: 100%" in template
    assert "overflow-x: auto" in template
    assert ".entity-table th:first-child" in template
    assert ".access-matrix-table th:first-child" in template
    assert "position: sticky" in template
    assert ".overview-dashboard-grid" in template
    assert ".profile-hero-layout" in template
    assert ".profile-meta-row" in template
    assert "data-active-tab" in template
    assert "data-module3-tab-link" in template
    assert "@media (max-width: 1440px)" in template
    assert "@media (max-width: 1366px)" in template
    assert ".ui-state.loading" in template
    assert ".ui-state.error" in template


def test_admin_users_roles_template_contains_module8_bridge_copy():
    template = open("templates/admin_users_roles.html", encoding="utf-8").read()
    nav = template.split('<nav class="module3-nav"', 1)[1].split("</nav>", 1)[0]
    overview = template.split('<section class="command-hero" id="overview">', 1)[1].split(
        '<section class="panel" id="settings"',
        1,
    )[0]
    users_section = template.split('<section class="panel" id="users">', 1)[1].split(
        '<section class="detail">',
        1,
    )[0]

    assert "Кабинеты и контекст" in template
    assert 'hidden data-system-section="module8-context-diagnostics"' in template
    assert "MODULE_08_PARTNER_PORTAL" in template
    assert "Module №3 их не хранит" in template
    assert "Source of truth остается в MODULE_08_PARTNER_PORTAL" in template
    assert "Список кабинетов пользователя" in template
    assert "Настройки видимости placeholder" in template
    assert "Настройки предложений placeholder" in template
    assert "Рекомендованные виджеты" in template
    assert "Рекомендованные быстрые действия" in template
    assert "Виджеты и доступ" in template
    assert "WidgetRegistry управляет metadata и доступом" in template
    assert "Payload формирует модуль-владелец данных" in template
    assert "UserDashboardLayout:" in template
    assert "Настройки конкретного экземпляра виджета" in template
    assert "WidgetSettingsSchema" in template
    assert "Модуль-владелец еще не отдал schema" in template
    assert "Быстрые действия" in template
    assert 'id="quick-actions" hidden data-system-section="quick-action-diagnostics"' in template
    assert "savedConfigRef:" in template
    assert "requirePermission(" in template
    assert "Обзор модуля" in overview
    assert 'data-user-type="{{ widget.userTypeCode }}"' in overview
    assert "Компании" in overview
    assert "Поставщики" in overview
    assert "Заказчики" in overview
    assert "Специалисты" in overview
    assert "Активные" in overview
    assert "Заблокированные" in overview
    assert "На модерации" in overview
    assert "История изменений" in overview
    assert "Дата и время" in overview
    assert "Кто изменил" in overview
    assert "Действие" in overview
    assert "Объект" in overview
    assert "Детали" in overview
    assert "{{ item.timestamp }}" in overview
    assert "{{ item.actorName }}" in overview
    assert "{{ item.action }}" in overview
    assert "{{ item.objectName or item.objectTypeCode }}" in overview
    assert "{{ item.detailsText or item.result }}" in overview
    assert "Модули в системе" in overview
    assert "Виджеты в системе" in overview
    assert "Системные пользователи" in overview
    assert "platform-admin" in overview
    assert "super-admin" in overview
    assert "moderator" in overview
    assert "Последняя активность" in overview
    assert "MODULE_03_USERS_ROLES · unified admin panel" not in overview
    assert "Роли, доступы и кабинетный контекст" not in overview
    assert "Единая системная панель управления" not in overview
    assert "User</span>" not in overview
    assert "Cabinet Context" not in overview
    assert "QuickAction Permission" not in overview
    assert "Состояния и причины недоступности" not in overview
    assert "пользователи без роли" not in overview.lower()
    assert "компании на проверке" not in overview.lower()
    assert "сотрудники компаний" not in overview.lower()
    assert "администраторы компаний" not in overview.lower()
    assert "конфликты доступа" not in overview.lower()
    assert "тарифные ограничения" not in overview.lower()
    assert "Последние изменения" not in overview
    assert "что требует внимания" not in overview.lower()
    assert "Новые модули и виджеты требуют распределения" not in overview
    assert "Пользователи — превью рабочей зоны" not in overview
    assert "Быстрые переходы администратора" not in overview
    assert "Быстрые действия" in template
    assert 'data-module3-quick-actions' in template
    assert template.index('data-module3-quick-actions') < template.index('<section class="command-hero" id="overview">')
    assert 'data-action-id="{{ action.id }}"' in template
    assert 'data-quick-action-code="{{ action.quickActionCode }}"' in template
    assert 'data-source-module-code="{{ action.sourceModuleCode }}"' in template
    assert 'data-action-code="{{ action.actionCode }}"' in template
    assert 'data-max-surface="{{ action.maxSurface }}"' in template
    assert 'data-permission-code="{{ action.permissionCode or \'\' }}"' in template
    assert 'data-feature-code="{{ action.featureCode or \'\' }}"' in template
    assert 'data-quick-action-storage-key="{{ overview.moduleQuickActionSettings.localStorageKey }}"' in template
    assert 'data-max-module-actions="{{ overview.moduleQuickActionSettings.maxModuleActions }}"' in template
    assert 'data-max-card-actions="{{ overview.moduleQuickActionSettings.maxDashboardCardActions }}"' in template
    assert "Настроить быстрые действия" in template
    assert "data-module3-quick-actions-configure" in template
    assert "data-module3-quick-action-modal" in template
    assert "data-module3-quick-action-module-toggle" in template
    assert "data-module3-quick-action-card-toggle" in template
    assert "data-module3-quick-action-order" in template
    assert "Внутри модуля можно закрепить не больше 9 быстрых действий." in template
    assert "На карточке модуля можно вывести не больше 3 быстрых действий." in template
    assert "UserDashboardLayout.layout_settings.moduleQuickActions" in template
    assert "window.localStorage.setItem(storageKey" in template
    assert 'data-without-company="{{ row.isWithoutCompany }}"' in template
    assert 'data-without-type="{{ row.isWithoutType }}"' in template
    assert 'data-system-user="{{ row.isSystemUser }}"' in template
    assert 'quickActionFilter = "without_company"' in template
    assert 'quickActionFilter = "without_type"' in template
    assert 'params.get("focus") === "search"' in template
    assert 'id="system-users"' in template
    assert "МОДУЛЬ №3" in nav
    assert "Обзор модуля" in nav
    assert "Пользователи" in nav
    assert "Доступы" in nav
    assert nav.count("<a ") == 3
    assert "Роли и группы" not in nav
    assert "Рабочие области" not in nav
    assert "Журнал изменений" not in nav
    assert "Настройки" not in nav
    assert 'id="roles-permissions" aria-labelledby="roles-groups-title" hidden data-system-section="roles-groups-preserved"' in template
    assert "Список ролей" in template
    assert "Список групп" in template
    assert "Карточка роли" in template
    assert "Карточка группы" in template
    assert "Участники" in template
    assert "Связанные модули / виджеты" in template
    assert "История изменений роли / группы" in template
    assert "Технические детали" in template
    assert "Коды доступны в tooltip" in template
    assert 'id="workspaces" aria-labelledby="workspaces-title" hidden data-system-section="workspace-preserved"' in template
    assert "Список рабочих областей" in template
    assert "Карточка workspace" in template
    assert "Связанные пользователи" in template
    assert "Связанные компании" in template
    assert "История изменений workspace" in template
    assert "Dashboard layout здесь не редактируется" in template
    assert "Технические Dashboard presets и layout registry скрыты" in template
    assert 'id="audit-log"' in template
    assert "Таблица изменений" in template
    assert "Фильтры журнала изменений" in template
    assert "Поиск по пользователю, компании, модулю или действию" in template
    assert "Detail drawer записи" in template
    assert "Старое значение" in template
    assert "Новое значение" in template
    assert "Кто изменил" in template
    assert "Когда изменил" in template
    assert "Для кого изменил" in template
    assert "Module3AuditLogEntry: id, timestamp, actorId, actorName, action, objectType, objectId, objectName, details" in template
    assert "actorId:" in template
    assert "objectId:" in template
    assert "Детали:" in template
    assert "Реестр модулей" not in nav
    assert "Виджеты и доступ" not in nav
    assert "Быстрые действия" not in nav
    assert "Макеты Dashboard" not in nav
    assert "Кабинеты и контекст" not in nav
    assert "Предпросмотр роли" not in nav
    assert "Системные разделы" in template
    assert "Registry / developer-only" in template
    assert "Обычные настройки Module №3" in template
    assert "Super Admin mode" in template
    assert "developer-only diagnostics" in template
    assert "Danger zone" in template
    assert "подтверждение опасных действий" in template
    assert "Registry diagnostics" in template
    assert "Widget diagnostics" in template
    assert "Legacy aliases" in template
    assert "UI states" in template
    assert "Module lifecycle diagnostics" in template
    assert "Widget lifecycle diagnostics" in template
    assert "Главный центр управления физлицами, компаниями, сотрудниками компаний, группами, доступами и историей" in users_section
    assert "Ручное создание пользователя здесь не предусмотрено" in users_section
    assert "Физические лица" in users_section
    assert "Компании" in users_section
    assert "Сотрудники компаний" in users_section
    assert "Группы" in users_section
    assert "Доступы" in users_section
    assert "История" in users_section
    assert "Summary chips по типам пользователей" in users_section
    assert "Все" in users_section
    assert "Поставщики" in users_section
    assert "Заказчики" in users_section
    assert "Специалисты" in users_section
    assert "Поиск по ФИО, названию компании, email, телефону, ИНН или ID" in users_section
    assert "Фильтр по типу пользователя" in users_section
    assert "Фильтр по статусу" in users_section
    assert "Фильтр по блокировке" in users_section
    assert "Фильтр по активности" in users_section
    assert "Фильтр по региону" in users_section
    assert "Фильтр по доступу к модулю" in users_section
    assert "Сортировка пользователей" in users_section
    assert "Единый список пользователей" in users_section
    assert "Наименование / ФИО" in users_section
    assert "Компания / Организация" in users_section
    assert "Последняя активность" in users_section
    assert "data-user-page-summary" in users_section
    assert "data-user-page-prev" in users_section
    assert "data-user-page-next" in users_section
    assert "Если модуль не выбран, связанные виджеты выбрать нельзя" in users_section
    assert "Рабочая матрица доступа: строки — модули и вложенные виджеты" in users_section
    assert "Заказчики" in users_section
    assert "Поставщики" in users_section
    assert "Строительные компании" in users_section
    assert "Самостоятельные инженеры" in users_section
    assert "Поиск по модулю / виджету" in users_section
    assert "Статус модуля" in users_section
    assert "Тип пользователя" in users_section
    assert "Развернуть все" in users_section
    assert "Свернуть все" in users_section
    assert "Сохранить изменения" in users_section
    assert "Сбросить" in users_section
    assert "нет изменений; есть несохраненные изменения; сохранение; ошибка сохранения; успешно сохранено" in users_section
    assert 'data-access-matrix-checkbox' in template
    assert 'data-access-matrix-payload' in template
    assert 'data-system-disabled' in template
    assert "Виджет недоступен, потому что модуль выключен" in template
    assert "if (!moduleCheckbox.checked)" in template
    assert "JSON.stringify(buildPayload())" in template
    assert "Доступы к модулям и виджетам" in template
    assert "Пользователь" in template
    assert "Компания" in template
    assert "Сотрудник компании" in template
    assert "Группа" in template
    assert "Роль" in template
    assert "Виджеты выбранного модуля" in template
    assert "Причины ограничения" in template
    assert "Закрыто администратором платформы" in template
    assert "Закрыто администратором компании" in template
    assert "Недоступно по тарифу" in template
    assert "Недоступно: системное ограничение" in template
    assert "Недоступно: модуль отключен" in template
    assert "Недоступно: модуль еще не активен" in template
    assert "Недоступно: модуль в подготовке" in template
    assert "Недоступно: виджет отключен" in template
    assert "Недоступно: виджет закрыт вместе с модулем" in template
    assert "Недоступно: пользователь заблокирован" in template
    assert "Недоступно: компания заблокирована" in template
    assert "ручной запрет ≠ тарифное ограничение" in template
    assert "Тарифное ограничение не равно ручному запрету администратора" in template
    assert "Future monetization fields" in template
    assert "planCode" in template
    assert "subscriptionCode" in template
    assert "billingFeatureCode" in template
    assert "billingRestrictionReason" in template
    assert "tariffLevel" in template
    assert "tariffExpiresAt" in template
    assert "isBillingRestricted" in template
    assert "Оплата, подписки, тарифные страницы и billing не реализуются в Module №3" in template
    assert "Открыть модуль" not in users_section
    assert "наследуется" not in template.lower()
    assert "Добавить пользователя" not in users_section
    assert "Создать пользователя" not in users_section
    assert "Карточка пользователя" in template
    assert "Карточка компании" in template
    assert "Карточка сотрудника компании" in template
    assert "Основной контакт" in template
    assert "Назначенный менеджер" in template
    assert 'data-profile-action="{{ action.id }}"' in template
    assert "{{ action.label }}" in template
    assert "Заблокировать" in template
    assert "Разблокировать" in template
    assert "Назначить доступ" in template
    assert "Сотрудники и роли" in template
    assert "Название компании" in template
    assert "Тип компании" in template
    assert "Юридический адрес" in template
    assert "Индивидуальный доступ" in template
    assert "Источник доступа: По типу пользователя, Индивидуально переопределен или Системный" in template
    assert "Включить модуль" in template
    assert "Выключить модуль" in template
    assert "Если модуль не разрешен, его виджеты нельзя включить" in template
    assert "Назначить группу" in template
    assert "Отвязать от компании" in template
    assert "Назначить администратора" in template
    assert "Назначить администратора компании" in template
    assert "Снять администратора компании" in template
    assert 'action="/api/v1/admin/users-roles/view/users/{{ detail.user.id }}/company-admin"' in template
    assert 'action="/api/v1/admin/users-roles/view/users/{{ detail.user.id }}/company-admin/revoke"' in template
    assert "не может открыть сотруднику модуль или виджет, закрытый компании платформой" in template
    assert "тарифные ограничения: внутри карточки" in template
    assert "кто, когда, что изменил" in template
    assert "Фильтр истории по автору" in template
    assert "Фильтр истории по дате" in template
    assert "Фильтр истории по действию" in template
    assert "Фильтр истории по типу объекта" in template
    assert "Фильтр истории по модулю" in template
    assert "Фильтр истории по виджету" in template
    assert "Срез по объектам" in template
    assert "Модули и виджеты" in template
    assert "Старое значение:" in template
    assert "Новое значение:" in template
    assert "Причина:" in template

    state_text = " ".join(state["description"] for state in ADMIN_UI_STATE_LEGEND)
    assert "Виджет недоступен: нет прав на данные модуля" in state_text
    assert "Это действие запланировано, но еще не активно" in state_text
    assert "Модуль объединен с другим модулем" in state_text


def test_module3_final_visual_unification_contract():
    template = open("templates/admin_users_roles.html", encoding="utf-8").read()
    nav = template.split('<nav class="module3-nav"', 1)[1].split("</nav>", 1)[0]
    overview = template.split('<section class="command-hero" id="overview">', 1)[1].split(
        '<section class="panel" id="settings"',
        1,
    )[0]

    assert template.count('<nav class="module3-nav"') == 1
    assert "module3-shell" in template
    assert "data-module3-shell" in template
    assert "data-module3-quick-actions" in template
    assert "data-module3-sidebar" in template
    assert "data-module3-content" in template
    assert "control-shell" in template
    assert "control-main" in template
    assert ".system-card" in template
    assert ".bridge-card" in template
    assert ".role-card" in template
    assert ".mini-card" in template
    assert ".entity-table tbody tr:hover" in template
    assert ".access-matrix-table tbody tr:hover" in template
    assert ".empty" in template

    for forbidden in (
        "Workspace:",
        "Регион:",
        "SUPER_ADMIN",
        "AuditLog ·",
        "QuickAction Permission",
        "Состояния и причины недоступности",
        "Кабинеты и контекст",
        "Виджеты и доступ",
        "Макеты Dashboard",
        "Предпросмотр роли",
        "Роли и группы",
        "Рабочие области",
    ):
        assert forbidden not in nav
        assert forbidden not in overview

    assert "Журнал изменений" not in nav
    assert "Настройки" not in nav
    assert "Обзор модуля" in nav
    assert "Пользователи" in nav
    assert "Доступы" in nav
    assert nav.count("<a ") == 3
    assert 'hidden data-system-section="roles-groups-preserved"' in template
    assert 'hidden data-system-section="workspace-preserved"' in template
    assert "наследуется" not in template.lower()
    assert "атомная карта" not in template.lower()
    assert "орбита" not in template.lower()
    assert "Dashboard-клон" not in template
    assert 'id="quick-actions" hidden data-system-section="quick-action-diagnostics"' in template
    assert 'hidden data-system-section="module8-context-diagnostics"' in template


def test_module8_cabinet_admin_preview_exposes_context_placeholders():
    preview = get_module8_cabinet_admin_preview(
        {
            "id": "user-1",
            "activeRegionCode": "KRASNODAR_KRAI",
            "workspaces": [
                {
                    "workspaceId": "workspace-1",
                    "workspaceTitle": "ООО СтройДом",
                    "workspaceType": "CONTRACTOR",
                    "roleCode": "CONTRACTOR",
                    "status": "ACTIVE",
                }
            ],
        },
        access_context={
            "userId": "user-1",
            "workspaceId": "workspace-1",
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedWidgetCodes": ["TEST_WIDGET"],
            "allowedQuickActionCodes": ["TEST_ACTION"],
        },
    ).to_dict()

    assert preview["sourceModuleCode"] == "MODULE_08_PARTNER_PORTAL"
    assert preview["activeCabinetType"] == "CONSTRUCTION_COMPANY"
    assert preview["activeBusinessRole"] == "CONTRACTOR"
    assert preview["visibilitySettingsPreview"]["sourceOfTruth"] == "MODULE_08_PARTNER_PORTAL"
    assert preview["offerSettingsPreview"]["sourceOfTruth"] == "MODULE_08_PARTNER_PORTAL"
    assert preview["dashboardContextPreview"]["recommendedWidgetCodes"] == ["TEST_WIDGET"]
    assert preview["dashboardContextPreview"]["recommendedQuickActionCodes"] == ["TEST_ACTION"]


def test_widget_access_rows_are_registry_metadata_without_payload():
    rows = widget_access_rows_for_user(
        {"id": "user-1", "roleCodes": ["PLATFORM_ADMIN"]},
        access_context={
            "userId": "user-1",
            "roleCodes": ["PLATFORM_ADMIN"],
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedFeatureCodes": ["PRICE_DYNAMICS"],
            "allowedWidgetCodes": ["materials-kpi", "price-dynamics"],
        },
        module8_preview={
            "dashboardContextPreview": {
                "recommendedWidgetCodes": ["price-dynamics"],
            }
        },
    )

    assert rows
    assert all("widgetCode" in row for row in rows)
    assert all("sourceModuleCode" in row for row in rows)
    assert all("businessPayload" not in row for row in rows)

    price_row = next(row for row in rows if row["widgetCode"] == "price-dynamics")
    assert price_row["sourceModuleCode"] == "MODULE_11_ANALYTICS"
    assert price_row["featureCode"] == "PRICE_DYNAMICS"
    assert price_row["legacyModuleCode"] == "MODULE_14_PRICE_HISTORY"
    assert price_row["module8Recommendation"] == "рекомендован"
    assert "UserDashboardLayout" not in price_row["unavailableReason"]
    assert price_row["layoutRelation"]
    assert price_row["settingsPreview"]["schemaSourceModuleCode"] == "MODULE_11_ANALYTICS"
    assert price_row["settingsPreview"]["featureCode"] == "PRICE_DYNAMICS"
    assert price_row["settingsPreview"]["storageLayer"] == "UserDashboardLayout.widgets[].userSettings"
    assert price_row["settingsPreview"]["auditEventType"] == "user_dashboard_layout_changed"
    assert "businessPayload" not in price_row["settingsPreview"]
    assert price_row["stateCode"] == "LEGACY_MERGED"
    assert "canonical moduleCode" in price_row["stateDescription"]

    setting_codes = {field["settingCode"] for field in price_row["settingsPreview"]["fields"]}
    assert {"period", "material", "region", "chart_type"}.issubset(setting_codes)

    future_row = next(row for row in rows if row["widgetCode"] == "digital-house-status")
    assert future_row["stateCode"] == "FUTURE_FEATURE"
    assert future_row["isAllowed"] is False


def test_quick_action_rows_expose_safe_preference_instance_without_business_result():
    rows = quick_action_rows_for_user(
        {"id": "user-1", "roleCodes": ["PLATFORM_ADMIN"]},
        access_context={
            "userId": "user-1",
            "workspaceId": "workspace-1",
            "roleCodes": ["PLATFORM_ADMIN"],
            "activeRegionCode": "KRASNODAR_KRAI",
            "allowedQuickActionCodes": ["SOURCE_TASK_CREATE", "DASHBOARD_CONFIGURE"],
        },
        module8_preview={
            "activeCabinetId": "admin-cabinet",
            "activeCabinetType": "ADMIN",
            "dashboardContextPreview": {
                "recommendedQuickActionCodes": ["SOURCE_TASK_CREATE"],
            },
        },
    )

    source_task = next(row for row in rows if row["quickActionCode"] == "SOURCE_TASK_CREATE")

    assert source_task["sourceModuleCode"] == "MODULE_01_MATERIAL_HUB"
    assert source_task["actionCode"] == "CREATE"
    assert source_task["isAllowed"] is True
    assert source_task["preferencePreview"]["savedConfigRef"].startswith(
        "MODULE_01_MATERIAL_HUB:SOURCE_TASK_CREATE:"
    )
    assert source_task["preferencePreview"]["activeCabinetId"] == "admin-cabinet"
    assert source_task["preferencePreview"]["requiresPermissionOnRun"] is True
    assert source_task["preferencePreview"]["auditEventType"] == "quick_action_preference_changed"
    assert "businessResult" not in source_task["preferencePreview"]
    assert source_task["stateCode"] == "AVAILABLE"

    future_action = next(row for row in rows if row["quickActionCode"] == "CUSTOMER_OBJECT_CREATE")
    assert future_action["stateCode"] == "FUTURE_FEATURE"
    assert future_action["isAllowed"] is False
