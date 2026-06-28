import pytest

from app.services.ai_access_restrictions import (
    AI_ASSISTANT_SOURCE_MODULE,
    AdminApprovalRequired,
    block_direct_ai_access_change,
    create_access_change_suggestion,
    create_ai_recommendation,
    explain_ai_access_boundary,
    is_ai_capability_allowed,
    is_ai_change_restricted,
    prepare_ai_access_change_or_block,
    require_admin_approval_for_ai_change,
)
from app.services.audit_log_service import AuditLogType, MOCK_AUDIT_EVENTS, clear_mock_audit_events


def setup_function():
    clear_mock_audit_events()


def test_ai_boundary_allows_explanations_but_marks_admin_changes_restricted():
    boundary = explain_ai_access_boundary()

    assert boundary["sourceModuleCode"] == AI_ASSISTANT_SOURCE_MODULE
    assert is_ai_capability_allowed("EXPLAIN_PERMISSION")
    assert is_ai_capability_allowed("DRAFT_ACCESS_CHANGE")
    assert not is_ai_capability_allowed("ASSIGN_ROLE")
    assert is_ai_change_restricted("ASSIGN_ROLE")
    assert is_ai_change_restricted("CHANGE_PERMISSION")
    assert is_ai_change_restricted("ENABLE_PAID_FEATURE")


def test_ai_recommendation_is_non_mutating_and_audited():
    recommendation = create_ai_recommendation(
        recommendation_code="rec-access-conflict-1",
        title="Лишний доступ",
        explanation="У роли поставщика есть лишний глобальный доступ.",
        module_code="MODULE_01_MATERIAL_HUB",
        role_code="SUPPLIER",
        severity="ATTENTION",
    )

    assert recommendation.sourceModuleCode == AI_ASSISTANT_SOURCE_MODULE
    assert recommendation.canonicalModuleCode == "MODULE_01_MATERIAL_HUB"
    assert recommendation.requiresAdminApproval is False
    assert recommendation.status == "DRAFT"
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.AI_RECOMMENDATION_CREATED
    assert MOCK_AUDIT_EVENTS[-1]["roleCode"] == "SUPPLIER"


def test_access_change_suggestion_is_draft_and_requires_admin_approval():
    suggestion = create_access_change_suggestion(
        suggestion_code="suggest-role-1",
        change_type="ASSIGN_ROLE",
        target_user_id="user-1",
        role_code="MODERATOR",
        old_value={"roleCode": "VIEWER"},
        new_value={"roleCode": "MODERATOR"},
        reason="Пользователь работает с модерацией материалов.",
    )

    assert suggestion.sourceModuleCode == AI_ASSISTANT_SOURCE_MODULE
    assert suggestion.requiresAdminApproval is True
    assert suggestion.approvalStatus == "PENDING_ADMIN_APPROVAL"
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.AI_ACCESS_CHANGE_SUGGESTED
    assert MOCK_AUDIT_EVENTS[-1]["result"] == "PENDING_ADMIN_APPROVAL"


def test_ai_cannot_apply_access_change_without_admin_approval():
    suggestion = create_access_change_suggestion(
        suggestion_code="suggest-permission-1",
        change_type="CHANGE_PERMISSION",
        module_code="MODULE_14_PRICE_HISTORY",
        feature_code="PRICE_DYNAMICS",
        role_code="ANALYST",
        new_value={"accessLevel": "ADMIN", "scope": "GLOBAL"},
    )

    with pytest.raises(AdminApprovalRequired) as exc_info:
        require_admin_approval_for_ai_change(suggestion)

    assert exc_info.value.suggestion == suggestion
    assert suggestion.canonicalModuleCode == "MODULE_11_ANALYTICS"
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.AI_ADMIN_APPROVAL_REQUIRED
    assert MOCK_AUDIT_EVENTS[-1]["result"] == "BLOCKED"


def test_prepare_ai_access_change_returns_draft_unless_apply_requested():
    suggestion = prepare_ai_access_change_or_block(
        suggestion_code="suggest-widget-1",
        change_type="ADD_WIDGET_ACCESS",
        widget_code="price-dynamics",
        module_code="MODULE_11_ANALYTICS",
        role_code="ANALYST",
        new_value={"widgetCode": "price-dynamics"},
    )

    assert suggestion.approvalStatus == "PENDING_ADMIN_APPROVAL"
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.AI_ACCESS_CHANGE_SUGGESTED

    with pytest.raises(AdminApprovalRequired):
        prepare_ai_access_change_or_block(
            suggestion_code="suggest-widget-apply-1",
            change_type="ADD_WIDGET_ACCESS",
            widget_code="price-dynamics",
            module_code="MODULE_11_ANALYTICS",
            role_code="ANALYST",
            apply_immediately=True,
        )

    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.AI_ADMIN_APPROVAL_REQUIRED


def test_direct_ai_mutation_is_blocked_and_audited():
    with pytest.raises(AdminApprovalRequired) as exc_info:
        block_direct_ai_access_change(
            change_type="ARCHIVE_MODULE",
            module_code="MODULE_01_MATERIAL_HUB",
            reason="AI attempted to archive a module directly.",
        )

    assert exc_info.value.suggestion.approvalStatus == "BLOCKED"
    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.AI_FORBIDDEN_ACCESS_CHANGE_BLOCKED
    assert MOCK_AUDIT_EVENTS[-1]["result"] == "DENIED"
