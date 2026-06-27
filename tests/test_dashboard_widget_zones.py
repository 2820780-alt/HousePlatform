from app.api.v1.admin_cabinet_view import _build_bottom_widget_grid, _build_top_widget_grid, _is_right_rail_enabled


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
