from app.services.dashboard_module_registry import (
    get_atom_map_modules,
    get_canonical_module_code,
    get_dashboard_module_registry_item,
    get_planned_dashboard_modules,
    get_visible_dashboard_modules,
    is_module_available_for_dashboard,
    is_region_available_for_dashboard,
    normalize_dashboard_layout,
    resolve_module_route,
)


def test_price_history_legacy_module_resolves_to_analytics_feature():
    assert get_canonical_module_code("MODULE_14_PRICE_HISTORY") == "MODULE_11_ANALYTICS"
    assert resolve_module_route("MODULE_14_PRICE_HISTORY") == "/modules/analytics?section=price-dynamics"
    assert is_module_available_for_dashboard("MODULE_14_PRICE_HISTORY") is False


def test_legacy_admin_cabinet_is_deprecated_context_alias_not_active_module_16():
    legacy_admin = get_dashboard_module_registry_item("MODULE_16_ADMIN_CABINET")
    logistics = get_dashboard_module_registry_item("MODULE_16_LOGISTICS_DELIVERY")

    assert legacy_admin is not None
    assert legacy_admin.status == "deprecated"
    assert get_canonical_module_code("MODULE_16_ADMIN_CABINET") == "MODULE_03_USERS_ROLES"
    assert is_module_available_for_dashboard("MODULE_16_ADMIN_CABINET") is False
    assert logistics is not None
    assert logistics.status == "planned"


def test_legacy_digital_object_is_merged_alias_for_digital_house():
    legacy_object = get_dashboard_module_registry_item("MODULE_07_DIGITAL_OBJECT")
    digital_house = get_dashboard_module_registry_item("MODULE_07_DIGITAL_HOUSE")

    assert legacy_object is not None
    assert legacy_object.status == "merged"
    assert legacy_object.canonicalModuleCode == "MODULE_07_DIGITAL_HOUSE"
    assert legacy_object.mergedIntoModuleCode == "MODULE_07_DIGITAL_HOUSE"
    assert legacy_object.redirectRoute == "/modules/digital-house"
    assert get_canonical_module_code("MODULE_07_DIGITAL_OBJECT") == "MODULE_07_DIGITAL_HOUSE"
    assert resolve_module_route("MODULE_07_DIGITAL_OBJECT") == "/modules/digital-house"
    assert is_module_available_for_dashboard("MODULE_07_DIGITAL_OBJECT") is False
    assert digital_house is not None
    assert digital_house.status == "planned"


def test_dashboard_layout_normalizes_legacy_module_codes_without_losing_legacy():
    layout = {
        "favoriteModules": ["MODULE_01_MATERIAL_HUB", "MODULE_14_PRICE_HISTORY", "MODULE_07_DIGITAL_OBJECT"],
        "widgets": [
            {
                "title": "Динамика цен",
                "moduleCode": "MODULE_14_PRICE_HISTORY",
                "moduleNumberLegacy": 14,
            },
            {
                "title": "Материалы",
                "moduleNumberLegacy": 1,
            },
            {
                "title": "Образ объекта",
                "moduleCode": "MODULE_07_DIGITAL_OBJECT",
            },
        ],
    }

    normalized = normalize_dashboard_layout(layout)

    assert normalized["favoriteModules"] == ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS", "MODULE_07_DIGITAL_HOUSE"]
    assert normalized["widgets"][0]["moduleCode"] == "MODULE_11_ANALYTICS"
    assert normalized["widgets"][0]["canonicalModuleCode"] == "MODULE_11_ANALYTICS"
    assert normalized["widgets"][0]["legacyModuleCode"] == "MODULE_14_PRICE_HISTORY"
    assert normalized["widgets"][1]["moduleCode"] == "MODULE_01_MATERIAL_HUB"
    assert normalized["widgets"][2]["moduleCode"] == "MODULE_07_DIGITAL_HOUSE"
    assert normalized["widgets"][2]["legacyModuleCode"] == "MODULE_07_DIGITAL_OBJECT"


def test_visible_dashboard_modules_hide_merged_and_use_canonical_access():
    profile = {
        "roleCode": "ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"],
        "favoriteModuleCodes": ["MODULE_14_PRICE_HISTORY", "MODULE_01_MATERIAL_HUB"],
    }

    visible_codes = {item["moduleCode"] for item in get_visible_dashboard_modules(profile)}
    atom_codes = [item["moduleCode"] for item in get_atom_map_modules(profile)]

    assert "MODULE_01_MATERIAL_HUB" in visible_codes
    assert "MODULE_11_ANALYTICS" in visible_codes
    assert "MODULE_14_PRICE_HISTORY" not in visible_codes
    assert atom_codes[0] == "MODULE_11_ANALYTICS"


def test_region_availability_uses_profile_context_or_known_registry_code():
    assert is_region_available_for_dashboard(
        "KRASNODAR_KRAI",
        {"availableRegionCodes": ["KRASNODAR_KRAI"]},
    )
    assert not is_region_available_for_dashboard(
        "ROSTOV_REGION",
        {"availableRegionCodes": ["KRASNODAR_KRAI"]},
    )


def test_planned_modules_are_preview_only_for_admin_context():
    admin_profile = {
        "roleCode": "SUPER_ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": [
            "MODULE_01_MATERIAL_HUB",
            "MODULE_05_ESTIMATE_ENGINE",
            "MODULE_07_DIGITAL_HOUSE",
        ],
        "favoriteModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
    }

    planned_codes = {item["moduleCode"] for item in get_planned_dashboard_modules(admin_profile)}
    visible_codes = {item["moduleCode"] for item in get_visible_dashboard_modules(admin_profile)}
    atom_codes = {item["moduleCode"] for item in get_atom_map_modules(admin_profile)}

    assert "MODULE_07_DIGITAL_HOUSE" in planned_codes
    assert "MODULE_05_ESTIMATE_ENGINE" in planned_codes
    assert "MODULE_07_DIGITAL_HOUSE" not in visible_codes
    assert "MODULE_07_DIGITAL_HOUSE" not in atom_codes
    assert not is_module_available_for_dashboard("MODULE_07_DIGITAL_HOUSE")


def test_planned_modules_are_hidden_from_regular_user_preview():
    regular_profile = {
        "roleCode": "VIEWER",
        "authMode": "mock",
        "allowedModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
        "favoriteModuleCodes": ["MODULE_07_DIGITAL_HOUSE"],
    }

    assert get_planned_dashboard_modules(regular_profile) == []
    assert get_visible_dashboard_modules(regular_profile) == []
    assert get_atom_map_modules(regular_profile) == []
