from fastapi.testclient import TestClient

from app.main import app
from app.models import ModuleActionRegistry, PlatformModuleRegistry
from app.services.module_visibility import (
    ActiveRegionContext,
    build_visible_module_items,
    normalize_legacy_module_mapping,
)


def _module(
    module_code: str,
    *,
    canonical_module_code: str | None = None,
    title: str = "Module",
    status: str = "ACTIVE",
    is_active: bool = True,
    route: str = "/modules/module",
    icon: str = "box",
    display_order: int = 10,
    feature_codes: list[str] | None = None,
    legacy_codes: list[str] | None = None,
    available_actions: list[str] | None = None,
) -> PlatformModuleRegistry:
    return PlatformModuleRegistry(
        module_code=module_code,
        canonical_module_code=canonical_module_code or module_code,
        title=title,
        status=status,
        is_active=is_active,
        is_public=True,
        is_visible_in_sidebar=True,
        is_visible_on_dashboard=True,
        is_visible_on_atom_map=True,
        route=route,
        icon=icon,
        display_order=display_order,
        feature_codes=feature_codes,
        legacy_codes=legacy_codes,
        available_actions=available_actions,
    )


def _action(module_code: str, action_code: str) -> ModuleActionRegistry:
    return ModuleActionRegistry(
        module_code=module_code,
        action_code=action_code,
        title=action_code.title(),
        is_active=True,
    )


def test_module_visibility_returns_only_accessible_active_modules_from_registry():
    modules = [
        _module("MODULE_01_MATERIAL_HUB", title="Material Hub", route="/modules/material-hub", icon="atom-material"),
        _module("MODULE_11_ANALYTICS", title="Analytics", route="/modules/analytics"),
        _module("MODULE_07_DIGITAL_HOUSE", title="Digital House", status="PLANNED", is_active=False),
        _module("MODULE_14_PRICE_HISTORY", canonical_module_code="MODULE_11_ANALYTICS", status="MERGED", is_active=False),
        _module("MODULE_99_ARCHIVED", status="ARCHIVED", is_active=False),
    ]

    items = build_visible_module_items(
        modules,
        {"roleCode": "SUPPLIER"},
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test"),
        [_action("MODULE_01_MATERIAL_HUB", "VIEW"), _action("MODULE_11_ANALYTICS", "VIEW")],
    )
    by_code = {item.moduleCode: item for item in items}

    assert set(by_code) == {"MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"}
    assert by_code["MODULE_01_MATERIAL_HUB"].accessLevel == "VIEW"
    assert by_code["MODULE_01_MATERIAL_HUB"].scope == "LIMITED"
    assert by_code["MODULE_01_MATERIAL_HUB"].availableActions == ["VIEW"]
    assert by_code["MODULE_01_MATERIAL_HUB"].activeRegionCode == "KRASNODAR_KRAI"
    assert by_code["MODULE_11_ANALYTICS"].scope == "OWN"
    assert by_code["MODULE_11_ANALYTICS"].visible is True


def test_module_visibility_normalizes_legacy_price_history_into_analytics_feature():
    modules = [
        _module(
            "MODULE_11_ANALYTICS",
            title="Analytics",
            route="/modules/analytics",
            feature_codes=["PRICE_DYNAMICS"],
        ),
        _module(
            "MODULE_14_PRICE_HISTORY",
            canonical_module_code="MODULE_11_ANALYTICS",
            title="Price History",
            status="MERGED",
            is_active=False,
            route="/modules/price-history",
            feature_codes=["PRICE_DYNAMICS"],
            legacy_codes=["MODULE_14_PRICE_DYNAMICS"],
        ),
    ]
    user = {
        "moduleAccessRules": [
            {
                "moduleCode": "MODULE_14_PRICE_HISTORY",
                "accessLevel": "VIEW",
                "accessScope": "GLOBAL",
            }
        ]
    }

    items = build_visible_module_items(
        modules,
        user,
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test"),
    )
    mapping = normalize_legacy_module_mapping("MODULE_14_PRICE_HISTORY", modules)

    assert [item.moduleCode for item in items] == ["MODULE_11_ANALYTICS"]
    assert items[0].canonicalModuleCode == "MODULE_11_ANALYTICS"
    assert items[0].featureCodes == ["PRICE_DYNAMICS"]
    assert "MODULE_14_PRICE_HISTORY" in items[0].legacyModuleCodes
    assert mapping == {
        "moduleCode": "MODULE_14_PRICE_HISTORY",
        "canonicalModuleCode": "MODULE_11_ANALYTICS",
        "featureCodes": ["PRICE_DYNAMICS"],
        "redirectRoute": None,
    }


def test_module_visibility_returns_empty_list_when_active_region_is_not_active():
    items = build_visible_module_items(
        [_module("MODULE_01_MATERIAL_HUB", title="Material Hub")],
        {"roleCode": "VIEWER"},
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", False, "test"),
    )

    assert items == []


def test_module_visibility_filters_actions_by_access_level():
    items = build_visible_module_items(
        [
            _module(
                "MODULE_18_QUALITY_CONTROL",
                title="Quality Control",
                available_actions=["VIEW", "CREATE_ISSUE", "APPROVE_CHECK", "DELETE_SECRET"],
            )
        ],
        {"roleCode": "CUSTOMER"},
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test"),
    )

    assert items[0].moduleCode == "MODULE_18_QUALITY_CONTROL"
    assert items[0].availableActions == ["VIEW"]


def test_access_my_modules_route_is_registered_under_v1_api_prefix():
    client = TestClient(app)

    response = client.get("/api/v1/access/my-modules")
    assert response.status_code in {401, 403}
