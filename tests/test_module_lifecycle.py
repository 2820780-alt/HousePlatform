from app.models import PlatformModuleRegistry
from app.services.module_lifecycle import (
    MODULE_LIFECYCLE_STATUSES,
    apply_module_lifecycle_state,
    can_physically_delete_module,
    can_transition_module_lifecycle,
    get_module_lifecycle_rule,
    get_module_lifecycle_rules,
    is_module_hidden_from_users,
    is_module_user_visible_status,
    module_lifecycle_validation_errors,
    normalize_module_status,
)


def _module(module_code: str = "MODULE_22_TEST", **overrides):
    data = {
        "module_code": module_code,
        "canonical_module_code": module_code,
        "title": module_code,
        "status": "ACTIVE",
        "is_active": True,
        "is_system": False,
        "is_visible_in_sidebar": True,
        "is_visible_on_dashboard": True,
        "is_visible_on_atom_map": True,
        "is_available_for_widgets": True,
    }
    data.update(overrides)
    return PlatformModuleRegistry(**data)


def test_module_lifecycle_statuses_are_explicit_and_documented():
    rules = get_module_lifecycle_rules()
    statuses = [rule["status"] for rule in rules]

    assert tuple(statuses) == MODULE_LIFECYCLE_STATUSES
    assert normalize_module_status("planned") == "PLANNED"
    assert normalize_module_status("DELETE") is None
    assert get_module_lifecycle_rule("MERGED").requiresMergedIntoModuleCode is True
    assert is_module_user_visible_status("ACTIVE")
    assert is_module_hidden_from_users("PLANNED")
    assert is_module_hidden_from_users("DRAFT")
    assert is_module_hidden_from_users("DISABLED")
    assert is_module_hidden_from_users("DEPRECATED")
    assert is_module_hidden_from_users("ARCHIVED")
    assert is_module_hidden_from_users("MERGED")


def test_non_active_lifecycle_statuses_force_module_hidden_from_user_surfaces():
    module = _module()

    apply_module_lifecycle_state(
        module,
        "DRAFT",
        visible_flags={
            "sidebar": True,
            "dashboard": True,
            "atomMap": True,
            "widgets": True,
        },
    )

    assert module.status == "DRAFT"
    assert module.is_active is False
    assert module.is_visible_in_sidebar is False
    assert module.is_visible_on_dashboard is False
    assert module.is_visible_on_atom_map is False
    assert module.is_available_for_widgets is False


def test_active_lifecycle_status_keeps_requested_visibility_flags():
    module = _module(status="DRAFT", is_active=False)

    apply_module_lifecycle_state(
        module,
        "ACTIVE",
        visible_flags={
            "sidebar": True,
            "dashboard": True,
            "atomMap": False,
            "widgets": True,
        },
    )

    assert module.status == "ACTIVE"
    assert module.is_active is True
    assert module.is_visible_in_sidebar is True
    assert module.is_visible_on_dashboard is True
    assert module.is_visible_on_atom_map is False
    assert module.is_available_for_widgets is True


def test_merged_lifecycle_requires_target_and_cannot_be_active_without_alias_context():
    module = _module(
        "MODULE_99_OLD",
        canonical_module_code="MODULE_99_OLD",
        merged_into_module_code=None,
        redirect_route=None,
    )

    assert not can_transition_module_lifecycle(module, "MERGED")
    assert "MERGED status requires merged_into_module_code." in module_lifecycle_validation_errors(module, "MERGED")

    module.merged_into_module_code = "MODULE_01_MATERIAL_HUB"
    module.redirect_route = "/modules/material-hub"
    assert can_transition_module_lifecycle(module, "MERGED")


def test_physical_delete_is_forbidden_for_system_modules_or_referenced_modules():
    system_module = _module("MODULE_03_USERS_ROLES", is_system=True)
    regular_module = _module("MODULE_22_TEST")

    assert not can_physically_delete_module(system_module)
    assert not can_physically_delete_module(
        regular_module,
        {
            "permissions": [{"count": 1}],
            "widgets": [],
            "dashboardLayouts": [],
            "auditNotes": [],
        },
    )
    assert can_physically_delete_module(
        regular_module,
        {
            "permissions": [],
            "widgets": [],
            "dashboardLayouts": [],
            "auditNotes": [],
        },
    )
