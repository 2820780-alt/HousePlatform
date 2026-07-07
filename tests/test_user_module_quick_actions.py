from app.models import (
    ATOM_CARD_ACCENTS,
    USER_MODULE_QUICK_ACTION_STATUSES,
    AddUserQuickActionRequest,
    QuickActionCandidate,
    QuickActionRunContext,
    QuickActionRunResult,
    UpdateUserQuickActionRequest,
    UserModuleQuickAction,
)
from app.services.quick_action_preferences import (
    MAX_MODULE_BAR_QUICK_ACTIONS,
    MAX_MODULE_CARD_QUICK_ACTIONS,
    build_user_quick_action_preference,
    select_module_bar_preferences,
    select_module_card_preferences,
)
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_user_module_quick_action_model_is_user_owned_and_module_scoped():
    columns = UserModuleQuickAction.__table__.columns

    assert UserModuleQuickAction.__tablename__ == "user_module_quick_actions"
    assert columns["user_id"].nullable is False
    assert columns["source_module_code"].nullable is False
    assert columns["action_key"].nullable is False
    assert "saved_config_ref" in columns
    assert "config_snapshot" in columns
    assert "is_pinned_to_atom_card" in columns
    assert "atom_card_order" in columns
    assert "status" in columns
    assert "business_payload" not in columns
    assert "result_payload" not in columns


def test_user_module_quick_action_is_not_registry_or_widget_reference():
    columns = UserModuleQuickAction.__table__.columns

    assert "quick_action_code" not in columns
    assert "quickActionCode" not in columns
    assert "widget_code" not in columns
    assert "widgetCode" not in columns
    assert "source_module_code" in columns
    assert "action_key" in columns
    assert "user_id" in columns

def test_quick_action_contract_statuses_and_atom_accents_are_explicit():
    assert USER_MODULE_QUICK_ACTION_STATUSES == (
        "ACTIVE",
        "DISABLED",
        "BROKEN_CONFIG",
        "MODULE_DISABLED",
        "NO_LONGER_AVAILABLE",
        "LOADING",
        "ERROR",
    )
    assert "cyan" in ATOM_CARD_ACCENTS
    assert "purple" in ATOM_CARD_ACCENTS


def test_quick_action_state_migration_extends_database_constraint():
    sql = (ROOT / "database/migrations/20260630_user_module_quick_action_states.sql").read_text(encoding="utf-8")

    assert "ck_user_module_quick_action_status" in sql
    assert "'LOADING'" in sql
    assert "'ERROR'" in sql


def test_quick_action_candidate_is_declared_by_owning_module():
    candidate = QuickActionCandidate(
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        featureCode="SOURCE_ANALYSIS",
        actionKey="RUN_SOURCE_ANALYSIS",
        title="Запустить анализ",
        route="/api/v1/admin/material-hub/view",
        canPinToAtomCard=True,
        configMode="SAVED_CONFIG_REF",
        currentConfigRef="source-analysis:lemana:materials",
    ).to_dict()

    assert candidate["sourceModuleCode"] == "MODULE_01_MATERIAL_HUB"
    assert candidate["actionKey"] == "RUN_SOURCE_ANALYSIS"
    assert candidate["currentConfigRef"] == "source-analysis:lemana:materials"
    assert "quickActionCode" not in candidate


