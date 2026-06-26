from app.services.dashboard_module_registry import (
    get_atom_map_modules,
    get_canonical_module_code,
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


def test_dashboard_layout_normalizes_legacy_module_codes_without_losing_legacy():
    layout = {
        "favoriteModules": ["MODULE_01_MATERIAL_HUB", "MODULE_14_PRICE_HISTORY"],
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
        ],
    }

    normalized = normalize_dashboard_layout(layout)

    assert normalized["favoriteModules"] == ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"]
    assert normalized["widgets"][0]["moduleCode"] == "MODULE_11_ANALYTICS"
    assert normalized["widgets"][0]["canonicalModuleCode"] == "MODULE_11_ANALYTICS"
    assert normalized["widgets"][0]["legacyModuleCode"] == "MODULE_14_PRICE_HISTORY"
    assert normalized["widgets"][1]["moduleCode"] == "MODULE_01_MATERIAL_HUB"


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
