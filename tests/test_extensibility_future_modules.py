import pytest

from app.core.exceptions import ForbiddenError
from app.core.module_registration import (
    DefaultModulePermission,
    NewModuleRegistration,
    registration_to_action_defaults,
    registration_to_module_access_defaults,
    registration_to_widget_defaults,
)
from app.core.permission_guard import can, require_permission
from app.models import ModuleActionRegistry, PlatformModuleRegistry, WidgetRegistryItem
from app.services.admin_module_registry_management import can_open_module_registry_admin
from app.services.audit_log_service import (
    MOCK_AUDIT_EVENTS,
    AuditLogType,
    clear_mock_audit_events,
    record_dashboard_layout_change,
    record_widget_registry_change,
    write_audit_event_mock,
)
from app.services.module_visibility import ActiveRegionContext, build_visible_module_items
from app.services.user_dashboard_layout import add_widget_to_layout
from app.services.widget_permission import can_add_widget, can_view_widget
from app.services.widget_registry import get_widget_registry_item


FUTURE_MODULE_CODE = "MODULE_TEST_FUTURE_SANDBOX"
FUTURE_WIDGET_CODE = "future-sandbox-status"
ACTIVE_REGION = ActiveRegionContext("KRASNODAR_KRAI", "Краснодарский край", True, "test")


def setup_function():
    clear_mock_audit_events()


def _future_registration() -> NewModuleRegistration:
    return NewModuleRegistration(
        moduleCode=FUTURE_MODULE_CODE,
        canonicalModuleCode=FUTURE_MODULE_CODE,
        title="Future Sandbox",
        status="PLANNED",
        defaultPermissions=(
            DefaultModulePermission("SUPER_ADMIN", "ADMIN", "GLOBAL"),
            DefaultModulePermission("PLATFORM_ADMIN", "VIEW", "GLOBAL"),
        ),
        availableActions=("VIEW", "RUN_SANDBOX"),
        dashboardWidgets=(FUTURE_WIDGET_CODE,),
        ownerScopeRules={"ownerField": "workspaceId", "regionField": "activeRegionCode"},
        featureCodes=("FUTURE_SANDBOX_STATUS",),
    )


def _registry_module(
    *,
    status: str = "ACTIVE",
    is_active: bool = True,
    available_actions: list[str] | None = None,
) -> PlatformModuleRegistry:
    return PlatformModuleRegistry(
        module_code=FUTURE_MODULE_CODE,
        canonical_module_code=FUTURE_MODULE_CODE,
        title="Future Sandbox",
        short_title="Sandbox",
        description="Test-only future module registration without business logic.",
        status=status,
        is_system=True,
        is_active=is_active,
        is_public=True,
        is_visible_in_sidebar=True,
        is_visible_on_dashboard=True,
        is_visible_on_atom_map=True,
        is_available_for_widgets=True,
        route="/modules/test-future-sandbox",
        icon="box",
        display_order=9900,
        feature_codes=["FUTURE_SANDBOX_STATUS"],
        available_actions=available_actions or ["VIEW", "RUN_SANDBOX"],
        dashboard_widgets=[FUTURE_WIDGET_CODE],
    )


def _action(module_code: str = FUTURE_MODULE_CODE, action_code: str = "VIEW") -> ModuleActionRegistry:
    return ModuleActionRegistry(
        module_code=module_code,
        action_code=action_code,
        title=action_code,
        is_active=True,
    )


def _platform_admin_with_future_permission() -> dict:
    return {
        "userId": "platform-admin",
        "roleCode": "PLATFORM_ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "moduleAccessRules": [
            {
                "moduleCode": FUTURE_MODULE_CODE,
                "accessLevel": "VIEW",
                "accessScope": "GLOBAL",
            }
        ],
    }


