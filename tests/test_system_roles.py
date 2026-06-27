from app.core.system_roles import (
    SYSTEM_ROLE_CODES,
    can_delete_role_code,
    can_rename_role_code,
    get_system_role_definitions,
    get_system_role_codes,
    is_system_role_code,
)
from app.models import Role


def test_system_role_codes_match_module03_sprint8_contract():
    assert get_system_role_codes() == (
        "SUPER_ADMIN",
        "PLATFORM_ADMIN",
        "MODERATOR",
        "KNOWLEDGE_MANAGER",
        "ESTIMATOR",
        "ENGINEER_DESIGNER",
        "SUPPLIER",
        "CONTRACTOR",
        "CUSTOMER",
        "ANALYST",
        "VIEWER",
    )
    assert len(set(SYSTEM_ROLE_CODES)) == len(SYSTEM_ROLE_CODES)


def test_system_role_definitions_are_locked_but_permission_extendable():
    definitions = get_system_role_definitions()

    assert {role["roleCode"] for role in definitions} == set(SYSTEM_ROLE_CODES)
    assert all(role["isSystem"] is True for role in definitions)
    assert all(role["canDelete"] is False for role in definitions)
    assert all(role["canRenameCode"] is False for role in definitions)
    assert all(role["canDisable"] is False for role in definitions)
    assert all(role["canExtendPermissions"] is True for role in definitions)


def test_system_role_helpers_distinguish_legacy_and_custom_roles():
    assert is_system_role_code("PLATFORM_ADMIN")
    assert not is_system_role_code("ADMIN")
    assert not can_delete_role_code("SUPER_ADMIN")
    assert not can_rename_role_code("VIEWER")
    assert can_delete_role_code("CUSTOM_COMPANY_ROLE")
    assert can_rename_role_code("CUSTOM_COMPANY_ROLE")


def test_role_model_can_store_system_role_lock_settings():
    role = Role(
        role_key="PLATFORM_ADMIN",
        name="Platform Admin",
        is_system=True,
        settings={
            "isSystemRole": True,
            "canDelete": False,
            "canRenameCode": False,
            "canDisable": False,
            "canExtendPermissions": True,
        },
    )

    assert role.role_key == "PLATFORM_ADMIN"
    assert role.is_system is True
    assert role.settings["canDelete"] is False
    assert role.settings["canExtendPermissions"] is True
