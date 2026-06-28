from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.access_scopes import AccessScope
from app.core.exceptions import ForbiddenError
from app.core.permission_guard import can, require_permission
from app.services.dashboard_module_registry import get_canonical_module_code
from app.services.audit_log_service import record_view_as_role_entered, record_view_as_role_exited
from app.services.role_dashboard_access_profiles import (
    can_preview_dashboard_access_profiles,
    get_role_dashboard_access_profile,
    normalize_role_dashboard_profile_code,
)
from app.services.user_dashboard_layout import reset_layout_to_role_profile


PREVIEW_ROLE_SOURCE_MODULE_CODE = "MODULE_03_USERS_ROLES"
PREVIEW_ROLE_ACTION_CODE = "VIEW_AS_ROLE"
PREVIEW_ROLE_LAYER = "module03_preview_role"
PREVIEW_ROLE_NOTE = (
    "Preview Role changes only visual Dashboard context. It does not change the actor role, "
    "does not grant real permissions and does not execute business operations for preview role."
)


@dataclass(frozen=True)
class PreviewRoleContext:
    actorUser: dict[str, Any]
    visualUser: dict[str, Any]
    roleDashboardAccessProfile: dict[str, Any]
    userDashboardLayout: dict[str, Any]
    previewRoleCode: str
    realRoleCode: str | None
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    previewCabinetType: str | None = None
    previewActiveCabinetId: str | None = None
    previewBusinessRole: str | None = None
    isPreviewMode: bool = True
    previewLayer: str = PREVIEW_ROLE_LAYER
    compatibilityNote: str = PREVIEW_ROLE_NOTE
    futureModule08Ready: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def enter_preview_role(
    actor: Any,
    preview_role_code: str | None,
    *,
    workspace_id: str | None = None,
    active_region_code: str | None = None,
    active_region_name: str | None = None,
    preview_cabinet_type: str | None = None,
    preview_active_cabinet_id: str | None = None,
    preview_business_role: str | None = None,
    reason: str | None = None,
    log_event: bool = True,
) -> dict[str, Any]:
    context = build_preview_role_context(
        actor,
        preview_role_code,
        workspace_id=workspace_id,
        active_region_code=active_region_code,
        active_region_name=active_region_name,
        preview_cabinet_type=preview_cabinet_type,
        preview_active_cabinet_id=preview_active_cabinet_id,
        preview_business_role=preview_business_role,
    )
    if log_event:
        record_view_as_role_entered(
            actor=actor,
            role_code=context.previewRoleCode,
            workspace_id=workspace_id,
            reason=reason or "View as Role mode entered.",
        )
    return context.to_dict()


def exit_preview_role(
    actor: Any,
    *,
    preview_role_code: str | None = None,
    workspace_id: str | None = None,
    reason: str | None = None,
    log_event: bool = True,
) -> dict[str, Any]:
    actor_data = _context_dict(actor)
    if log_event:
        record_view_as_role_exited(
            actor=actor,
            role_code=normalize_role_dashboard_profile_code(preview_role_code),
            workspace_id=workspace_id,
            reason=reason or "View as Role mode exited.",
        )
    return {
        "actorUser": actor_data,
        "visualUser": dict(actor_data),
        "previewRoleCode": None,
        "realRoleCode": _real_role_code(actor),
        "isPreviewMode": False,
        "previewLayer": PREVIEW_ROLE_LAYER,
        "compatibilityNote": PREVIEW_ROLE_NOTE,
    }


