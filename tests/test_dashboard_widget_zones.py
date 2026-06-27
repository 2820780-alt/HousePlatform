from app.api.v1.admin_cabinet_view import _build_bottom_widget_grid, _is_right_rail_enabled


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
    )

    assert grid["zoneCode"] == "BOTTOM_WIDGET_GRID"
    assert len(grid["widgets"]) == 8
    assert grid["hiddenCount"] == 2
    assert grid["widgets"][0]["size"] == "small"
    assert grid["widgets"][0]["gridSpan"] == 3


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
