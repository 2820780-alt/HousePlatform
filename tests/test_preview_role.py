import pytest

from app.core.exceptions import ForbiddenError
from app.models import ModuleActionRegistry, PlatformModuleRegistry
from app.services.audit_log_service import AuditLogType, MOCK_AUDIT_EVENTS, clear_mock_audit_events
from app.services.module_visibility import ActiveRegionContext, build_visible_module_items
from app.services.preview_role import (
    PREVIEW_ROLE_LAYER,
    can_enter_preview_role,
    enter_preview_role,
    exit_preview_role,
    filter_preview_module_visibility_items,
    require_real_actor_permission_for_preview_action,
)


def setup_function():
    clear_mock_audit_events()


def _actor(**overrides):
    data = {
        "userId": "admin-1",
        "roleCode": "SUPER_ADMIN",
        "workspaceId": "workspace-admin",
        "activeRegionCode": "KRASNODAR_KRAI",
        "authMode": "mock",
    }
    data.update(overrides)
    return data


def _module(module_code: str, **overrides):
    data = {
        "module_code": module_code,
        "canonical_module_code": module_code,
        "title": module_code,
        "status": "ACTIVE",
        "is_active": True,
        "is_visible_on_dashboard": True,
        "route": f"/modules/{module_code.lower()}",
        "display_order": 10,
        "available_actions": ["VIEW"],
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


def test_enter_preview_role_preserves_real_actor_and_builds_visual_user():
    preview = enter_preview_role(
        _actor(roleCode="ADMIN"),
        "SUPPLIER",
        active_region_code="KRASNODAR_KRAI",
        workspace_id="workspace-admin",
    )

    assert preview["previewLayer"] == PREVIEW_ROLE_LAYER
    assert preview["isPreviewMode"] is True
    assert preview["actorUser"]["roleCode"] == "ADMIN"
    assert preview["visualUser"]["roleCode"] == "SUPPLIER"
    assert preview["visualUser"]["realRoleCode"] == "ADMIN"
    assert preview["visualUser"]["activeRegionCode"] == "KRASNODAR_KRAI"
    assert preview["visualUser"]["allowedActionCodes"] == ["SUPPLIER_PRICE_UPLOAD", "DASHBOARD_CONFIGURE"]
    assert preview["userDashboardLayout"]["isPreviewLayout"] is True
    assert preview["userDashboardLayout"]["previewRoleCode"] == "SUPPLIER"
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.VIEW_AS_ROLE_ENTERED
    assert MOCK_AUDIT_EVENTS[-1]["roleCode"] == "SUPPLIER"


def test_exit_preview_role_logs_exit_without_mutating_actor_role():
    result = exit_preview_role(
        _actor(roleCode="ADMIN"),
        preview_role_code="CUSTOMER",
        workspace_id="workspace-admin",
    )

    assert result["isPreviewMode"] is False
    assert result["actorUser"]["roleCode"] == "ADMIN"
    assert result["visualUser"]["roleCode"] == "ADMIN"
    assert result["previewRoleCode"] is None
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.VIEW_AS_ROLE_EXITED
    assert MOCK_AUDIT_EVENTS[-1]["roleCode"] == "CUSTOMER"


def test_ordinary_role_cannot_enter_preview_role():
    supplier = _actor(roleCode="SUPPLIER")

    assert not can_enter_preview_role(supplier, "CUSTOMER")
    with pytest.raises(ForbiddenError):
        enter_preview_role(supplier, "CUSTOMER", active_region_code="KRASNODAR_KRAI")


def test_preview_visibility_uses_visual_role_profile_not_admin_access():
    preview = enter_preview_role(
        _actor(roleCode="ADMIN"),
        "SUPPLIER",
        active_region_code="KRASNODAR_KRAI",
        log_event=False,
    )
    modules = [
        _module("MODULE_01_MATERIAL_HUB", title="Material Hub"),
        _module("MODULE_03_USERS_ROLES", title="Users"),
        _module("MODULE_11_ANALYTICS", title="Analytics"),
    ]
    raw_visible = build_visible_module_items(
        modules,
        preview["visualUser"],
        ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test"),
        [_action("MODULE_01_MATERIAL_HUB"), _action("MODULE_03_USERS_ROLES"), _action("MODULE_11_ANALYTICS")],
    )
    filtered = filter_preview_module_visibility_items(preview, raw_visible)

    assert {item.moduleCode for item in raw_visible} == {"MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"}
    assert [item.moduleCode for item in filtered] == ["MODULE_01_MATERIAL_HUB"]
    assert "MODULE_03_USERS_ROLES" not in {item.moduleCode for item in filtered}


def test_dangerous_action_uses_real_actor_permission_not_preview_role():
    admin = _actor(roleCode="ADMIN")
    supplier = _actor(roleCode="SUPPLIER")

    assert require_real_actor_permission_for_preview_action(
        admin,
        module_code="MODULE_03_USERS_ROLES",
        action_code="EDIT",
        scope="GLOBAL",
    ) == admin
    with pytest.raises(ForbiddenError):
        require_real_actor_permission_for_preview_action(
            supplier,
            module_code="MODULE_03_USERS_ROLES",
            action_code="EDIT",
            scope="GLOBAL",
        )
