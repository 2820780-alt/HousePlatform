import uuid
from datetime import datetime

from app.models import AuditLog
from app.services.dashboard_widget_payload import (
    atom_widget_payload_from_admin_widget,
    build_atom_widget_payload,
)


def test_build_atom_widget_payload_normalizes_shape_and_canonical_module_code():
    payload = build_atom_widget_payload(
        widget_code="price-dynamics",
        source_module_code="MODULE_14_PRICE_HISTORY",
        feature_code="PRICE_DYNAMICS",
        title="Динамика цен",
        status="unexpected",
        severity="critical",
        primary_value="+12%",
        primary_label="рынок",
        trend={"direction": "sideways", "value": "+1,2%"},
        mini_chart={"type": "unknown", "points": [1, 2, 3]},
        items=[
            {"label": "Газобетон", "value": "+8%", "caption": "05.07 08:57", "status": "ok", "route": "/modules/analytics"},
            {"label": "OSB", "value": "-3%", "status": "bad"},
        ],
        attention_items=[
            {"title": "Аномалия цены", "severity": "error", "targetRoute": "/modules/analytics"}
        ],
        cta={"label": "Открыть аналитику", "route": "/modules/analytics", "actionCode": "VIEW"},
        updated_at=datetime(2026, 6, 26, 14, 37),
    )

    data = payload.to_dict()

    assert data["sourceModuleCode"] == "MODULE_11_ANALYTICS"
    assert data["featureCode"] == "PRICE_DYNAMICS"
    assert data["status"] == "info"
    assert data["severity"] == "critical"
    assert data["trend"]["direction"] == "flat"
    assert data["miniChart"]["type"] == "sparkline"
    assert data["items"][0]["status"] == "ok"
    assert data["items"][1]["status"] is None
    assert data["items"][0]["caption"] == "05.07 08:57"
    assert data["attentionItems"][0]["severity"] == "error"
    assert data["cta"]["actionCode"] == "VIEW"
    assert data["updatedAt"] == "2026-06-26 14:37"


def test_atom_widget_payload_from_admin_widget_maps_dashboard_widget_to_standard():
    payload = atom_widget_payload_from_admin_widget(
        {
            "title": "Analytics / Price Dynamics",
            "module_code": "MODULE_14_PRICE_HISTORY",
            "feature_code": "PRICE_DYNAMICS",
            "type": "CHART",
            "items": [
                {"label": "Рост", "value": "+12%", "tone": "success"},
                {"label": "Аномалии", "value": 3, "tone": "danger"},
                {"label": "Mock source", "value": "mock", "mock": True},
            ],
        },
        updated_at="2026-06-26 15:00",
    )

    assert payload["widgetCode"].startswith("MODULE_11_ANALYTICS.PRICE_DYNAMICS.")
    assert payload["sourceModuleCode"] == "MODULE_11_ANALYTICS"
    assert payload["featureCode"] == "PRICE_DYNAMICS"
    assert payload["status"] == "error"
    assert payload["severity"] == "medium"
    assert payload["primaryLabel"] == "Рост"
    assert payload["primaryValue"] == "+12%"
    assert payload["items"][0]["status"] == "ok"
    assert payload["items"][1]["status"] == "error"
    assert [item["severity"] for item in payload["attentionItems"]] == ["error", "attention"]
    assert payload["updatedAt"] == "2026-06-26 15:00"


def test_admin_context_payload_uses_module_03_source_without_module_16_conflict():
    payload = atom_widget_payload_from_admin_widget(
        {
            "title": "Уведомления",
            "type": "ALERTS",
            "items": [{"label": "Ошибок нет", "value": 0, "tone": "success"}],
        },
        updated_at="2026-06-27 10:00",
    )

    assert payload["widgetCode"].startswith("MODULE_03_USERS_ROLES.ALERTS.")
    assert payload["sourceModuleCode"] == "MODULE_03_USERS_ROLES"
    assert payload["contextCode"] == "DASHBOARD_ADMIN_CONTEXT"

def test_module3_dashboard_widget_payloads_use_existing_sources_without_settings_or_actions():
    from app.services.dashboard_widget_payload import build_module3_dashboard_widget_payloads

    payloads = build_module3_dashboard_widget_payloads(users=[], workspaces=[], history=[], updated_at="2026-07-06 12:00")
    by_code = {payload["widgetCode"]: payload for payload in payloads}

    assert set(by_code) == {
        "MODULE_03_USERS_SUMMARY_WIDGET",
        "MODULE_03_MODERATION_QUEUE_WIDGET",
        "MODULE_03_AUDIT_LOG_WIDGET",
        "MODULE_03_MODULES_STATUS_WIDGET",
        "MODULE_03_WIDGETS_STATUS_WIDGET",
    }
    assert all(payload["sourceModuleCode"] == "MODULE_03_USERS_ROLES" for payload in payloads)
    assert by_code["MODULE_03_USERS_SUMMARY_WIDGET"]["primaryLabel"] == "\u0412\u0441\u0435\u0433\u043e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439"
    assert by_code["MODULE_03_MODERATION_QUEUE_WIDGET"]["primaryLabel"] == "\u041d\u0435\u0442 \u0437\u0430\u044f\u0432\u043e\u043a"
    assert by_code["MODULE_03_AUDIT_LOG_WIDGET"]["primaryValue"] == 0
    assert by_code["MODULE_03_MODULES_STATUS_WIDGET"]["miniChart"]["type"] == "donut"
    assert by_code["MODULE_03_WIDGETS_STATUS_WIDGET"]["items"][0]["label"] == "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435"
    assert all(payload["styleVariant"] == "administrative" for payload in payloads)
    assert all(payload["iconKey"] for payload in payloads)
    assert by_code["MODULE_03_USERS_SUMMARY_WIDGET"]["emptyStateLabel"] == "\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445"
    assert by_code["MODULE_03_MODERATION_QUEUE_WIDGET"]["emptyStateLabel"] == "\u041d\u0435\u0442 \u0437\u0430\u044f\u0432\u043e\u043a"
    assert by_code["MODULE_03_AUDIT_LOG_WIDGET"]["emptyStateLabel"] == "\u041d\u0435\u0442 \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0439"
    assert all(payload["cta"] is None for payload in payloads)

def test_module3_audit_dashboard_widget_compacts_latest_entries():
    from app.services.dashboard_widget_payload import build_module3_dashboard_widget_payload

    audit = AuditLog(
        id=uuid.uuid4(),
        user_id=None,
        workspace_id=uuid.uuid4(),
        action_type="module_access_changed",
        entity_type="ModuleAccess",
        entity_id=uuid.uuid4(),
        result="SUCCESS",
        created_at=datetime(2026, 7, 5, 8, 57, 0),
        details={
            "moduleCode": "MODULE_03_USERS_ROLES",
            "targetUserId": "user-1",
            "oldValue": {"allowed": False},
            "newValue": {"allowed": True},
            "reason": "test",
        },
    )

    payload = build_module3_dashboard_widget_payload(
        widget_code="MODULE_03_AUDIT_LOG_WIDGET",
        history=[audit],
        updated_at="2026-07-06 12:00",
    )

    assert payload["primaryValue"] == 1
    assert payload["items"][0]["label"]
    assert payload["items"][0]["value"]
    assert payload["items"][0]["caption"] == "05.07 08:57"
    assert payload["cta"] is None
