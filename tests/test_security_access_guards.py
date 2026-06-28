import pytest

from app.core.exceptions import ForbiddenError
from app.core.permission_guard import can, canonical_module_code, require_permission
from app.core.scope_filters import filter_resources_by_scope, project_limited_fields, resource_matches_scope
from app.models import ModuleActionRegistry, PlatformModuleRegistry
from app.services.admin_user_role_management import can_assign_role_code
from app.services.dashboard_module_registry import get_planned_dashboard_modules
from app.services.module_visibility import ActiveRegionContext, build_visible_module_items
from app.services.preview_role import enter_preview_role, require_real_actor_permission_for_preview_action
from app.services.user_dashboard_layout import validate_user_dashboard_layout
from app.services.widget_permission import can_view_widget


def _module(module_code: str, **overrides):
    data = {
        "module_code": module_code,
        "canonical_module_code": overrides.pop("canonical_module_code", module_code),
        "title": module_code,
        "status": "ACTIVE",
        "is_active": True,
        "is_public": True,
        "is_visible_in_sidebar": True,
        "is_visible_on_dashboard": True,
        "is_visible_on_atom_map": True,
        "route": f"/modules/{module_code.lower()}",
        "display_order": 10,
        "available_actions": ["VIEW", "EDIT", "ADMIN"],
    }
    data.update(overrides)
    return PlatformModuleRegistry(**data)


def _action(module_code: str, action_code: str = "VIEW"):
    return ModuleActionRegistry(
        module_code=module_code,
        action_code=action_code,
        title=action_code,
        is_active=True,
    )


def test_user_without_role_sees_no_modules_and_has_no_permissions():
    user = {"userId": "anonymous"}

    assert not can(user, "MODULE_01_MATERIAL_HUB", "VIEW", "LIMITED")
    assert build_visible_module_items(
        [_module("MODULE_01_MATERIAL_HUB")],
        user,
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test"),
        [_action("MODULE_01_MATERIAL_HUB")],
    ) == []


def test_viewer_cannot_edit_and_hidden_button_is_not_a_backend_guard():
    viewer = {"userId": "viewer-1", "roleCode": "VIEWER"}

    assert not can(viewer, "MODULE_01_MATERIAL_HUB", "EDIT", "GLOBAL")
    with pytest.raises(ForbiddenError):
        require_permission(viewer, "MODULE_01_MATERIAL_HUB", "EDIT", "GLOBAL")


def test_supplier_scope_blocks_foreign_data_and_canonical_material_edit():
    supplier = {"userId": "supplier-user", "roleCode": "SUPPLIER", "supplierIds": ["supplier-1"]}
    resources = [
        {"id": "own-price", "supplier_id": "supplier-1"},
        {"id": "foreign-price", "supplier_id": "supplier-2"},
    ]

    assert filter_resources_by_scope(resources, supplier, "OWN") == [{"id": "own-price", "supplier_id": "supplier-1"}]
    assert not can(supplier, "MODULE_01_MATERIAL_HUB", "EDIT", "GLOBAL")
    with pytest.raises(ForbiddenError):
        require_permission(supplier, "MODULE_01_MATERIAL_HUB", "EDIT", "GLOBAL")


def test_contractor_and_customer_do_not_see_foreign_resources():
    contractor = {"roleCode": "CONTRACTOR", "contractorIds": ["contractor-1"]}
    customer = {"roleCode": "CUSTOMER", "customerIds": ["customer-1"], "projectIds": ["project-1"]}

    assert resource_matches_scope({"contractor_id": "contractor-1"}, contractor, "OWN")
    assert not resource_matches_scope({"contractor_id": "contractor-2"}, contractor, "OWN")
    assert resource_matches_scope({"customer_id": "customer-1"}, customer, "OWN")
    assert not resource_matches_scope({"customer_id": "customer-2"}, customer, "OWN")
    assert resource_matches_scope({"project_id": "project-1"}, customer, "OWN")
    assert not resource_matches_scope({"project_id": "project-2"}, customer, "OWN")


def test_moderator_estimator_and_platform_admin_boundaries():
    moderator = {"roleCode": "MODERATOR"}
    estimator = {"roleCode": "ESTIMATOR"}
    platform_admin = {"roleCode": "PLATFORM_ADMIN"}

    assert not can(moderator, "MODULE_03_USERS_ROLES", "EDIT", "GLOBAL")
    assert not can(estimator, "MODULE_01_MATERIAL_HUB", "EDIT", "GLOBAL")
    assert can(platform_admin, "MODULE_03_USERS_ROLES", "EDIT", "GLOBAL")
    assert not can(platform_admin, "MODULE_03_USERS_ROLES", "ADMIN", "GLOBAL")
    assert not can_assign_role_code(platform_admin, "SUPER_ADMIN")