def test_add_update_and_run_types_keep_config_not_result_payload():
    request = AddUserQuickActionRequest(
        userId="user-1",
        workspaceId="workspace-1",
        activeRegionCode="KRASNODAR_KRAI",
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        featureCode="SOURCE_ANALYSIS",
        actionKey="RUN_SOURCE_ANALYSIS",
        title="Запустить анализ источника",
        savedConfigRef="source-analysis:config-1",
        pinToAtomCard=True,
    ).to_dict()
    update = UpdateUserQuickActionRequest(
        order=2,
        isVisibleInModuleBar=True,
        isPinnedToAtomCard=True,
        atomCardOrder=1,
        atomCardAccent="cyan",
    ).to_dict()
    context = QuickActionRunContext(
        userId="user-1",
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        actionKey="RUN_SOURCE_ANALYSIS",
        savedConfigRef="source-analysis:config-1",
    ).to_dict()
    result = QuickActionRunResult(
        status="OPEN_MODULE_HANDLER",
        sourceModuleCode="MODULE_01_MATERIAL_HUB",
        actionKey="RUN_SOURCE_ANALYSIS",
        route="/api/v1/admin/material-hub/view",
        message="Передано в модуль-владелец.",
    ).to_dict()

    assert request["userId"] == "user-1"
    assert request["sourceModuleCode"] == "MODULE_01_MATERIAL_HUB"
    assert request["actionKey"] == "RUN_SOURCE_ANALYSIS"
    assert update["atomCardAccent"] == "cyan"
    assert context["savedConfigRef"] == "source-analysis:config-1"
    assert result["requiresModuleHandler"] is True
    assert "businessPayload" not in request
    assert "resultPayload" not in result


def test_user_quick_action_preference_contract_is_module_scoped_and_limited():
    preferences = [
        build_user_quick_action_preference(
            user_id="user-1",
            quick_action_code=f"ACTION_{index}",
            source_module_code="MODULE_03_USERS_ROLES",
            is_enabled=True,
            is_pinned_in_module=True,
            is_pinned_on_module_card=True,
            sort_order=index,
        )
        for index in range(12)
    ]

    assert preferences[0]["userId"] == "user-1"
    assert preferences[0]["sourceModuleCode"] == "MODULE_03_USERS_ROLES"
    assert "moduleNumber" not in preferences[0]
    assert "businessPayload" not in preferences[0]
    assert len(select_module_bar_preferences(preferences)) == MAX_MODULE_BAR_QUICK_ACTIONS
    assert len(select_module_card_preferences(preferences)) == MAX_MODULE_CARD_QUICK_ACTIONS


def test_user_quick_action_preference_requires_source_module_code():
    try:
        build_user_quick_action_preference(
            user_id="user-1",
            quick_action_code="ACTION",
            source_module_code="",
        )
    except ValueError as exc:
        assert "source_module_code is required" in str(exc)
    else:
        raise AssertionError("source_module_code must be required")


def test_user_quick_action_preferences_survive_new_and_archived_actions():
    preferences = [
        build_user_quick_action_preference(
            user_id="user-1",
            quick_action_code="SAMPLE_ARCHIVED_ACTION",
            source_module_code="MODULE_TEST_SAMPLE",
            is_enabled=False,
            is_pinned_in_module=True,
            is_pinned_on_module_card=True,
            sort_order=1,
            disabled_reason="Действие больше недоступно.",
        ),
        build_user_quick_action_preference(
            user_id="user-1",
            quick_action_code="SAMPLE_OPEN_LIST",
            source_module_code="MODULE_TEST_SAMPLE",
            is_enabled=True,
            is_pinned_in_module=True,
            is_pinned_on_module_card=True,
            sort_order=2,
        ),
        build_user_quick_action_preference(
            user_id="user-1",
            quick_action_code="SAMPLE_NEW_REPORT",
            source_module_code="MODULE_TEST_SAMPLE",
            is_enabled=True,
            is_pinned_in_module=False,
            is_pinned_on_module_card=False,
            sort_order=3,
        ),
    ]

    module_bar = select_module_bar_preferences(preferences)
    module_card = select_module_card_preferences(preferences)

    assert [item["quickActionCode"] for item in module_bar] == ["SAMPLE_OPEN_LIST"]
    assert [item["quickActionCode"] for item in module_card] == ["SAMPLE_OPEN_LIST"]
    assert all(item["sourceModuleCode"] == "MODULE_TEST_SAMPLE" for item in preferences)
    assert all("moduleNumber" not in item for item in preferences)
