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
    assert context.activeCabinetTitle == "Административное пространство / Администратор"
    assert context.currentBlock == "Главная"
    assert context.cabinetDashboardPreset["presetCode"] == "ADMIN_CABINET_DEFAULT"
    assert context.cabinetDashboardPreset["topbar"]["showGlobalPeriod"] is False
    assert context.cabinetDashboardPreset["atomCardActions"]["maxActionsPerCard"] == 3
    assert "MODULE_01_MATERIAL_HUB" in context.cabinetDashboardPreset["atomCardActions"]["moduleActionCodes"]
    assert "DASHBOARD_CONFIGURE" in context.allowedActionCodes


def test_cabinet_context_uses_effective_preview_role_in_title():
    context = get_current_cabinet_context(
        {
            "roleCode": "ADMIN",
            "effectiveRoleCode": "SUPPLIER",
            "effectiveRoleLabel": "Поставщик",
            "workspaceTitle": "Административное пространство",
            "activeCabinetId": "cabinet-admin-mock",
            "activeCabinetType": "SUPPLIER",
            "allowedActionCodes": ["SUPPLIER_PRICE_UPLOAD"],
        }
    )

    assert context.activeCabinetType == "SUPPLIER"
    assert context.activeCabinetTitle == "Административное пространство / Поставщик"
    assert context.businessRole == "SUPPLIER"
