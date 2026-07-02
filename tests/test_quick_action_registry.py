from app.models import QuickActionRegistryItem
from pathlib import Path
from app.services.quick_action_registry import (
    QUICK_ACTION_REGISTRY_LAYER,
    get_quick_action_registry_items_for_module,
    get_preview_quick_action_registry_items,
    get_quick_action_registry,
    get_quick_action_registry_item,
)


ROOT = Path(__file__).resolve().parents[1]


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


def test_module3_shell_actions_are_registered_in_platform_quick_action_registry():
    actions = get_quick_action_registry_items_for_module("MODULE_03_USERS_ROLES", surface="MODULE_BAR")
    codes = [action["quickActionCode"] for action in actions]

    assert codes == [
        "MODULE3_USERS_OPEN",
        "MODULE3_COMPANIES_OPEN",
        "MODULE3_USERS_IMPORT",
        "MODULE3_AUDIT_OPEN",
        "MODULE3_ACCESS_CONFIGURE",
        "MODULE3_ACCESS_BULK_ASSIGN",
        "MODULE3_USERS_EXPORT",
    ]
    assert all(action["sourceModuleCode"] == "MODULE_03_USERS_ROLES" for action in actions)
    assert all(action["maxSurface"] == "MODULE_BAR" for action in actions)
    assert all(action["settings"]["shellActionId"] for action in actions)
    assert actions[0]["targetRoute"] == "#users"
    assert actions[4]["settings"]["detailTarget"] == "#access-matrix-detail"


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
