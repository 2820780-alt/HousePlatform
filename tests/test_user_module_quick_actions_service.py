import asyncio
import uuid

import pytest

from app.core.exceptions import ForbiddenError, ValidationError
from app.models.user_module_quick_action import UserModuleQuickAction
from app.services import user_module_quick_actions as service


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ACTION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MODULE_CODE = "MODULE_01_MATERIAL_HUB"


class FakeSession:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.flushed = False

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushed = True

    async def refresh(self, item):
        return None

    async def delete(self, item):
        self.deleted.append(item)


def run(coro):
    return asyncio.run(coro)


def async_value(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


def _action(**overrides):
    data = {
        "id": ACTION_ID,
        "user_id": USER_ID,
        "source_module_code": MODULE_CODE,
        "action_key": "RUN_SOURCE_ANALYSIS",
        "title": "Запустить анализ",
        "route": "/modules/material-hub/source-analysis",
        "status": "ACTIVE",
        "is_pinned_to_atom_card": False,
        "atom_card_order": None,
        "order": 1,
    }
    data.update(overrides)
    return UserModuleQuickAction(**data)


def _request(**overrides):
    data = {
        "userId": str(USER_ID),
        "sourceModuleCode": MODULE_CODE,
        "featureCode": "SOURCE_ANALYSIS",
        "actionKey": "RUN_SOURCE_ANALYSIS",
        "title": "Запустить анализ",
        "route": "/modules/material-hub/source-analysis",
    }
    data.update(overrides)
    return data


def _context(**overrides):
    data = {
        "userId": str(USER_ID),
        "sourceModuleCode": MODULE_CODE,
    }
    data.update(overrides)
    return data


def test_add_user_module_quick_action_creates_user_owned_shortcut(monkeypatch):
    fake_db = FakeSession()
    monkeypatch.setattr(service, "_active_count", async_value(2))
    monkeypatch.setattr(service, "_pinned_count", async_value(1))
    monkeypatch.setattr(service, "_next_order", async_value(3))
    monkeypatch.setattr(service, "_next_atom_card_order", async_value(2))

    action = run(
        service.addUserModuleQuickAction(
            fake_db,
            _request(
                savedConfigRef="source-analysis:lemana",
                configSnapshot={"scenario": "initial_fill", "regionCode": "KRASNODAR_KRAI"},
                pinToAtomCard=True,
                atomCardAccent="cyan",
            ),
            _context(),
        )
    )

    assert action.user_id == USER_ID
    assert action.source_module_code == MODULE_CODE
    assert action.action_key == "RUN_SOURCE_ANALYSIS"
    assert action.saved_config_ref == "source-analysis:lemana"
    assert action.is_pinned_to_atom_card is True
    assert action.atom_card_order == 2
    assert action.order == 3
    assert fake_db.added == [action]
    assert fake_db.flushed is True


def test_add_user_module_quick_action_limits_nine_actions_per_module(monkeypatch):
    monkeypatch.setattr(service, "_active_count", async_value(service.MAX_MODULE_QUICK_ACTIONS))

    with pytest.raises(ValidationError) as exc:
        run(service.addUserModuleQuickAction(FakeSession(), _request(), _context()))

    assert "9 быстрых действий" in exc.value.detail


def test_add_user_module_quick_action_limits_three_pinned_actions(monkeypatch):
    monkeypatch.setattr(service, "_active_count", async_value(1))
    monkeypatch.setattr(service, "_pinned_count", async_value(service.MAX_ATOM_CARD_PINNED_ACTIONS))

    with pytest.raises(ValidationError) as exc:
        run(
            service.addUserModuleQuickAction(
                FakeSession(),
                _request(pinToAtomCard=True),
                _context(),
            )
        )

    assert "не более 3" in exc.value.detail


def test_add_user_module_quick_action_rejects_business_payload_snapshot(monkeypatch):
    monkeypatch.setattr(service, "_active_count", async_value(0))

    with pytest.raises(ValidationError) as exc:
        run(
            service.addUserModuleQuickAction(
                FakeSession(),
                _request(configSnapshot={"filters": {"rawData": [{"id": 1}]}}),
                _context(),
            )
        )

    assert "business/raw payload" in exc.value.detail


def test_add_user_module_quick_action_cannot_cross_module_boundary():
    with pytest.raises(ForbiddenError):
        run(
            service.addUserModuleQuickAction(
                FakeSession(),
                _request(sourceModuleCode="MODULE_02_KNOWLEDGE_BASE"),
                _context(sourceModuleCode=MODULE_CODE),
            )
        )


def test_add_user_module_quick_action_requires_owner_module_context():
    with pytest.raises(ForbiddenError) as exc:
        run(service.addUserModuleQuickAction(FakeSession(), _request(), {"userId": str(USER_ID)}))

    assert "Module owner context" in exc.value.detail


def test_remove_user_module_quick_action_unpins_before_delete(monkeypatch):
    fake_db = FakeSession()
    action = _action(is_pinned_to_atom_card=True, atom_card_order=1)
    monkeypatch.setattr(service, "_get_action", async_value(action))
    monkeypatch.setattr(service, "_compact_module_order", async_value(None))
    monkeypatch.setattr(service, "_compact_pinned_order", async_value(None))

    run(service.removeUserModuleQuickAction(fake_db, ACTION_ID, _context()))

    assert action.is_pinned_to_atom_card is False
    assert action.atom_card_order is None
    assert fake_db.deleted == [action]
    assert fake_db.flushed is True


def test_reset_user_module_quick_actions_deletes_module_actions_and_unpins(monkeypatch):
    fake_db = FakeSession()
    first = _action(id=uuid.UUID("22222222-2222-2222-2222-222222222221"), is_pinned_to_atom_card=True, atom_card_order=1)
    second = _action(id=uuid.UUID("22222222-2222-2222-2222-222222222223"), order=2)
    monkeypatch.setattr(service, "getUserModuleQuickActions", async_value([first, second]))

    removed = run(service.resetUserModuleQuickActions(fake_db, USER_ID, MODULE_CODE, _context()))

    assert removed == 2
    assert first.is_pinned_to_atom_card is False
    assert first.atom_card_order is None
    assert fake_db.deleted == [first, second]
    assert fake_db.flushed is True


def test_reset_atom_card_pinned_quick_actions_only_unpins(monkeypatch):
    fake_db = FakeSession()
    first = _action(id=uuid.UUID("22222222-2222-2222-2222-222222222221"), is_pinned_to_atom_card=True, atom_card_order=1)
    second = _action(id=uuid.UUID("22222222-2222-2222-2222-222222222223"), is_pinned_to_atom_card=True, atom_card_order=2)
    monkeypatch.setattr(service, "getAtomCardPinnedActions", async_value([first, second]))

    unpinned = run(service.resetAtomCardPinnedQuickActions(fake_db, USER_ID, MODULE_CODE, _context()))

    assert unpinned == 2
    assert first.is_pinned_to_atom_card is False
    assert first.atom_card_order is None
    assert second.is_pinned_to_atom_card is False
    assert second.atom_card_order is None
    assert fake_db.added == [first, second]
    assert fake_db.deleted == []
    assert fake_db.flushed is True


def test_pin_quick_action_to_atom_card_respects_pinned_limit(monkeypatch):
    action = _action(is_pinned_to_atom_card=False)
    monkeypatch.setattr(service, "_get_action", async_value(action))
    monkeypatch.setattr(service, "_pinned_count", async_value(service.MAX_ATOM_CARD_PINNED_ACTIONS))

    with pytest.raises(ValidationError) as exc:
        run(service.pinQuickActionToAtomCard(FakeSession(), ACTION_ID, _context()))

    assert "не более 3" in exc.value.detail


def test_validate_quick_action_blocks_broken_config(monkeypatch):
    action = _action(saved_config_ref="source-analysis:old-config")
    monkeypatch.setattr(service, "_get_action", async_value(action))

    result = run(
        service.validateQuickActionBeforeRun(
            FakeSession(),
            ACTION_ID,
            _context(brokenConfigRefs=["source-analysis:old-config"]),
        )
    )

    assert result.status == "BLOCKED"
    assert result.state == "BROKEN_CONFIG"
    assert result.requiresModuleHandler is True


def test_validate_quick_action_returns_loading_state_without_crashing(monkeypatch):
    action = _action(status="LOADING")
    monkeypatch.setattr(service, "_get_action", async_value(action))

    result = run(service.validateQuickActionBeforeRun(FakeSession(), ACTION_ID, _context()))

    assert result.status == "LOADING"
    assert result.state == "LOADING"
    assert "обновляется" in result.message
    assert result.requiresModuleHandler is True


def test_validate_quick_action_blocks_error_state_without_business_result(monkeypatch):
    action = _action(status="ERROR")
    monkeypatch.setattr(service, "_get_action", async_value(action))

    result = run(service.runUserQuickAction(FakeSession(), ACTION_ID, _context()))

    assert result.status == "BLOCKED"
    assert result.state == "ERROR"
    assert "Не удалось подготовить" in result.message
    assert result.resultRef is None


def test_atom_card_pinned_payload_keeps_disabled_state_for_dashboard(monkeypatch):
    action = _action(
        status="BROKEN_CONFIG",
        is_pinned_to_atom_card=True,
        atom_card_order=1,
        atom_card_accent="orange",
        saved_config_ref="source-analysis:old-config",
    )
    monkeypatch.setattr(service, "getAtomCardPinnedActions", async_value([action]))

    payloads = run(service.getAtomCardPinnedActionPayloads(FakeSession(), USER_ID, MODULE_CODE, _context()))

    assert payloads == [
        {
            "quickActionId": str(ACTION_ID),
            "sourceModuleCode": MODULE_CODE,
            "featureCode": None,
            "actionKey": "RUN_SOURCE_ANALYSIS",
            "title": "Запустить анализ",
            "icon": None,
            "route": "/modules/material-hub/source-analysis",
            "deepLink": None,
            "savedConfigRef": "source-analysis:old-config",
            "atomCardOrder": 1,
            "atomCardAccent": "orange",
            "status": "BROKEN_CONFIG",
            "isDisabled": True,
            "isLoading": False,
            "isError": False,
            "placement": "ATOM_CARD",
            "tooltip": "Настройки этого быстрого действия устарели. Откройте модуль и настройте действие заново.",
        }
    ]


def test_atom_card_pinned_payload_marks_loading_and_error_states():
    loading = _action(
        id=uuid.UUID("22222222-2222-2222-2222-222222222221"),
        status="LOADING",
        is_pinned_to_atom_card=True,
        atom_card_order=1,
    )
    error = _action(
        id=uuid.UUID("22222222-2222-2222-2222-222222222223"),
        status="ERROR",
        is_pinned_to_atom_card=True,
        atom_card_order=2,
    )

    loading_payload = service._atom_card_payload(loading)
    error_payload = service._atom_card_payload(error)

    assert loading_payload["isDisabled"] is True
    assert loading_payload["isLoading"] is True
    assert loading_payload["isError"] is False
    assert "обновляется" in loading_payload["tooltip"]
    assert error_payload["isDisabled"] is True
    assert error_payload["isLoading"] is False
    assert error_payload["isError"] is True
    assert "Не удалось подготовить" in error_payload["tooltip"]


def test_run_user_quick_action_returns_module_handler_not_business_result(monkeypatch):
    action = _action(route="/modules/material-hub/source-analysis")
    monkeypatch.setattr(service, "_get_action", async_value(action))

    result = run(service.runUserQuickAction(FakeSession(), ACTION_ID, _context()))

    assert result.status == "OPEN_MODULE_HANDLER"
    assert result.sourceModuleCode == MODULE_CODE
    assert result.actionKey == "RUN_SOURCE_ANALYSIS"
    assert result.route == "/modules/material-hub/source-analysis"
    assert result.resultRef is None
    assert result.requiresModuleHandler is True
