import asyncio
from app.services.dashboard_cabinet_context import get_current_cabinet_context
from app.services import dashboard_quick_actions as dashboard_service
from app.services.dashboard_quick_actions import (
    get_atom_card_quick_action_options,
    get_quick_actions_for_dashboard,
)
from app.services.user_module_quick_actions import MAX_ATOM_CARD_PINNED_ACTIONS


def test_dashboard_quick_actions_do_not_use_fixed_registry_presets():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["SAMPLE_OPEN_LIST"],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    assert cabinet_context["cabinetDashboardPreset"]["quickActionCodes"] == []
    assert get_quick_actions_for_dashboard(user_context, cabinet_context) == []


def test_atom_card_quick_actions_require_user_selected_actions():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["SAMPLE_OPEN_LIST"],
    }
    cabinet_context = get_current_cabinet_context(user_context).to_dict()

    assert get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
    ) == []
    assert get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
        selected_action_codes=["SAMPLE_OPEN_LIST"],
    ) == []


def test_dashboard_quick_action_legacy_contract_is_empty_and_limited_to_three():
    assert dashboard_service.QUICK_ACTION_REGISTRY == ()
    assert dashboard_service.DEFAULT_ATOM_CARD_ACTION_CODES == {}
    assert dashboard_service.ATOM_CARD_QUICK_ACTION_LIMIT == MAX_ATOM_CARD_PINNED_ACTIONS == 3


def test_dashboard_ignores_preset_quick_action_codes_without_user_saved_source():
    user_context = {
        "roleCode": "ADMIN",
        "activeRegionCode": "KRASNODAR_KRAI",
        "allowedActionCodes": ["LEGACY_FIXED_ACTION"],
    }
    cabinet_context = {
        "cabinetDashboardPreset": {
            "quickActionCodes": ["LEGACY_FIXED_ACTION"],
        }
    }

    assert get_quick_actions_for_dashboard(user_context, cabinet_context) == []
    assert get_atom_card_quick_action_options(
        user_context,
        cabinet_context,
        "MODULE_01_MATERIAL_HUB",
        selected_action_codes=["LEGACY_FIXED_ACTION"],
    ) == []

import uuid
from types import SimpleNamespace


MODULE_CODE = "MODULE_01_MATERIAL_HUB"
USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000202")


class _FakeScalarResult:
    def __init__(self, actions):
        self._actions = actions

    def all(self):
        return self._actions


class _FakeExecuteResult:
    def __init__(self, actions):
        self._actions = actions

    def scalars(self):
        return _FakeScalarResult(self._actions)


class _FakeDb:
    def __init__(self, actions):
        self.actions = actions
        self.executed = False

    async def execute(self, statement):
        self.executed = True
        self.statement = statement
        return _FakeExecuteResult(self.actions)


def _dashboard_user(**overrides):
    data = {
        "userId": str(USER_ID),
        "roleCode": "ADMIN",
        "authMode": "mock",
        "allowedModuleCodes": [MODULE_CODE],
        "allowedActionCodes": [],
    }
    data.update(overrides)
    return data


def _action(**overrides):
    data = {
        "id": uuid.uuid4(),
        "user_id": USER_ID,
        "source_module_code": MODULE_CODE,
        "feature_code": None,
        "action_key": "VIEW",
        "title": "Open materials",
        "icon": "+",
        "route": "/api/v1/admin/material-hub/view",
        "deep_link": None,
        "config_snapshot": {},
        "is_pinned_to_atom_card": True,
        "atom_card_order": 1,
        "atom_card_accent": "cyan",
        "status": "ACTIVE",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_dashboard_atom_card_actions_come_from_user_module_quick_actions():
    db = _FakeDb([_action()])

    actions = asyncio.run(dashboard_service.get_user_atom_card_quick_action_options(db, _dashboard_user(), MODULE_CODE))

    assert db.executed is True
    assert len(actions) == 1
    assert actions[0]["quickActionId"]
    assert actions[0]["actionCode"] == "VIEW"
    assert actions[0]["label"] == "Open materials"
    assert actions[0]["href"] == "/api/v1/admin/material-hub/view"
    assert actions[0]["moduleCode"] == MODULE_CODE
    assert actions[0]["isSelected"] is True
    assert actions[0]["placement"] == "ATOM_CARD"


def test_dashboard_atom_card_actions_filter_owner_pin_status_module_and_limit():
    valid = [_action(title=f"Action {index}", atom_card_order=index) for index in range(1, 5)]
    db = _FakeDb([
        _action(user_id=OTHER_USER_ID, title="Other user"),
        _action(is_pinned_to_atom_card=False, title="Unpinned"),
        _action(status="DISABLED", title="Disabled"),
        _action(source_module_code="MODULE_11_ANALYTICS", title="Other module"),
        *valid,
    ])

    actions = asyncio.run(dashboard_service.get_user_atom_card_quick_action_options(db, _dashboard_user(), MODULE_CODE))

    assert [action["label"] for action in actions] == ["Action 1", "Action 2", "Action 3"]


def test_dashboard_atom_card_actions_require_module_access_without_query():
    db = _FakeDb([_action()])

    actions = asyncio.run(dashboard_service.get_user_atom_card_quick_action_options(
        db,
        _dashboard_user(allowedModuleCodes=[]),
        MODULE_CODE,
    ))

    assert actions == []
    assert db.executed is False


def test_dashboard_atom_card_actions_ignore_non_uuid_mock_user_without_query():
    db = _FakeDb([_action()])

    actions = asyncio.run(dashboard_service.get_user_atom_card_quick_action_options(
        db,
        _dashboard_user(userId="dev-admin-mock"),
        MODULE_CODE,
    ))

    assert actions == []
    assert db.executed is False
