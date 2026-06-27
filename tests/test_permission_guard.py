import pytest

from app.core.exceptions import ForbiddenError
from app.core.permission_guard import (
    DEV_USER,
    can,
    canonical_module_code,
    requireOwnResource,
    requirePermission,
    require_own_resource,
    require_permission,
    required_access_level_for_action,
)
from app.models import ModuleAccess, User
from app.models.enums import UserRole


def test_can_uses_role_matrix_with_module_code_not_module_number():
    user = {"roleCode": "SUPPLIER"}

    assert can(user, "MODULE_01_MATERIAL_HUB", "VIEW", "LIMITED")
    assert can(user, "MODULE_01_MATERIAL_HUB", "EDIT", "LIMITED") is False
    assert can(user, "MODULE_11_ANALYTICS", "VIEW", "OWN")


def test_legacy_admin_role_maps_to_platform_admin_for_current_auth_placeholder():
    user = User(email="admin@example.com", password_hash="x", role=UserRole.ADMIN)

    assert can(user, "MODULE_01_MATERIAL_HUB", "EDIT", "GLOBAL")
    assert can(user, "MODULE_03_USERS_ROLES", "EDIT", "GLOBAL")
    assert can(user, "MODULE_03_USERS_ROLES", "ADMIN", "GLOBAL") is False


def test_aliases_are_normalized_before_permission_check():
    customer = {"roleCode": "CUSTOMER"}

    assert canonical_module_code("MODULE_05_ESTIMATES") == "MODULE_05_ESTIMATE_ENGINE"
    assert can(customer, "MODULE_05_ESTIMATES", "VIEW", "OWN")
    assert can(customer, "MODULE_05_ESTIMATE_ENGINE", "VIEW", "OWN")
    assert can(customer, "MODULE_09_PROCUREMENT", "VIEW", "OWN")


def test_default_registration_permissions_cover_future_modules():
    assert can(DEV_USER, "MODULE_18_QUALITY_CONTROL", "ADMIN", "GLOBAL")
    assert can({"roleCode": "MODERATOR"}, "MODULE_18_QUALITY_CONTROL", "APPROVE_CHECK", "GLOBAL")
    assert can({"roleCode": "CUSTOMER"}, "MODULE_18_QUALITY_CONTROL", "VIEW", "OWN")
    assert can({"roleCode": "CUSTOMER"}, "MODULE_18_QUALITY_CONTROL", "EDIT", "OWN") is False
    assert can({"roleCode": "SUPER_ADMIN"}, "MODULE_16_QUALITY_CONTROL", "ADMIN", "GLOBAL")


def test_explicit_no_access_overrides_role_matrix():
    user = {
        "roleCode": "SUPER_ADMIN",
        "moduleAccessRules": [
            {
                "moduleCode": "MODULE_01_MATERIAL_HUB",
                "accessLevel": "NO_ACCESS",
                "accessScope": "NONE",
            }
        ],
    }

    assert can(user, "MODULE_01_MATERIAL_HUB", "VIEW", "GLOBAL") is False


def test_model_module_access_rules_can_grant_module_permissions():
    user = {
        "roleCode": "VIEWER",
        "module_access": [
            ModuleAccess(
                module_code="MODULE_18_QUALITY_CONTROL",
                canonical_module_code="MODULE_18_QUALITY_CONTROL",
                access_level="EDIT",
                access_scope="OWN",
            )
        ],
    }

    assert can(user, "MODULE_18_QUALITY_CONTROL", "EDIT", "OWN")
    assert can(user, "MODULE_18_QUALITY_CONTROL", "EDIT", "GLOBAL") is False


def test_require_permission_raises_for_denied_access():
    user = {"roleCode": "SUPPLIER"}

    assert require_permission(user, "MODULE_01_MATERIAL_HUB", "VIEW", "LIMITED") == user
    assert requirePermission(user, "MODULE_01_MATERIAL_HUB", "VIEW", "LIMITED") == user
    with pytest.raises(ForbiddenError):
        require_permission(user, "MODULE_01_MATERIAL_HUB", "ADMIN", "GLOBAL")


def test_require_own_resource_checks_common_owner_fields():
    user = {"userId": "user-1", "roleCode": "CUSTOMER"}

    resource = {"owner_id": "user-1"}
    assert require_own_resource(user, resource) == resource
    assert requireOwnResource(user, resource) == resource

    with pytest.raises(ForbiddenError):
        require_own_resource(user, {"owner_id": "user-2"})


def test_unknown_custom_action_requires_admin_by_default():
    assert required_access_level_for_action("EXPORT_REPORT") == "VIEW"
    assert required_access_level_for_action("CREATE_ISSUE") == "CREATE"
    assert required_access_level_for_action("SOMETHING_CUSTOM") == "ADMIN"
