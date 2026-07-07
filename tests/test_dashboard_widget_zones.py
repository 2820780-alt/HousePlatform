from pathlib import Path

from jinja2 import Environment

from app.api.v1.admin_cabinet_view import (
    _build_bottom_widget_grid,
    _build_top_widget_grid,
    _build_widget_settings_groups,
    _is_right_rail_enabled,
    _widget_accent_color,
)
from app.services.dashboard_module_registry import get_dashboard_module_registry_item
from app.services.dashboard_widget_registry import get_dashboard_widget_registry
from app.services.dashboard_widget_payload import build_module3_dashboard_widget_payloads

MODULE3_DASHBOARD_WIDGETS = {
    "MODULE_03_USERS_SUMMARY_WIDGET",
    "MODULE_03_MODERATION_QUEUE_WIDGET",
    "MODULE_03_AUDIT_LOG_WIDGET",
    "MODULE_03_MODULES_STATUS_WIDGET",
    "MODULE_03_WIDGETS_STATUS_WIDGET",
}

def _payload(widget_code: str) -> dict:
    return {
        "widgetCode": widget_code,
        "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        "featureCode": None,
        "title": widget_code,
        "status": "info",
        "updatedAt": "2026-06-26 12:00",
        "items": [{"label": "Всего", "value": 1, "status": "info"}],
    }


def test_bottom_widget_grid_limits_widgets_and_uses_zone_code():
    admin_widgets = [{"payload": _payload(f"admin-{index}")} for index in range(10)]
    grid = _build_bottom_widget_grid(
        admin_widgets=admin_widgets,
        right_rail_widgets=[],
        include_right_rail_widgets=False,
        user_context={"allowedModuleCodes": ["MODULE_01_MATERIAL_HUB"], "allowedFeatureCodes": []},
    )

    assert grid["zoneCode"] == "BOTTOM_WIDGET_GRID"
    assert len(grid["widgets"]) == 6
    assert grid["hiddenCount"] == 4
    assert grid["widgets"][0]["size"] == "small"
    assert grid["widgets"][0]["gridSpan"] == 2


def test_bottom_widget_grid_inherits_accent_from_owner_module():
    module3 = get_dashboard_module_registry_item("MODULE_03_USERS_ROLES")
    module3_payloads = build_module3_dashboard_widget_payloads(users=[], workspaces=[], history=[])
    grid = _build_bottom_widget_grid(
        admin_widgets=[{"payload": payload} for payload in module3_payloads],
        right_rail_widgets=[],
        include_right_rail_widgets=False,
        user_context={
            "allowedModuleCodes": ["MODULE_03_USERS_ROLES"],
            "allowedFeatureCodes": [payload["featureCode"] for payload in module3_payloads],
        },
    )

    assert module3 is not None
    assert {widget["accentColor"] for widget in grid["widgets"]} == {module3.color}


def test_dashboard_settings_groups_include_module3_widgets_as_allowed():
    groups = _build_widget_settings_groups(
        get_dashboard_widget_registry(),
        {
            "roleCode": "PLATFORM_ADMIN",
            "effectiveRoleCode": "PLATFORM_ADMIN",
            "authMode": "mock",
            "allowedModuleCodes": ["MODULE_03_USERS_ROLES"],
            "allowedWidgetCodes": sorted(MODULE3_DASHBOARD_WIDGETS),
            "allowedFeatureCodes": ["DASHBOARD_PERSONALIZE"],
        },
    )
    module3_group = next(group for group in groups if group["moduleCode"] == "MODULE_03_USERS_ROLES")
    module3_widgets = {
        widget["widgetCode"]: widget
        for widget in module3_group["widgets"]
        if widget["widgetCode"] in MODULE3_DASHBOARD_WIDGETS
    }

    assert set(module3_widgets) == MODULE3_DASHBOARD_WIDGETS
    assert all(widget["isAllowed"] is True for widget in module3_widgets.values())
    assert all(widget["isEnabled"] is True for widget in module3_widgets.values())

def test_widget_accent_color_falls_back_to_platform_cyan():
    assert _widget_accent_color("MODULE_UNKNOWN") == "#18d7f2"

def test_bottom_widget_grid_does_not_auto_include_right_rail_widgets():
    admin_widgets = [{"payload": _payload("admin-widget")}]
    right_rail_widgets = [
        {
            "widgetCode": "price-dynamics",
            "sourceModuleCode": "MODULE_11_ANALYTICS",
            "featureCode": "PRICE_DYNAMICS",
            "payload": {
                **_payload("price-dynamics"),
                "sourceModuleCode": "MODULE_11_ANALYTICS",
                "featureCode": "PRICE_DYNAMICS",
                "title": "Аналитика",
            },
            "size": "medium",
            "zoneCode": "RIGHT_RAIL",
            "order": 1,
        }
    ]

    grid = _build_bottom_widget_grid(
        admin_widgets=admin_widgets,
        right_rail_widgets=right_rail_widgets,
        include_right_rail_widgets=False,
        user_context={
            "allowedModuleCodes": ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"],
            "allowedFeatureCodes": ["PRICE_DYNAMICS"],
        },
    )

    assert [widget["widgetCode"] for widget in grid["widgets"]] == ["admin-widget"]