def test_limited_scope_does_not_leak_hidden_fields():
    payload = {
        "id": "material-1",
        "title": "Газоблок",
        "internal_margin": "hidden",
        "supplier_secret": "hidden",
    }

    assert project_limited_fields(payload, ["id", "title"]) == {
        "id": "material-1",
        "title": "Газоблок",
    }


def test_widget_layout_cannot_grant_unavailable_or_out_of_scope_widget_data():
    customer = {
        "userId": "customer-1",
        "roleCode": "CUSTOMER",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedWidgetCodes": ["price-dynamics", "digital-house-status"],
        "allowedFeatureCodes": ["PRICE_DYNAMICS"],
    }
    layout = {
        "roleCode": "CUSTOMER",
        "activeRegionCode": "KRASNODAR_KRAI",
        "userDashboardLayout": {
            "widgets": [
                {"widgetCode": "price-dynamics", "isVisible": True},
                {"widgetCode": "digital-house-status", "isVisible": True},
            ]
        },
    }

    assert not can_view_widget(customer, "price-dynamics", layout)
    assert not can_view_widget(customer, "digital-house-status", layout)
    assert validate_user_dashboard_layout(
        {
            "userId": "customer-1",
            "activeRegionCode": "KRASNODAR_KRAI",
            "widgets": [{"widgetCode": "digital-house-status", "position": 1}],
        },
        user=customer,
    )["widgets"] == []


def test_disabled_archived_merged_and_planned_modules_are_not_active_visibility_items():
    modules = [
        _module("MODULE_01_MATERIAL_HUB"),
        _module("MODULE_DISABLED", status="DISABLED", is_active=False),
        _module("MODULE_ARCHIVED", status="ARCHIVED", is_active=False),
        _module("MODULE_14_PRICE_HISTORY", canonical_module_code="MODULE_11_ANALYTICS", status="MERGED", is_active=False),
        _module("MODULE_07_DIGITAL_HOUSE", status="PLANNED", is_active=False),
    ]

    items = build_visible_module_items(
        modules,
        {"roleCode": "SUPER_ADMIN"},
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test"),
        [_action("MODULE_01_MATERIAL_HUB")],
    )

    assert [item.moduleCode for item in items] == ["MODULE_01_MATERIAL_HUB"]


def test_future_modules_and_widgets_are_hidden_without_permissions():
    assert get_planned_dashboard_modules({"roleCode": "VIEWER", "authMode": "mock"}) == []
    assert not can_view_widget(
        {"roleCode": "VIEWER", "activeRegionCode": "KRASNODAR_KRAI"},
        "digital-house-status",
        {"roleCode": "VIEWER", "activeRegionCode": "KRASNODAR_KRAI", "userDashboardLayout": {"widgets": []}},
    )


def test_legacy_module_codes_normalize_without_becoming_active_modules():
    assert canonical_module_code("MODULE_07_DIGITAL_OBJECT") == "MODULE_07_DIGITAL_HOUSE"
    assert canonical_module_code("MODULE_14_PRICE_HISTORY") == "MODULE_11_ANALYTICS"
    assert canonical_module_code("MODULE_14_CONSTRUCTOR_LITE") == "MODULE_19_CONSTRUCTOR_LITE"
    assert canonical_module_code("MODULE_15_CONSTRUCTION_GROUPS") == "MODULE_01_MATERIAL_HUB"
    assert canonical_module_code("MODULE_16_ADMIN_CABINET") == "MODULE_03_USERS_ROLES"


def test_preview_role_changes_visual_access_but_not_real_actor_permission():
    preview = enter_preview_role(
        {"userId": "admin-1", "roleCode": "ADMIN", "authMode": "mock"},
        "SUPPLIER",
        active_region_code="KRASNODAR_KRAI",
        log_event=False,
    )

    assert preview["actorUser"]["roleCode"] == "ADMIN"
    assert preview["visualUser"]["roleCode"] == "SUPPLIER"
    assert can(preview["visualUser"], "MODULE_03_USERS_ROLES", "EDIT", "GLOBAL") is False
    assert require_real_actor_permission_for_preview_action(
        preview["actorUser"],
        module_code="MODULE_03_USERS_ROLES",
        action_code="EDIT",
        scope="GLOBAL",
    ) == preview["actorUser"]
    with pytest.raises(ForbiddenError):
        require_real_actor_permission_for_preview_action(
            {"userId": "supplier-1", "roleCode": "SUPPLIER"},
            module_code="MODULE_03_USERS_ROLES",
            action_code="EDIT",
            scope="GLOBAL",
        )
