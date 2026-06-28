from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.audit_log_service import (
    record_ai_access_change_suggested,
    record_ai_admin_approval_required,
    record_ai_forbidden_access_change_blocked,
    record_ai_recommendation_created,
)
from app.services.dashboard_module_registry import get_canonical_module_code

AI_ASSISTANT_SOURCE_MODULE = "MODULE_12_AI_ASSISTANT"

AI_ALLOWED_CAPABILITIES = frozenset(
    {
        "EXPLAIN_PERMISSION",
        "SHOW_ACCESS_CONFLICT",
        "SUGGEST_SETTING",
        "FIND_EXCESS_ACCESS",
        "PREPARE_RECOMMENDATION",
        "EXPLAIN_MODULE_HIDDEN",
        "EXPLAIN_WIDGET_UNAVAILABLE",
        "DRAFT_ACCESS_CHANGE",
    }
)

AI_RESTRICTED_CHANGE_TYPES = frozenset(
    {
        "ASSIGN_ROLE",
        "CHANGE_PERMISSION",
        "ENABLE_MODULE",
        "DISABLE_MODULE",
        "ARCHIVE_MODULE",
        "MERGE_MODULE",
        "ADD_WIDGET_ACCESS",
        "DELETE_USER",
        "CHANGE_USER_DASHBOARD_LAYOUT",
        "CHANGE_ACTIVE_CABINET_CONTEXT",
        "ENABLE_PAID_FEATURE",
    }
)


@dataclass(frozen=True)
class AIRecommendation:
    recommendationCode: str
    title: str
    explanation: str
    sourceModuleCode: str = AI_ASSISTANT_SOURCE_MODULE
    targetModuleCode: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    widgetCode: str | None = None
    roleCode: str | None = None
    severity: str = "INFO"
    status: str = "DRAFT"
    requiresAdminApproval: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AccessChangeSuggestion:
    suggestionCode: str
    changeType: str
    sourceModuleCode: str = AI_ASSISTANT_SOURCE_MODULE
    targetUserId: str | None = None
    workspaceId: str | None = None
    moduleCode: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    widgetCode: str | None = None
    roleCode: str | None = None
    oldValue: Any | None = None
    newValue: Any | None = None
    reason: str | None = None
    createdBy: str = "AI_ASSISTANT"
    approvalStatus: str = "PENDING_ADMIN_APPROVAL"
    requiresAdminApproval: bool = True
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdminApprovalRequired(PermissionError):
    def __init__(self, message: str, suggestion: AccessChangeSuggestion | None = None):
        super().__init__(message)
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": "ADMIN_APPROVAL_REQUIRED",
            "message": str(self),
            "suggestion": self.suggestion.to_dict() if self.suggestion else None,
        }


def is_ai_capability_allowed(capability_code: str) -> bool:
    return capability_code in AI_ALLOWED_CAPABILITIES


def is_ai_change_restricted(change_type: str) -> bool:
    return change_type in AI_RESTRICTED_CHANGE_TYPES


def create_ai_recommendation(
    *,
    recommendation_code: str,
    title: str,
    explanation: str,
    module_code: str | None = None,
    feature_code: str | None = None,
    widget_code: str | None = None,
    role_code: str | None = None,
    severity: str = "INFO",
    payload: dict[str, Any] | None = None,
) -> AIRecommendation:
    canonical_module_code = get_canonical_module_code(module_code) if module_code else None
    recommendation = AIRecommendation(
        recommendationCode=recommendation_code,
        title=title,
        explanation=explanation,
        targetModuleCode=module_code,
        canonicalModuleCode=canonical_module_code,
        featureCode=feature_code,
        widgetCode=widget_code,
        roleCode=role_code,
        severity=severity,
        payload=payload or {},
    )
    record_ai_recommendation_created(
        recommendation_code=recommendation.recommendationCode,
        module_code=module_code,
        canonical_module_code=canonical_module_code,
        feature_code=feature_code,
        widget_code=widget_code,
        role_code=role_code,
        reason="AI recommendation created as a non-mutating draft.",
        metadata={"severity": severity},
    )
    return recommendation


