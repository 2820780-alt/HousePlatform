from pathlib import Path

from app.models import QuickActionRegistryItem
from app.services.quick_action_registry import (
    DEPRECATED_ACTIVE_DISPLAY_FIELDS,
    QUICK_ACTION_REGISTRY_LAYER,
    build_quick_action_registry_item,
    filter_quick_action_registry_items_for_module,
    get_preview_quick_action_registry_items,
    get_quick_action_registry,
    get_quick_action_registry_item,
    get_quick_action_registry_items_for_module,
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
        "titleRu": "РћС‚РєСЂС‹С‚СЊ СЃРїРёСЃРѕРє",
        "descriptionRu": "РўРµСЃС‚РѕРІРѕРµ РґРµР№СЃС‚РІРёРµ РґР»СЏ РїСЂРѕРІРµСЂРєРё СЂР°СЃС€РёСЂСЏРµРјРѕСЃС‚Рё quick actions.",
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
        "titleRu": "РђСЂС…РёРІРЅРѕРµ РґРµР№СЃС‚РІРёРµ",
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


def test_quick_action_registry_is_empty_compatibility_layer():
    assert get_quick_action_registry() == []
    assert get_quick_action_registry_item("SAMPLE_OPEN_LIST") is None
    assert get_quick_action_registry_items_for_module("MODULE_TEST_SAMPLE") == []
    assert get_quick_action_registry_items_for_module("MODULE_03_USERS_ROLES") == []
    assert get_preview_quick_action_registry_items({"roleCode": "SUPER_ADMIN", "authMode": "mock"}) == []


def test_dashboard_service_does_not_import_quick_action_registry_as_source():
    dashboard_service = (ROOT / "app/services/dashboard_quick_actions.py").read_text(encoding="utf-8")

    assert "get_quick_action_registry" not in dashboard_service
    assert "get_quick_action_registry_item" not in dashboard_service
    assert "DEFAULT_ATOM_CARD_ACTION_CODES: dict[str, tuple[str, ...]] = {}" in dashboard_service


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


def test_user_saved_shortcuts_can_use_universal_surface_contract():
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
    assert item.registryLayer == QUICK_ACTION_REGISTRY_LAYER
    assert payload["titleRu"] == "РћС‚РєСЂС‹С‚СЊ СЃРїРёСЃРѕРє"
    assert payload["sortOrder"] == 10
    assert "moduleNumber" not in payload
    assert "sourceModuleNumber" not in payload


def test_external_user_shortcut_items_can_be_filtered_by_module_and_surface():
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


def test_quick_action_registry_database_contract_has_deprecated_compatibility_fields():
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
    assert set(DEPRECATED_ACTIVE_DISPLAY_FIELDS) == {
        "quickActionCode",
        "isEnabledByDefault",
        "maxSurface",
        "allowedRoles",
        "allowedCabinetTypes",
        "widgetCode",
    }
    for column_name in (
        "quick_action_code",
        "is_enabled_by_default",
        "max_surface",
        "allowed_roles",
        "allowed_cabinet_types",
        "widget_code",
    ):
        assert "not an active source" in columns[column_name].info["deprecated"]


def test_quick_action_migrations_keep_schema_but_do_not_seed_fixed_actions():
    migration_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "database/migrations").glob("*.sql"))

    assert "CREATE TABLE IF NOT EXISTS quick_action_registry_items" in migration_text
    assert "CREATE TABLE IF NOT EXISTS user_module_quick_actions" in migration_text
    assert "INSERT INTO quick_action_registry_items" not in migration_text
    assert "default_quick_action_codes" not in migration_text
