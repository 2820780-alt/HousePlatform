from app.models import QuickActionRegistryItem
from pathlib import Path
from app.services.quick_action_registry import (
    QUICK_ACTION_REGISTRY_LAYER,
    build_quick_action_registry_item,
    filter_quick_action_registry_items_for_module,
    get_quick_action_registry_items_for_module,
    get_preview_quick_action_registry_items,
    get_quick_action_registry,
    get_quick_action_registry_item,
    quick_action_registry_item_to_dict,
)


ROOT = Path(__file__).resolve().parents[1]


SAMPLE_MODULE_QUICK_ACTIONS = [
    {
        "quickActionCode": "SAMPLE_OPEN_LIST",
        "sourceModuleCode": "MODULE_TEST_SAMPLE",
        "featureCode": "SAMPLE",
        "sectionCode": "LIST",
        "actionCode": "OPEN_LIST",
        "titleRu": "Открыть список",
        "descriptionRu": "Тестовое действие для проверки расширяемости quick actions.",
        "actionType": "navigate",
        "targetRoute": "/modules/sample/list",
        "requiredPermission": "sample.read",
        "isEnabledByDefault": False,
        "isAvailable": True,
        "maxSurface": "BOTH",
        "sortOrder": 10,
    },
    {
        "quickActionCode": "SAMPLE_ARCHIVED_ACTION",
        "sourceModuleCode": "MODULE_TEST_SAMPLE",
        "featureCode": "SAMPLE",
        "sectionCode": "LEGACY",
        "actionCode": "OPEN_ARCHIVED",
        "titleRu": "Архивное действие",
        "actionType": "navigate",
        "targetRoute": "/modules/sample/legacy",
        "requiredPermission": "sample.read",
        "isEnabledByDefault": False,
        "isAvailable": False,
        "status": "DISABLED",
        "maxSurface": "BOTH",
        "sortOrder": 20,
    },
]


def test_quick_action_registry_is_code_first_and_not_dashboard_hardcode():
    registry = get_quick_action_registry()

    assert registry
    assert all(item["registryLayer"] == QUICK_ACTION_REGISTRY_LAYER for item in registry)
    assert all("moduleNumber" not in item for item in registry)
    assert all("sourceModuleNumber" not in item for item in registry)
    assert all(item["sourceModuleCode"] for item in registry)
    assert all(item["quickActionCode"] for item in registry)
    assert all(item["actionCode"] for item in registry)
    assert all(item["actionType"] in {"navigate", "modal", "callback"} for item in registry)
    assert all(item["maxSurface"] in {"MODULE_BAR", "MODULE_CARD", "BOTH"} for item in registry)

    supplier_action = get_quick_action_registry_item("SUPPLIER_PRICE_UPLOAD")
    assert supplier_action is not None
    assert supplier_action.sourceModuleCode == "MODULE_01_MATERIAL_HUB"
    assert supplier_action.featureCode == "UPLOAD_SUPPLIER_FILE"
    assert supplier_action.actionCode == "OPEN_SUPPLIER_PRICE_UPLOAD"
    assert supplier_action.requiredActionCode == "VIEW"
    assert supplier_action.requiredAccessLevel == "VIEW"
    assert supplier_action.requiredScope == "LIMITED"
    assert supplier_action.targetRoute == "/api/v1/admin/material-hub/view"