def build_preview_role_context(
    actor: Any,
    preview_role_code: str | None,
    *,
    workspace_id: str | None = None,
    active_region_code: str | None = None,
    active_region_name: str | None = None,
    preview_cabinet_type: str | None = None,
    preview_active_cabinet_id: str | None = None,
    preview_business_role: str | None = None,
) -> PreviewRoleContext:
    actor_data = _context_dict(actor)
    real_role_code = _real_role_code(actor)
    normalized_preview_role = normalize_role_dashboard_profile_code(preview_role_code)
    if not normalized_preview_role:
        raise ForbiddenError("Preview role is required.")
    if not can_preview_dashboard_access_profiles(real_role_code):
        raise ForbiddenError("Current user cannot enter Preview Role mode.")
    if not can(actor_data, PREVIEW_ROLE_SOURCE_MODULE_CODE, PREVIEW_ROLE_ACTION_CODE, AccessScope.GLOBAL):
        raise ForbiddenError("Current user does not have Module 03 permission for Preview Role.")

    profile = get_role_dashboard_access_profile(normalized_preview_role)
    if not profile:
        raise ForbiddenError("Preview role profile is not configured.")

    settings = profile.get("settings") or {}
    effective_workspace_id = workspace_id or actor_data.get("workspaceId") or actor_data.get("workspace_id")
    effective_region_code = active_region_code or actor_data.get("activeRegionCode")
    effective_cabinet_type = preview_cabinet_type or settings.get("activeCabinetType")
    visual_user = {
        **actor_data,
        "roleCode": normalized_preview_role,
        "effectiveRoleCode": normalized_preview_role,
        "realRoleCode": real_role_code,
        "previewRoleCode": normalized_preview_role,
        "workspaceId": effective_workspace_id,
        "activeRegionCode": effective_region_code,
        "activeRegionName": active_region_name or actor_data.get("activeRegionName"),
        "activeCabinetId": preview_active_cabinet_id or actor_data.get("activeCabinetId"),
        "activeCabinetType": effective_cabinet_type,
        "businessRole": preview_business_role or normalized_preview_role,
        "allowedModuleCodes": profile.get("allowedModuleCodes") or [],
        "allowedWidgetCodes": profile.get("defaultWidgetCodes") or [],
        "allowedFeatureCodes": profile.get("allowedFeatureCodes") or [],
        "allowedActionCodes": profile.get("defaultQuickActionCodes") or [],
        "favoriteModuleCodes": settings.get("favoriteModuleCodes") or [],
        "roleDashboardAccessProfile": profile,
        "isPreviewMode": True,
        "previewLayer": PREVIEW_ROLE_LAYER,
    }
    preview_layout = reset_layout_to_role_profile(
        user=visual_user,
        role_code=normalized_preview_role,
        context={
            **visual_user,
            "roleDashboardAccessProfile": profile,
            "activeRegionCode": effective_region_code,
        },
    )
    preview_layout["isPreviewLayout"] = True
    preview_layout["previewRoleCode"] = normalized_preview_role

    visual_user["userDashboardLayout"] = preview_layout
    return PreviewRoleContext(
        actorUser=actor_data,
        visualUser=visual_user,
        roleDashboardAccessProfile=profile,
        userDashboardLayout=preview_layout,
        previewRoleCode=normalized_preview_role,
        realRoleCode=real_role_code,
        workspaceId=effective_workspace_id,
        activeRegionCode=effective_region_code,
        previewCabinetType=effective_cabinet_type,
        previewActiveCabinetId=preview_active_cabinet_id,
        previewBusinessRole=preview_business_role,
        metadata={
            "moduleVisibilityUser": "visualUser",
            "widgetPermissionUser": "visualUser",
            "dangerousActionUser": "actorUser",
            "module08FutureFields": [
                "previewCabinetType",
                "previewActiveCabinetId",
                "previewBusinessRole",
            ],
        },
    )


def require_real_actor_permission_for_preview_action(
    actor: Any,
    *,
    module_code: str,
    action_code: str,
    scope: str = AccessScope.GLOBAL,
) -> Any:
    return require_permission(actor, module_code, action_code, scope)


def filter_preview_module_visibility_items(preview_context: Any, module_items: list[Any]) -> list[Any]:
    data = preview_context.to_dict() if isinstance(preview_context, PreviewRoleContext) else _context_dict(preview_context)
    profile = data.get("roleDashboardAccessProfile") or {}
    allowed_modules = {
        get_canonical_module_code(code) or code
        for code in profile.get("allowedModuleCodes", [])
    }
    if not allowed_modules:
        return []

    filtered: list[Any] = []
    for item in module_items:
        canonical = (
            _get_value(item, "canonicalModuleCode")
            or _get_value(item, "canonical_module_code")
            or _get_value(item, "moduleCode")
            or _get_value(item, "module_code")
        )
        canonical = get_canonical_module_code(canonical) or canonical
        if canonical in allowed_modules:
            filtered.append(item)
    return filtered


def can_enter_preview_role(actor: Any, preview_role_code: str | None) -> bool:
    try:
        build_preview_role_context(actor, preview_role_code)
    except ForbiddenError:
        return False
    return True


def _real_role_code(actor: Any) -> str | None:
    data = _context_dict(actor)
    return (
        data.get("realRoleCode")
        or data.get("roleCode")
        or data.get("role_code")
        or data.get("role")
    )


def _context_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_template_dict"):
        return value.to_template_dict()
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


enterPreviewRole = enter_preview_role
exitPreviewRole = exit_preview_role
buildPreviewRoleContext = build_preview_role_context
filterPreviewModuleVisibilityItems = filter_preview_module_visibility_items
requireRealActorPermissionForPreviewAction = require_real_actor_permission_for_preview_action
canEnterPreviewRole = can_enter_preview_role
