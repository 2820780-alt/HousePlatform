from datetime import datetime

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
            {"label": "Газобетон", "value": "+8%", "status": "ok", "route": "/modules/analytics"},
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