def test_new_future_module_registration_exports_registry_permissions_actions_and_widgets():
    registration = _future_registration()
    metadata = registration.to_registry_metadata()

    assert metadata["moduleCode"] == FUTURE_MODULE_CODE
    assert metadata["canonicalModuleCode"] == FUTURE_MODULE_CODE
    assert metadata["status"] == "PLANNED"
    assert metadata["availableActions"] == ["VIEW", "RUN_SANDBOX"]
    assert metadata["dashboardWidgets"] == [FUTURE_WIDGET_CODE]
    assert metadata["ownerScopeRules"]["regionField"] == "activeRegionCode"
    assert "moduleNumber" not in metadata

    assert registration_to_module_access_defaults(registration) == [
        {
            "roleCode": "SUPER_ADMIN",
            "moduleCode": FUTURE_MODULE_CODE,
            "accessLevel": "ADMIN",
            "accessScope": "GLOBAL",
        },
        {
            "roleCode": "PLATFORM_ADMIN",
            "moduleCode": FUTURE_MODULE_CODE,
            "accessLevel": "VIEW",
            "accessScope": "GLOBAL",
        },
    ]
    assert registration_to_action_defaults(registration) == [
        {"moduleCode": FUTURE_MODULE_CODE, "actionCode": "VIEW"},
        {"moduleCode": FUTURE_MODULE_CODE, "actionCode": "RUN_SANDBOX"},
    ]
    assert registration_to_widget_defaults(registration) == [
        {"widgetCode": FUTURE_WIDGET_CODE, "sourceModuleCode": FUTURE_MODULE_CODE}
    ]


def test_future_module_can_be_stored_in_platform_module_registry_without_dashboard_rewrite():
    module = _registry_module(status="ACTIVE", is_active=True)
    platform_admin = _platform_admin_with_future_permission()

    items = build_visible_module_items(
        [module],
        platform_admin,
        ACTIVE_REGION,
        [_action(action_code="VIEW"), _action(action_code="RUN_SANDBOX")],
    )

    assert module.module_code == FUTURE_MODULE_CODE
    assert module.default_permissions is None
    assert [item.moduleCode for item in items] == [FUTURE_MODULE_CODE]
    assert items[0].availableActions == ["VIEW"]
    assert items[0].activeRegionCode == "KRASNODAR_KRAI"


def test_future_module_is_hidden_without_permissions_and_platform_admin_needs_explicit_grant():
    module = _registry_module(status="ACTIVE", is_active=True)

    assert build_visible_module_items([module], {"userId": "no-role"}, ACTIVE_REGION, [_action()]) == []
    assert build_visible_module_items([module], {"roleCode": "PLATFORM_ADMIN"}, ACTIVE_REGION, [_action()]) == []
    assert build_visible_module_items(
        [module],
        _platform_admin_with_future_permission(),
        ACTIVE_REGION,
        [_action()],
    )[0].moduleCode == FUTURE_MODULE_CODE


def test_super_admin_can_see_future_module_in_registry_admin_but_not_as_active_when_planned():
    planned_module = _registry_module(status="PLANNED", is_active=False)
    super_admin = {"userId": "super-admin", "roleCode": "SUPER_ADMIN"}

    assert can_open_module_registry_admin(super_admin)
    assert planned_module.module_code == FUTURE_MODULE_CODE
    assert build_visible_module_items(
        [planned_module],
        {**super_admin, "moduleAccessRules": [{"moduleCode": FUTURE_MODULE_CODE, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}]},
        ACTIVE_REGION,
        [_action()],
    ) == []


@pytest.mark.parametrize("status", ["PLANNED", "DRAFT", "MERGED", "ARCHIVED"])
def test_future_lifecycle_statuses_do_not_appear_as_active_modules(status: str):
    module = _registry_module(status=status, is_active=status not in {"PLANNED", "DRAFT", "ARCHIVED"})

    assert build_visible_module_items(
        [module],
        _platform_admin_with_future_permission(),
        ACTIVE_REGION,
        [_action()],
    ) == []


