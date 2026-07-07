import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.v1 import api_router
from app.api.v1 import user_module_quick_actions as api
from app.core.exceptions import ForbiddenError
from app.models.user_module_quick_action import QuickActionRunResult


USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
ACTION_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
MODULE_CODE = "MODULE_01_MATERIAL_HUB"
ACTION_KEY = "RUN_SOURCE_ANALYSIS"


def run(coro):
    return asyncio.run(coro)


def _user(user_id=USER_ID, access_level="ADMIN"):
    return SimpleNamespace(
        id=user_id,
        roleCode=None,
        moduleAccessRules=[
            {
                "moduleCode": MODULE_CODE,
                "accessLevel": access_level,
                "accessScope": "GLOBAL",
            }
        ],
    )


def _action(**overrides):
    data = {
        "id": ACTION_ID,
        "user_id": USER_ID,
        "workspace_id": None,
        "active_region_code": None,
        "source_module_code": MODULE_CODE,
        "feature_code": "SOURCE_ANALYSIS",
        "action_key": ACTION_KEY,
        "title": "Run source analysis",
        "description": "Open saved source analysis",
        "icon": "search",
        "route": "/modules/material-hub/source-analysis",
        "deep_link": None,
        "saved_config_ref": "source-analysis:config-1",
        "config_snapshot": {"filters": {"regionCode": "KRASNODAR_KRAI"}},
        "order": 1,
        "is_visible_in_module_bar": True,
        "is_pinned_to_atom_card": False,
        "atom_card_order": None,
        "atom_card_accent": None,
        "status": "ACTIVE",
        "created_at": datetime(2026, 7, 5, 8, 57),
        "updated_at": datetime(2026, 7, 5, 8, 57),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_create_api_uses_current_user_source_module_and_action_key(monkeypatch):
    captured = {}

    async def fake_add(db, payload, context):
        captured["payload"] = payload
        captured["context"] = context
        return _action(
            user_id=uuid.UUID(payload["userId"]),
            source_module_code=payload["sourceModuleCode"],
            action_key=payload["actionKey"],
            title=payload["title"],
            config_snapshot=payload["configSnapshot"],
            is_pinned_to_atom_card=payload["pinToAtomCard"],
            atom_card_accent=payload["atomCardAccent"],
        )

    async def fake_update(db, quick_action_id, payload, context):
        captured["update_payload"] = payload
        captured["update_context"] = context
        return _action(
            atom_card_accent=payload["atomCardAccent"],
            atom_card_order=payload["atomCardOrder"],
            is_pinned_to_atom_card=True,
        )

    monkeypatch.setattr(api.quick_action_service, "addUserModuleQuickAction", fake_add)
    monkeypatch.setattr(api.quick_action_service, "updateUserModuleQuickAction", fake_update)

    result = run(
        api.create_user_module_quick_action(
            api.UserQuickActionCreateRequest(
                sourceModuleCode=MODULE_CODE,
                actionKey=ACTION_KEY,
                title="Run source analysis",
                route="/modules/material-hub/source-analysis",
                configSnapshot={"filters": {"regionCode": "KRASNODAR_KRAI"}},
                pinToAtomCard=True,
                atomCardAccent="cyan",
                atomCardOrder=2,
            ),
            object(),
            _user(),
        )
    )

    assert captured["payload"]["userId"] == str(USER_ID)
    assert captured["payload"]["sourceModuleCode"] == MODULE_CODE
    assert captured["payload"]["actionKey"] == ACTION_KEY
    assert captured["payload"]["configSnapshot"] == {"filters": {"regionCode": "KRASNODAR_KRAI"}}
    assert "quickActionCode" not in captured["payload"]
    assert captured["context"]["userId"] == str(USER_ID)
    assert captured["context"]["sourceModuleCode"] == MODULE_CODE
    assert captured["context"]["actionKey"] == ACTION_KEY
    assert captured["update_payload"] == {"atomCardAccent": "cyan", "atomCardOrder": 2}
    assert result["quickActionId"] == str(ACTION_ID)
    assert result["sourceModuleCode"] == MODULE_CODE
    assert result["actionKey"] == ACTION_KEY
    assert result["atomCardOrder"] == 2


def test_list_api_hides_inactive_actions_by_default(monkeypatch):
    async def fake_get(db, user_id, source_module_code, context):
        return [
            _action(id=uuid.UUID("22222222-2222-2222-2222-222222222221"), status="ACTIVE"),
            _action(id=uuid.UUID("22222222-2222-2222-2222-222222222223"), status="DISABLED"),
        ]

    monkeypatch.setattr(api.quick_action_service, "getUserModuleQuickActions", fake_get)

    active_only = run(api.list_user_module_quick_actions(object(), _user(), sourceModuleCode=MODULE_CODE))
    with_inactive = run(
        api.list_user_module_quick_actions(
            object(),
            _user(),
            sourceModuleCode=MODULE_CODE,
            includeInactive=True,
        )
    )

    assert [item["status"] for item in active_only] == ["ACTIVE"]
    assert [item["status"] for item in with_inactive] == ["ACTIVE", "DISABLED"]


def test_update_rename_remove_reorder_and_pin_api_call_user_service(monkeypatch):
    calls = []

    async def fake_update(db, quick_action_id, payload, context):
        calls.append(("update", str(quick_action_id), payload, context))
        return _action(**_payload_to_action_fields(payload))

    async def fake_remove(db, quick_action_id, context):
        calls.append(("remove", str(quick_action_id), context))

    async def fake_reorder(db, source_module_code, ordered_ids, context):
        calls.append(("reorder", source_module_code, [str(item) for item in ordered_ids], context))
        return [_action(id=item, order=index + 1) for index, item in enumerate(ordered_ids)]

    async def fake_unpin_atom(db, quick_action_id, context):
        calls.append(("unpin_atom", str(quick_action_id), context))
        return _action(is_pinned_to_atom_card=False, atom_card_order=None)

    monkeypatch.setattr(api.quick_action_service, "updateUserModuleQuickAction", fake_update)
    monkeypatch.setattr(api.quick_action_service, "removeUserModuleQuickAction", fake_remove)
    monkeypatch.setattr(api.quick_action_service, "reorderUserModuleQuickActions", fake_reorder)
    monkeypatch.setattr(api.quick_action_service, "unpinQuickActionFromAtomCard", fake_unpin_atom)

    run(api.rename_user_module_quick_action(ACTION_ID, api.UserQuickActionRenameRequest(title="New title"), object(), _user(), sourceModuleCode=MODULE_CODE))
    run(api.pin_user_module_quick_action_to_module_bar(ACTION_ID, object(), _user(), sourceModuleCode=MODULE_CODE))
    run(api.unpin_user_module_quick_action_from_module_bar(ACTION_ID, object(), _user(), sourceModuleCode=MODULE_CODE))
    run(
        api.pin_user_module_quick_action_to_atom_card(
            ACTION_ID,
            api.UserQuickActionPinAtomCardRequest(atomCardAccent="purple", atomCardOrder=2),
            object(),
            _user(),
            sourceModuleCode=MODULE_CODE,
        )
    )
    run(api.unpin_user_module_quick_action_from_atom_card(ACTION_ID, object(), _user(), sourceModuleCode=MODULE_CODE))
    run(
        api.reorder_user_module_quick_actions(
            api.UserQuickActionReorderRequest(sourceModuleCode=MODULE_CODE, orderedIds=[ACTION_ID]),
            object(),
            _user(),
        )
    )
    removed = run(api.remove_user_module_quick_action(ACTION_ID, object(), _user(), sourceModuleCode=MODULE_CODE))

    assert calls[0][0:3] == ("update", str(ACTION_ID), {"title": "New title"})
    assert calls[1][2] == {"isVisibleInModuleBar": True}
    assert calls[2][2] == {"isVisibleInModuleBar": False}
    assert calls[3][2] == {"atomCardAccent": "purple", "atomCardOrder": 2, "isPinnedToAtomCard": True}
    assert calls[4][0] == "unpin_atom"
    assert calls[5][0:3] == ("reorder", MODULE_CODE, [str(ACTION_ID)])
    assert calls[6][0:2] == ("remove", str(ACTION_ID))
    assert removed == {"removed": True, "quickActionId": str(ACTION_ID)}


def test_validate_and_run_api_check_rbac_before_service(monkeypatch):
    async def fail_if_called(*args, **kwargs):
        raise AssertionError("service must not run when RBAC denies access")

    monkeypatch.setattr(api.quick_action_service, "validateQuickActionBeforeRun", fail_if_called)

    request = api.UserQuickActionRunRequest(sourceModuleCode=MODULE_CODE, actionKey=ACTION_KEY)
    with pytest.raises(ForbiddenError):
        run(api.validate_user_module_quick_action_before_run(ACTION_ID, request, object(), _user(access_level="NO_ACCESS")))


def test_validate_and_run_api_passes_current_user_context(monkeypatch):
    calls = []

    async def fake_validate(db, quick_action_id, context):
        calls.append(("validate", str(quick_action_id), context))
        return QuickActionRunResult(
            status="READY",
            quickActionId=str(quick_action_id),
            sourceModuleCode=MODULE_CODE,
            actionKey=ACTION_KEY,
            route="/modules/material-hub/source-analysis",
        )

    async def fake_run(db, quick_action_id, context):
        calls.append(("run", str(quick_action_id), context))
        return QuickActionRunResult(
            status="OPEN_MODULE_HANDLER",
            quickActionId=str(quick_action_id),
            sourceModuleCode=MODULE_CODE,
            actionKey=ACTION_KEY,
            route="/modules/material-hub/source-analysis",
        )

    monkeypatch.setattr(api.quick_action_service, "validateQuickActionBeforeRun", fake_validate)
    monkeypatch.setattr(api.quick_action_service, "runUserQuickAction", fake_run)

    request = api.UserQuickActionRunRequest(
        sourceModuleCode=MODULE_CODE,
        actionKey=ACTION_KEY,
        disabledModuleCodes=["MODULE_99_DISABLED"],
        availableActionKeys=[ACTION_KEY],
        brokenConfigRefs=["old-config"],
    )

    validation = run(api.validate_user_module_quick_action_before_run(ACTION_ID, request, object(), _user()))
    result = run(api.run_user_module_quick_action(ACTION_ID, request, object(), _user()))

    assert validation["status"] == "READY"
    assert result["status"] == "OPEN_MODULE_HANDLER"
    assert calls[0][2]["userId"] == str(USER_ID)
    assert calls[0][2]["sourceModuleCode"] == MODULE_CODE
    assert calls[0][2]["actionKey"] == ACTION_KEY
    assert calls[0][2]["disabledModuleCodes"] == ["MODULE_99_DISABLED"]
    assert calls[0][2]["availableActionKeys"] == [ACTION_KEY]
    assert calls[0][2]["brokenConfigRefs"] == ["old-config"]
    assert [call[0] for call in calls] == ["validate", "validate", "run"]


def test_api_routes_are_registered_without_quick_action_code_contract():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app/api/v1/user_module_quick_actions.py").read_text(encoding="utf-8")
    init_source = (root / "app/api/v1/__init__.py").read_text(encoding="utf-8")
    paths = {route.path for route in api.router.routes}

    assert "user_module_quick_actions" in init_source
    assert "api_router.include_router(user_module_quick_actions.router)" in init_source
    assert "/quick-actions/user-module" in paths
    assert "/quick-actions/user-module/{quick_action_id}/rename" in paths
    assert "/quick-actions/user-module/{quick_action_id}/pin-module-bar" in paths
    assert "/quick-actions/user-module/{quick_action_id}/pin-atom-card" in paths
    assert "/quick-actions/user-module/{quick_action_id}/validate" in paths
    assert "/quick-actions/user-module/{quick_action_id}/run" in paths
    assert "quickActionCode" not in source


def _payload_to_action_fields(payload):
    fields = {}
    if "title" in payload:
        fields["title"] = payload["title"]
    if "order" in payload:
        fields["order"] = payload["order"]
    if "isVisibleInModuleBar" in payload:
        fields["is_visible_in_module_bar"] = payload["isVisibleInModuleBar"]
    if "isPinnedToAtomCard" in payload:
        fields["is_pinned_to_atom_card"] = payload["isPinnedToAtomCard"]
    if "atomCardOrder" in payload:
        fields["atom_card_order"] = payload["atomCardOrder"]
    if "atomCardAccent" in payload:
        fields["atom_card_accent"] = payload["atomCardAccent"]
    return fields