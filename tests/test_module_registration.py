import pytest

from app.core.module_registration import (
    LEGACY_OR_CONFLICTING_MODULE_CODES,
    DefaultModulePermission,
    NewModuleRegistration,
    QUALITY_CONTROL_MODULE_REGISTRATION,
    registration_to_action_defaults,
    registration_to_module_access_defaults,
    registration_to_widget_defaults,
)
from app.models import PlatformModuleRegistry


def test_quality_control_registration_uses_canonical_module_code():
    registration = QUALITY_CONTROL_MODULE_REGISTRATION

    assert registration.moduleCode == "MODULE_18_QUALITY_CONTROL"
    assert registration.canonicalModuleCode == "MODULE_18_QUALITY_CONTROL"
    assert "MODULE_16_QUALITY_CONTROL" in LEGACY_OR_CONFLICTING_MODULE_CODES
    assert LEGACY_OR_CONFLICTING_MODULE_CODES["MODULE_16_QUALITY_CONTROL"] == "MODULE_18_QUALITY_CONTROL"


def test_new_module_registration_exports_code_first_defaults():
    registration = QUALITY_CONTROL_MODULE_REGISTRATION
    access_defaults = registration_to_module_access_defaults(registration)
    action_defaults = registration_to_action_defaults(registration)
    widget_defaults = registration_to_widget_defaults(registration)

    assert access_defaults
    assert all(rule["moduleCode"] == "MODULE_18_QUALITY_CONTROL" for rule in access_defaults)
    assert all("moduleNumber" not in rule for rule in access_defaults)
    assert {"moduleCode": "MODULE_18_QUALITY_CONTROL", "actionCode": "CREATE_ISSUE"} in action_defaults
    assert widget_defaults == [
        {"widgetCode": "QUALITY_CONTROL_ISSUES", "sourceModuleCode": "MODULE_18_QUALITY_CONTROL"}
    ]


def test_new_module_registration_rejects_legacy_or_conflicting_module_codes():
    with pytest.raises(ValueError, match="Use MODULE_18_QUALITY_CONTROL"):
        NewModuleRegistration(
            moduleCode="MODULE_16_QUALITY_CONTROL",
            title="Quality Control",
            defaultPermissions=(DefaultModulePermission("SUPER_ADMIN", "ADMIN", "GLOBAL"),),
            availableActions=("VIEW",),
        )


def test_new_module_registration_validates_role_access_and_scope():
    with pytest.raises(ValueError, match="Unknown system role"):
        DefaultModulePermission("ADMIN", "ADMIN", "GLOBAL")

    with pytest.raises(ValueError, match="Invalid access level"):
        DefaultModulePermission("SUPER_ADMIN", "VIEW_OWN", "GLOBAL")

    with pytest.raises(ValueError, match="Invalid access scope"):
        DefaultModulePermission("SUPER_ADMIN", "VIEW", "VIEW_OWN")


def test_platform_module_registry_supports_registration_metadata_fields():
    registry_item = PlatformModuleRegistry(
        module_code="MODULE_18_QUALITY_CONTROL",
        canonical_module_code="MODULE_18_QUALITY_CONTROL",
        title="Quality Control",
        status="PLANNED",
        default_permissions=[{"role": "SUPER_ADMIN", "accessLevel": "ADMIN", "scope": "GLOBAL"}],
        available_actions=["VIEW", "CREATE_ISSUE"],
        dashboard_widgets=["QUALITY_CONTROL_ISSUES"],
        owner_scope_rules={"ownerField": "workspaceId"},
    )

    assert registry_item.default_permissions[0]["role"] == "SUPER_ADMIN"
    assert registry_item.available_actions == ["VIEW", "CREATE_ISSUE"]
    assert registry_item.dashboard_widgets == ["QUALITY_CONTROL_ISSUES"]
    assert registry_item.owner_scope_rules == {"ownerField": "workspaceId"}