def test_top_widget_grid_supports_zero_to_six_widgets():
    user_context = {"allowedModuleCodes": ["MODULE_01_MATERIAL_HUB"], "allowedFeatureCodes": []}
    empty_grid = _build_top_widget_grid([], user_context)
    seven_item_grid = _build_top_widget_grid([
        {
            "label": f"KPI {index}",
            "value": index,
            "delta": "ok",
            "tone": "info",
            "spark": [1, 2, 3],
            "sourceModuleCode": "MODULE_01_MATERIAL_HUB",
        }
        for index in range(7)
    ], user_context)

    assert empty_grid["zoneCode"] == "TOP_WIDGET_GRID"
    assert empty_grid["widgets"] == []
    assert len(seven_item_grid["widgets"]) == 6
    assert seven_item_grid["hiddenCount"] == 1
    assert {widget["gridSpan"] for widget in seven_item_grid["widgets"]} == {2}


def test_widget_grids_filter_by_preview_role_access():
    user_context = {"allowedModuleCodes": ["MODULE_01_MATERIAL_HUB"], "allowedFeatureCodes": []}
    top_grid = _build_top_widget_grid(
        [
            {"label": "Материалы", "value": 1, "delta": "ok", "tone": "info", "sourceModuleCode": "MODULE_01_MATERIAL_HUB"},
            {"label": "Аналитика", "value": 2, "delta": "ok", "tone": "info", "sourceModuleCode": "MODULE_11_ANALYTICS"},
        ],
        user_context,
    )

    assert [widget["payload"]["title"] for widget in top_grid["widgets"]] == ["Материалы"]


def test_right_rail_can_be_enabled_by_layout_or_preset():
    assert _is_right_rail_enabled(
        {"userDashboardLayout": {"zones": {"RIGHT_RAIL": {"isEnabled": False}}}},
        {"cabinetDashboardPreset": {"widgetZones": {"rightRailEnabled": True}}},
    ) is False
    assert _is_right_rail_enabled(
        {"userDashboardLayout": {"zones": {}}},
        {"cabinetDashboardPreset": {"widgetZones": {"rightRailEnabled": True}}},
    ) is True


def test_right_rail_defaults_off_but_can_use_preview_role():
    assert _is_right_rail_enabled(
        {"userDashboardLayout": {"zones": {}}, "roleCode": "ADMIN"},
        {"cabinetDashboardPreset": {"widgetZones": {"rightRailEnabled": False, "rightRailRoleCodes": ["ANALYST"]}}},
    ) is False
    assert _is_right_rail_enabled(
        {"userDashboardLayout": {"previewRoleCode": "ANALYST", "zones": {}}, "roleCode": "ADMIN"},
        {"cabinetDashboardPreset": {"widgetZones": {"rightRailEnabled": False, "rightRailRoleCodes": ["ANALYST"]}}},
    ) is True

def test_bottom_widget_template_uses_administrative_card_contract():
    template = Path("templates/admin_cabinet_view.html").read_text(encoding="utf-8")

    assert "admin-widget-card--{{ widget.payload.styleVariant }}" in template
    assert "data-widget-style-variant=\"{{ widget.payload.styleVariant or '' }}\"" in template
    assert "data-widget-accent-color=\"{{ widget.accentColor or '#18d7f2' }}\"" in template
    assert "--widget-accent: {{ widget.accentColor or '#18d7f2' }}" in template
    assert "admin-widget-icon--{{ widget.payload.iconKey or 'default' }}" in template
    assert "widget.payload.primaryValue is not none" in template
    assert "widget.payload.emptyStateLabel" in template
    assert "MODULE_03_USERS_SUMMARY_WIDGET" in template
    assert "MODULE_03_MODERATION_QUEUE_WIDGET" in template
    assert "MODULE_03_AUDIT_LOG_WIDGET" in template
    assert "admin-widget-audit-row" in template
    assert "MODULE_03_MODULES_STATUS_WIDGET" in template
    assert "MODULE_03_WIDGETS_STATUS_WIDGET" in template
    assert "admin-widget-donut" in template
    assert "admin-widget-system-row" in template
    assert "Открыть все" not in template[template.index("bottom-widget-grid") : template.index("</section>", template.index("bottom-widget-grid"))]

def test_admin_cabinet_template_jinja_syntax_is_valid():
    template = Path("templates/admin_cabinet_view.html").read_text(encoding="utf-8")

    Environment().parse(template)
