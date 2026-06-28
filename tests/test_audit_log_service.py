import pytest

from app.core.exceptions import ForbiddenError
from app.core.permission_guard import require_permission
from app.services.audit_log_service import (
    MOCK_AUDIT_EVENTS,
    AuditLogType,
    clear_mock_audit_events,
    record_dashboard_layout_change,
    record_inaccessible_widget_add_attempt,
    record_legacy_module_normalization,
    record_module_merge_or_alias_change,
    record_permission_change,
    record_view_as_role_entered,
    record_widget_permission_change,
    record_widget_registry_change,
    sanitize_audit_details,
    write_audit_event_mock,
)
from app.services.dashboard_module_registry import normalize_dashboard_layout
from app.services.module_visibility import ActiveRegionContext, normalize_legacy_module_mapping
from tests.test_module_visibility import _module


def setup_function():
    clear_mock_audit_events()


def test_audit_details_redact_sensitive_values():
    details = sanitize_audit_details(
        {
            "moduleCode": "MODULE_03_USERS_ROLES",
            "password": "secret",
            "nested": {"access_token": "token", "safe": "ok"},
        }
    )

    assert details["password"] == "[REDACTED]"
    assert details["nested"]["access_token"] == "[REDACTED]"
    assert details["nested"]["safe"] == "ok"


def test_write_audit_event_mock_keeps_standard_fields():
    event = write_audit_event_mock(
        {
            "eventType": AuditLogType.WIDGET_REGISTRY_CHANGED,
            "widgetCode": "materials.kpi",
            "token": "secret",
        }
    )

    assert event["eventType"] == AuditLogType.WIDGET_REGISTRY_CHANGED
    assert event["widgetCode"] == "materials.kpi"
    assert event["token"] == "[REDACTED]"
    assert MOCK_AUDIT_EVENTS == [event]


def test_permission_guard_records_denied_attempt():
    with pytest.raises(ForbiddenError):
        require_permission({"roleCode": "SUPPLIER", "userId": "u-1"}, "MODULE_03_USERS_ROLES", "ADMIN", "GLOBAL")

    assert MOCK_AUDIT_EVENTS[-1]["eventType"] == AuditLogType.ACCESS_DENIED
    assert MOCK_AUDIT_EVENTS[-1]["moduleCode"] == "MODULE_03_USERS_ROLES"
    assert MOCK_AUDIT_EVENTS[-1]["metadata"]["actionCode"] == "ADMIN"


def test_legacy_layout_normalization_records_audit_event():
    normalized = normalize_dashboard_layout(
        {
            "favoriteModules": ["MODULE_14_PRICE_HISTORY"],
            "widgets": [
                {
                    "sourceModuleCode": "MODULE_14_PRICE_HISTORY",
                    "featureCode": "PRICE_DYNAMICS",
                    "title": "Динамика цен",
                }
            ],
        }
    )

    assert normalized["favoriteModules"] == ["MODULE_11_ANALYTICS"]
    assert any(event["eventType"] == AuditLogType.PRICE_HISTORY_MIGRATED_TO_ANALYTICS for event in MOCK_AUDIT_EVENTS)
    assert any(event["featureCode"] == "PRICE_DYNAMICS" for event in MOCK_AUDIT_EVENTS)


def test_module_visibility_normalization_records_inactive_and_migration_events():
    mapping = normalize_legacy_module_mapping(
        "MODULE_14_PRICE_HISTORY",
        [
            _module(
                "MODULE_14_PRICE_HISTORY",
                canonical_module_code="MODULE_11_ANALYTICS",
                status="MERGED",
                is_active=False,
                feature_codes=["PRICE_DYNAMICS"],
            )
        ],
    )

    assert mapping["canonicalModuleCode"] == "MODULE_11_ANALYTICS"
    event_types = [event["eventType"] for event in MOCK_AUDIT_EVENTS]
    assert AuditLogType.INACTIVE_MODULE_OPEN_ATTEMPT in event_types
    assert AuditLogType.PRICE_HISTORY_MIGRATED_TO_ANALYTICS in event_types


def test_permission_scope_widget_layout_and_preview_helpers_emit_expected_events():
    record_permission_change(
        actor={"userId": "admin"},
        role_code="SUPPLIER",
        module_code="MODULE_01_MATERIAL_HUB",
        old_value={"accessScope": "LIMITED"},
        new_value={"accessScope": "OWN"},
    )
    record_widget_registry_change(widget_code="materials.kpi", module_code="MODULE_01_MATERIAL_HUB")
    record_widget_permission_change(widget_code="materials.kpi", role_code="SUPPLIER")
    record_inaccessible_widget_add_attempt(widget_code="future.widget", reason="planned")
    record_dashboard_layout_change(user={"userId": "u-1"}, old_layout={}, new_layout={"widgets": []})
    record_view_as_role_entered(actor={"userId": "admin"}, role_code="CUSTOMER")
    record_module_merge_or_alias_change(
        module_code="MODULE_07_DIGITAL_OBJECT",
        canonical_module_code="MODULE_07_DIGITAL_HOUSE",
        merged_into_module_code="MODULE_07_DIGITAL_HOUSE",
    )

    event_types = {event["eventType"] for event in MOCK_AUDIT_EVENTS}
    assert AuditLogType.SCOPE_CHANGED in event_types
    assert AuditLogType.WIDGET_REGISTRY_CHANGED in event_types
    assert AuditLogType.WIDGET_PERMISSION_CHANGED in event_types
    assert AuditLogType.INACCESSIBLE_WIDGET_ADD_ATTEMPT in event_types
    assert AuditLogType.USER_DASHBOARD_LAYOUT_CHANGED in event_types
    assert AuditLogType.VIEW_AS_ROLE_ENTERED in event_types
    assert AuditLogType.MODULE_MERGED in event_types