def test_widget_registry_can_register_future_widget_as_metadata_without_business_payload():
    widget = WidgetRegistryItem(
        widget_code=FUTURE_WIDGET_CODE,
        title="Future sandbox status",
        description="Test-only future widget metadata.",
        source_module_code=FUTURE_MODULE_CODE,
        canonical_module_code=FUTURE_MODULE_CODE,
        feature_code="FUTURE_SANDBOX_STATUS",
        widget_type="STATUS",
        required_access_level="VIEW",
        required_scope="GLOBAL",
        required_action_code="VIEW",
        default_size="small",
        allowed_sizes=["small", "medium"],
        status="PLANNED",
        is_system=True,
        is_mock=True,
    )

    assert widget.widget_code == FUTURE_WIDGET_CODE
    assert widget.source_module_code == FUTURE_MODULE_CODE
    assert widget.status == "PLANNED"
    assert not hasattr(widget, "source_module_number")
    assert not hasattr(widget, "business_payload")


def test_planned_future_widget_is_registered_for_preview_but_hidden_from_add_and_view():
    widget = get_widget_registry_item("quality-control-issues")
    user = {
        "userId": "platform-admin",
        "roleCode": "PLATFORM_ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedWidgetCodes": ["quality-control-issues"],
    }
    context = {
        "activeRegionCode": "KRASNODAR_KRAI",
        "userDashboardLayout": {"widgets": []},
    }

    assert widget is not None
    assert widget.sourceModuleCode == "MODULE_18_QUALITY_CONTROL"
    assert widget.status == "PLANNED"
    assert can_view_widget(user, "quality-control-issues", context) is False
    assert can_add_widget(user, "quality-control-issues", context) is False
    assert add_widget_to_layout(
        {"userId": "platform-admin", "activeRegionCode": "KRASNODAR_KRAI", "widgets": []},
        "quality-control-issues",
        user=user,
    )["widgets"] == []


def test_future_module_service_must_use_require_permission():
    def future_sandbox_service(user: dict) -> dict:
        require_permission(user, FUTURE_MODULE_CODE, "VIEW", "GLOBAL")
        return {"moduleCode": FUTURE_MODULE_CODE, "status": "ok"}

    with pytest.raises(ForbiddenError):
        future_sandbox_service({"userId": "viewer", "roleCode": "VIEWER"})

    assert future_sandbox_service(_platform_admin_with_future_permission()) == {
        "moduleCode": FUTURE_MODULE_CODE,
        "status": "ok",
    }
    assert can(_platform_admin_with_future_permission(), FUTURE_MODULE_CODE, "VIEW", "GLOBAL")


def test_extensibility_changes_are_audited():
    write_audit_event_mock(
        {
            "eventType": AuditLogType.PLATFORM_MODULE_REGISTRY_CHANGED,
            "moduleCode": FUTURE_MODULE_CODE,
            "canonicalModuleCode": FUTURE_MODULE_CODE,
            "newValue": {"status": "PLANNED"},
            "reason": "Future module registered for extensibility test.",
        }
    )
    record_widget_registry_change(
        widget_code=FUTURE_WIDGET_CODE,
        module_code=FUTURE_MODULE_CODE,
        canonical_module_code=FUTURE_MODULE_CODE,
        new_value={"status": "PLANNED"},
    )
    record_dashboard_layout_change(
        user={"userId": "platform-admin"},
        old_layout={"widgets": []},
        new_layout={"widgets": [{"widgetCode": FUTURE_WIDGET_CODE, "isVisible": False}]},
        reason="Future widget layout compatibility check.",
    )

    event_types = {event["eventType"] for event in MOCK_AUDIT_EVENTS}
    assert AuditLogType.PLATFORM_MODULE_REGISTRY_CHANGED in event_types
    assert AuditLogType.WIDGET_REGISTRY_CHANGED in event_types
    assert AuditLogType.USER_DASHBOARD_LAYOUT_CHANGED in event_types
