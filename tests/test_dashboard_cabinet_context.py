from app.services.dashboard_cabinet_context import get_current_cabinet_context


def test_cabinet_context_mock_exposes_dashboard_preset_and_actions():
    context = get_current_cabinet_context(
        {
            "roleCode": "ADMIN",
            "activeCabinetId": "cabinet-admin-mock",
            "activeCabinetType": "ADMIN",
            "allowedActionCodes": ["DASHBOARD_CONFIGURE", "MATERIAL_CREATE"],
        }
    )

    assert context.activeCabinetId == "cabinet-admin-mock"
    assert context.activeCabinetType == "ADMIN"
    assert context.currentBlock == "Главная"
    assert context.cabinetDashboardPreset["presetCode"] == "ADMIN_CABINET_DEFAULT"
    assert context.cabinetDashboardPreset["topbar"]["showGlobalPeriod"] is False
    assert "DASHBOARD_CONFIGURE" in context.allowedActionCodes