def test_quick_action_layer_does_not_branch_by_module_number():
    files = [
        ROOT / "app/services/quick_action_registry.py",
        ROOT / "app/services/quick_action_permission.py",
        ROOT / "app/services/quick_action_preferences.py",
        ROOT / "app/services/user_module_quick_actions.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "if (moduleNumber" not in text
    assert "if moduleNumber" not in text
    assert "if module_number" not in text
    assert "sourceModuleNumber" not in text


def test_future_module_quick_actions_can_use_universal_surface_contract():
    item = build_quick_action_registry_item(SAMPLE_MODULE_QUICK_ACTIONS[0])
    payload = quick_action_registry_item_to_dict(SAMPLE_MODULE_QUICK_ACTIONS[0])

    assert item.quickActionCode == "SAMPLE_OPEN_LIST"
    assert item.sourceModuleCode == "MODULE_TEST_SAMPLE"
    assert item.featureCode == "SAMPLE"
    assert item.sectionCode == "LIST"
    assert item.actionCode == "OPEN_LIST"
    assert item.requiredPermission == "sample.read"
    assert item.requiredActionCode == "VIEW"
    assert item.requiredAccessLevel == "VIEW"
    assert item.requiredScope == "GLOBAL"
    assert item.targetRoute == "/modules/sample/list"
    assert item.maxSurface == "BOTH"
    assert payload["titleRu"] == "Открыть список"
    assert payload["sortOrder"] == 10
    assert "moduleNumber" not in payload
    assert "sourceModuleNumber" not in payload

    module_bar = filter_quick_action_registry_items_for_module(
        SAMPLE_MODULE_QUICK_ACTIONS,
        "MODULE_TEST_SAMPLE",
        surface="MODULE_BAR",
    )
    module_card = filter_quick_action_registry_items_for_module(
        SAMPLE_MODULE_QUICK_ACTIONS,
        "MODULE_TEST_SAMPLE",
        surface="MODULE_CARD",
    )
    inactive = filter_quick_action_registry_items_for_module(
        SAMPLE_MODULE_QUICK_ACTIONS,
        "MODULE_TEST_SAMPLE",
        surface="MODULE_CARD",
        include_inactive=True,
    )

    assert [action["quickActionCode"] for action in module_bar] == ["SAMPLE_OPEN_LIST"]
    assert [action["quickActionCode"] for action in module_card] == ["SAMPLE_OPEN_LIST"]
    assert [action["quickActionCode"] for action in inactive] == [
        "SAMPLE_OPEN_LIST",
        "SAMPLE_ARCHIVED_ACTION",
    ]
    assert get_quick_action_registry_items_for_module("MODULE_TEST_SAMPLE") == []


def test_module3_shell_actions_are_registered_in_platform_quick_action_registry():
    actions = get_quick_action_registry_items_for_module("MODULE_03_USERS_ROLES", surface="MODULE_BAR")
    codes = [action["quickActionCode"] for action in actions]

    assert codes == [
        "MODULE_03_FIND_USER",
        "MODULE_03_BLOCKED_USERS",
        "MODULE_03_CHECK_ACCESS",
        "MODULE_03_AUDIT_LOG",
        "MODULE_03_USERS_WITHOUT_COMPANY",
        "MODULE_03_USERS_WITHOUT_TYPE",
        "MODULE_03_SYSTEM_USERS",
        "MODULE_03_ACCESS_MATRIX",
        "MODULE_03_EXPORT_USERS",
    ]
    assert all(action["sourceModuleCode"] == "MODULE_03_USERS_ROLES" for action in actions)
    assert all(action["maxSurface"] == "BOTH" for action in actions)
    assert all(action["settings"]["shellActionId"] for action in actions)
    assert actions[0]["titleRu"] == "Найти пользователя"
    assert actions[0]["targetRoute"] == "#users?focus=search"
    assert actions[2]["actionCode"] == "CHECK_EFFECTIVE_ACCESS"
    assert actions[7]["settings"]["detailTarget"] == "#access-matrix-detail"
    assert actions[8]["isAvailable"] is False
    assert actions[8]["settings"]["disabledReason"] == "Экспорт будет доступен после подключения сервиса экспорта."


def test_planned_future_actions_are_registry_metadata_not_available_actions():
    action = get_quick_action_registry_item("CUSTOMER_OBJECT_CREATE")

    assert action is not None
    assert action.status == "PLANNED"
    assert action.sourceModuleCode == "MODULE_07_DIGITAL_HOUSE"
    assert action.settings["payloadOwner"] == "MODULE_07_DIGITAL_HOUSE"


def test_admin_can_preview_non_active_quick_action_registry_items():
    preview_items = get_preview_quick_action_registry_items(
        {
            "roleCode": "SUPER_ADMIN",
            "authMode": "mock",
        }
    )
    preview_codes = {item["quickActionCode"] for item in preview_items}

    assert "CUSTOMER_OBJECT_CREATE" in preview_codes
    assert "SUPPLIER_OFFER_CREATE" in preview_codes
    assert "MATERIAL_CREATE" not in preview_codes


def test_quick_action_registry_model_is_module03_metadata_not_payload():
    item = QuickActionRegistryItem(
        quick_action_code="TEST_ACTION",
        title="Test",
        source_module_code="MODULE_01_MATERIAL_HUB",
        action_code="OPEN_TEST",
        action_type="navigate",
        required_action_code="VIEW",
        required_access_level="VIEW",
        required_scope="LIMITED",
        max_surface="BOTH",
    )

    assert item.quick_action_code == "TEST_ACTION"
    assert item.action_code == "OPEN_TEST"
    assert item.max_surface == "BOTH"
    assert not hasattr(item, "business_payload")


def test_quick_action_registry_database_contract_has_surface_fields():
    columns = QuickActionRegistryItem.__table__.columns

    assert "section_code" in columns
    assert "action_code" in columns
    assert "action_type" in columns
    assert "target_route" in columns
    assert "modal_code" in columns
    assert "required_permission" in columns
    assert "is_enabled_by_default" in columns
    assert "is_available" in columns
    assert "max_surface" in columns


def test_quick_action_surface_migration_is_compatible_and_registers_module3_actions():
    sql = (ROOT / "database/migrations/20260702_platform_quick_action_surfaces.sql").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS action_code" in sql
    assert "ADD COLUMN IF NOT EXISTS max_surface" in sql
    assert "ck_quick_action_registry_action_type" in sql
    assert "ck_quick_action_registry_max_surface" in sql
    assert "MODULE3_USERS_OPEN" in sql
    assert "MODULE3_ACCESS_CONFIGURE" in sql
    assert "moduleNumber" not in sql


def test_module3_quick_action_registration_migration_replaces_old_shell_actions():
    sql = (ROOT / "database/migrations/20260702_module03_quick_actions_registration.sql").read_text(encoding="utf-8")

    assert "MODULE_03_FIND_USER" in sql
    assert "MODULE_03_BLOCKED_USERS" in sql
    assert "MODULE_03_CHECK_ACCESS" in sql
    assert "MODULE_03_USERS_WITHOUT_COMPANY" in sql
    assert "MODULE_03_EXPORT_USERS" in sql
    assert "MODULE3_USERS_OPEN" in sql
    assert "status = 'DISABLED'" in sql
    assert "Экспорт будет доступен после подключения сервиса экспорта." in sql
    assert "moduleNumber" not in sql
