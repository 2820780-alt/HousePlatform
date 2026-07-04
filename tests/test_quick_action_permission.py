import pytest

from app.core.exceptions import ForbiddenError
from app.services.quick_action_permission import (
    canUseQuickAction,
    can_use_quick_action,
    can_use_quick_action_item,
    filterAllowedQuickActions,
    filter_allowed_quick_action_items,
    filter_allowed_quick_actions,
    requireQuickActionPermission,
    require_quick_action_permission,
)


SAMPLE_MODULE_QUICK_ACTIONS = [
    {
        "quickActionCode": "SAMPLE_OPEN_LIST",
        "sourceModuleCode": "MODULE_TEST_SAMPLE",
        "featureCode": "SAMPLE",
        "sectionCode": "LIST",
        "actionCode": "OPEN_LIST",
        "titleRu": "Открыть список",
        "actionType": "navigate",
        "targetRoute": "/modules/sample/list",
        "requiredPermission": "sample.read",
        "isEnabledByDefault": False,
        "isAvailable": True,
        "maxSurface": "BOTH",
        "sortOrder": 10,
    },
    {
        "quickActionCode": "SAMPLE_ARCHIVED_ACTION",
        "sourceModuleCode": "MODULE_TEST_SAMPLE",
        "featureCode": "SAMPLE",
        "sectionCode": "LEGACY",
        "actionCode": "OPEN_ARCHIVED",
        "titleRu": "Архивное действие",
        "actionType": "navigate",
        "targetRoute": "/modules/sample/legacy",
        "requiredPermission": "sample.read",
        "isEnabledByDefault": False,
        "isAvailable": False,
        "status": "DISABLED",
        "maxSurface": "BOTH",
        "sortOrder": 20,
    },
]


def _user(**overrides):
    data = {
        "userId": "user-1",
        "roleCode": "PLATFORM_ADMIN",
        "authMode": "mock",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["SAMPLE_OPEN_LIST", "SAMPLE_ARCHIVED_ACTION"],
        "allowedFeatureCodes": ["DASHBOARD_PERSONALIZE", "PRICE_DYNAMICS"],
        "moduleAccessRules": [
            {
                "moduleCode": "MODULE_TEST_SAMPLE",
                "accessLevel": "VIEW",
                "accessScope": "GLOBAL",
            }
        ],
    }
    data.update(overrides)
    return data


def _context(**overrides):
    data = {
        "activeRegionCode": "KRASNODAR_KRAI",
        "roleCode": "PLATFORM_ADMIN",
        "activeCabinetType": "ADMIN",
    }
    data.update(overrides)
    return data


def test_registry_code_shortcuts_are_not_allowed_when_not_user_saved_items():
    assert not can_use_quick_action(_user(), "SAMPLE_OPEN_LIST", _context())
    assert not canUseQuickAction(_user(), "SAMPLE_OPEN_LIST", _context())
    assert filter_allowed_quick_actions(_user(), [{"quickActionCode": "SAMPLE_OPEN_LIST"}], _context()) == []
    assert filterAllowedQuickActions(_user(), [{"quickActionCode": "SAMPLE_OPEN_LIST"}], _context()) == []


def test_require_quick_action_permission_raises_for_empty_registry():
    with pytest.raises(ForbiddenError):
        require_quick_action_permission("SAMPLE_OPEN_LIST", _context(), user=_user())

    with pytest.raises(ForbiddenError):
        requireQuickActionPermission("SAMPLE_OPEN_LIST", {**_context(), "user": _user()})


def test_user_saved_quick_action_items_filter_by_permissions_without_registry_presets():
    assert can_use_quick_action_item(_user(), SAMPLE_MODULE_QUICK_ACTIONS[0], _context())
    assert not can_use_quick_action_item(_user(), SAMPLE_MODULE_QUICK_ACTIONS[1], _context())
    assert filter_allowed_quick_action_items(_user(), SAMPLE_MODULE_QUICK_ACTIONS, _context()) == [
        SAMPLE_MODULE_QUICK_ACTIONS[0],
    ]


def test_user_saved_quick_action_item_requires_region_and_user_allowed_code():
    assert not can_use_quick_action_item(
        _user(activeRegionCode=None),
        SAMPLE_MODULE_QUICK_ACTIONS[0],
        _context(activeRegionCode=None),
    )
    assert not can_use_quick_action_item(
            _user(allowedActionCodes=["OTHER_ACTION"]),
        SAMPLE_MODULE_QUICK_ACTIONS[0],
        _context(),
    )


def test_user_saved_quick_action_item_requires_module_permission():
    denied_user = _user(
        moduleAccessRules=[
            {
                "moduleCode": "MODULE_TEST_SAMPLE",
                "accessLevel": "NO_ACCESS",
                "accessScope": "GLOBAL",
            }
        ],
    )
    assert not can_use_quick_action_item(denied_user, SAMPLE_MODULE_QUICK_ACTIONS[0], _context())

    disabled_context = _context(disabledModuleCodes=["MODULE_TEST_SAMPLE"])
    assert not can_use_quick_action_item(_user(), SAMPLE_MODULE_QUICK_ACTIONS[0], disabled_context)