def create_access_change_suggestion(
    *,
    suggestion_code: str,
    change_type: str,
    target_user_id: str | None = None,
    workspace_id: str | None = None,
    module_code: str | None = None,
    feature_code: str | None = None,
    widget_code: str | None = None,
    role_code: str | None = None,
    old_value: Any | None = None,
    new_value: Any | None = None,
    reason: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AccessChangeSuggestion:
    canonical_module_code = get_canonical_module_code(module_code) if module_code else None
    suggestion = AccessChangeSuggestion(
        suggestionCode=suggestion_code,
        changeType=change_type,
        targetUserId=target_user_id,
        workspaceId=workspace_id,
        moduleCode=module_code,
        canonicalModuleCode=canonical_module_code,
        featureCode=feature_code,
        widgetCode=widget_code,
        roleCode=role_code,
        oldValue=old_value,
        newValue=new_value,
        reason=reason,
        payload=payload or {},
    )
    record_ai_access_change_suggested(
        suggestion_code=suggestion.suggestionCode,
        change_type=change_type,
        module_code=module_code,
        canonical_module_code=canonical_module_code,
        feature_code=feature_code,
        widget_code=widget_code,
        role_code=role_code,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
    )
    return suggestion


def require_admin_approval_for_ai_change(suggestion: AccessChangeSuggestion) -> None:
    if not suggestion.requiresAdminApproval:
        return
    record_ai_admin_approval_required(
        change_type=suggestion.changeType,
        suggestion_code=suggestion.suggestionCode,
        module_code=suggestion.moduleCode,
        canonical_module_code=suggestion.canonicalModuleCode,
        feature_code=suggestion.featureCode,
        widget_code=suggestion.widgetCode,
        role_code=suggestion.roleCode,
    )
    raise AdminApprovalRequired(
        "AI Assistant can prepare this change only as a draft. Administrator approval is required.",
        suggestion,
    )


def block_direct_ai_access_change(
    *,
    change_type: str,
    module_code: str | None = None,
    feature_code: str | None = None,
    widget_code: str | None = None,
    role_code: str | None = None,
    reason: str | None = None,
) -> None:
    canonical_module_code = get_canonical_module_code(module_code) if module_code else None
    record_ai_forbidden_access_change_blocked(
        change_type=change_type,
        module_code=module_code,
        canonical_module_code=canonical_module_code,
        feature_code=feature_code,
        widget_code=widget_code,
        role_code=role_code,
        reason=reason,
    )
    raise AdminApprovalRequired(
        "AI Assistant cannot directly change roles, permissions, modules, widgets, registry or layouts.",
        AccessChangeSuggestion(
            suggestionCode=f"blocked-{change_type.lower()}",
            changeType=change_type,
            moduleCode=module_code,
            canonicalModuleCode=canonical_module_code,
            featureCode=feature_code,
            widgetCode=widget_code,
            roleCode=role_code,
            reason=reason,
            approvalStatus="BLOCKED",
        ),
    )


def prepare_ai_access_change_or_block(
    *,
    suggestion_code: str,
    change_type: str,
    apply_immediately: bool = False,
    **kwargs: Any,
) -> AccessChangeSuggestion:
    suggestion = create_access_change_suggestion(
        suggestion_code=suggestion_code,
        change_type=change_type,
        **kwargs,
    )
    if apply_immediately:
        require_admin_approval_for_ai_change(suggestion)
    return suggestion


def explain_ai_access_boundary() -> dict[str, Any]:
    return {
        "sourceModuleCode": AI_ASSISTANT_SOURCE_MODULE,
        "allowedCapabilities": sorted(AI_ALLOWED_CAPABILITIES),
        "restrictedChangeTypes": sorted(AI_RESTRICTED_CHANGE_TYPES),
        "rule": "AI can explain and draft access changes, but cannot apply administrative decisions.",
    }
