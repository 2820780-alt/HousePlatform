import uuid

import pytest

from app.api.v1.admin_users_roles_view import router as admin_users_roles_router
from app.core.exceptions import ForbiddenError, ValidationError
from app.models import Role, User, UserRoleAssignment
from app.models.enums import UserRole
from app.services.admin_user_role_management import (
    DISABLE_CONFIRMATION,
    active_permissions_for_user,
    active_role_codes_for_user,
    can_assign_role_code,
    can_disable_user,
    can_open_user_role_admin,
    require_can_assign_role,
    require_can_disable_user,
)


def _user(role=UserRole.ADMIN) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        role=role,
    )


def _user_with_assignment(role_code: str) -> User:
    user = _user(UserRole.CUSTOMER)
    role = Role(role_key=role_code, name=role_code, is_system=True)
    user.role_assignments = [
        UserRoleAssignment(
            id=uuid.uuid4(),
            user_id=user.id,
            role_id=uuid.uuid4(),
            role=role,
            status="ACTIVE",
        )
    ]
    return user


def test_legacy_admin_is_platform_admin_not_super_admin():
    actor = _user(UserRole.ADMIN)

    assert active_role_codes_for_user(actor) == {"PLATFORM_ADMIN"}
    assert can_open_user_role_admin(actor)
    assert can_assign_role_code(actor, "MODERATOR")
    assert not can_assign_role_code(actor, "SUPER_ADMIN")

    with pytest.raises(ForbiddenError):
        require_can_assign_role(actor, "SUPER_ADMIN")


def test_super_admin_can_assign_protected_roles():
    actor = _user_with_assignment("SUPER_ADMIN")

    assert active_role_codes_for_user(actor) == {"CUSTOMER", "SUPER_ADMIN"}
    assert can_open_user_role_admin(actor)
    assert can_assign_role_code(actor, "SUPER_ADMIN")
    require_can_assign_role(actor, "SUPER_ADMIN")


def test_platform_admin_cannot_disable_super_admin():
    actor = _user(UserRole.ADMIN)
    target = _user_with_assignment("SUPER_ADMIN")

    assert not can_disable_user(actor, target)
    with pytest.raises(ForbiddenError):
        require_can_disable_user(actor, target, DISABLE_CONFIRMATION)


def test_disable_user_requires_explicit_confirmation():
    actor = _user_with_assignment("SUPER_ADMIN")
    target = _user(UserRole.SUPPLIER)

    with pytest.raises(ValidationError):
        require_can_disable_user(actor, target, "yes")
    require_can_disable_user(actor, target, DISABLE_CONFIRMATION)


def test_active_permissions_are_role_matrix_based_and_code_first():
    actor = _user(UserRole.ADMIN)
    permissions = active_permissions_for_user(actor)

    module_codes = {permission["moduleCode"] for permission in permissions}
    assert "MODULE_03_USERS_ROLES" in module_codes
    assert "MODULE_14_PRICE_HISTORY" not in module_codes
    assert all("moduleNumber" not in permission for permission in permissions)


def test_admin_users_roles_view_route_is_registered():
    paths = {route.path for route in admin_users_roles_router.routes}

    assert "/admin/users-roles/view" in paths
    assert "/admin/users-roles/view/users/{user_id}" in paths
