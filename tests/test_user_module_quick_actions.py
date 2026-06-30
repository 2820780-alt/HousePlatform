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
