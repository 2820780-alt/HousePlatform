from app.models import QuickActionRegistryItem
from app.services.quick_action_registry import (
    QUICK_ACTION_REGISTRY_LAYER,
    get_preview_quick_action_registry_items,
    get_quick_action_registry,
    get_quick_action_registry_item,
)


def test_quick_action_registry_is_code_first_and_not_dashboard_hardcode():
    registry = get_quick_action_registry()

    assert registry
    assert all(item["registryLayer"] == QUICK_ACTION_REGISTRY_LAYER for item in registry)
    assert all("moduleNumber" not in item for item in registry)
    assert all("sourceModuleNumber" not in item for item in registry)

    supplier_action = get_quick_action_registry_item("SUPPLIER_PRICE_UPLOAD")
    assert supplier_action is not None
    assert supplier_action.sourceModuleCode == "MODULE_01_MATERIAL_HUB"
    assert supplier_action.featureCode == "UPLOAD_SUPPLIER_FILE"
    assert supplier_action.requiredActionCode == "VIEW"
    assert supplier_action.requiredAccessLevel == "VIEW"
    assert supplier_action.requiredScope == "LIMITED"


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
        required_action_code="VIEW",
        required_access_level="VIEW",
        required_scope="LIMITED",
    )

    assert item.quick_action_code == "TEST_ACTION"
    assert not hasattr(item, "business_payload")
