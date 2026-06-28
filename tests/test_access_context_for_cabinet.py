from app.services.access_context_for_cabinet import (
    SOURCE_MODULE_CODE,
    build_access_context_for_cabinet,
    get_access_context_for_cabinet,
)


def test_access_context_for_cabinet_exposes_module03_permissions_without_cabinet_payload():
    context = build_access_context_for_cabinet(
        {
            "userId": "supplier-user",
            "workspaceId": "supplier-workspace",
            "roleCode": "SUPPLIER",
            "activeRegionCode": "KRASNODAR_KRAI",
            "activeCabinetId": "must-not-leak",
            "activeCabinetType": "SUPPLIER",
        }
    )
    data = context.to_dict()

    assert data["sourceModuleCode"] == SOURCE_MODULE_CODE
    assert data["userId"] == "supplier-user"
    assert data["workspaceId"] == "supplier-workspace"
    assert data["roleCodes"] == ["SUPPLIER"]
    assert data["activeRegionCode"] == "KRASNODAR_KRAI"
    assert "MODULE_01_MATERIAL_HUB" in data["allowedModuleCodes"]
    assert "MODULE_11_ANALYTICS" in data["allowedModuleCodes"]
    assert {"moduleCode": "MODULE_01_MATERIAL_HUB", "accessScope": "LIMITED", "accessLevel": "VIEW"} in data["scopes"]
    assert any(permission["source"] == "role_access_matrix" for permission in data["permissions"])
    assert "activeCabinetId" not in data
    assert "activeCabinetType" not in data
    assert "cabinetDashboardPreset" not in data
    assert "cabinetBlockCatalog" not in data
    assert "participantProfile" not in data


def test_access_context_helpers_check_module_widget_and_quick_action_access_without_module8():
    context = build_access_context_for_cabinet(
        {
            "userId": "supplier-user",
            "roleCode": "SUPPLIER",
            "activeRegionCode": "KRASNODAR_KRAI",
        }
    )

    assert context.canViewModule("MODULE_01_MATERIAL_HUB")
    assert context.canViewModule("MODULE_14_PRICE_HISTORY")
    assert not context.canViewModule("MODULE_03_USERS_ROLES")
    assert context.canViewWidget("materials-kpi")
    assert not context.canViewWidget("price-dynamics")
    assert context.canRunQuickAction("SUPPLIER_PRICE_UPLOAD")
    assert not context.canRunQuickAction("SOURCE_TASK_CREATE")


def test_access_context_filters_widgets_and_actions_when_region_is_missing():
    context = build_access_context_for_cabinet(
        {
            "userId": "platform-admin",
            "roleCode": "PLATFORM_ADMIN",
        }
    )

    assert context.activeRegionCode is None
    assert "MODULE_01_MATERIAL_HUB" in context.allowedModuleCodes
    assert context.allowedWidgetCodes == []
    assert context.allowedQuickActionCodes == []
    assert not context.canViewWidget("materials-kpi")
    assert not context.canRunQuickAction("MATERIAL_CREATE")


def test_access_context_accepts_explicit_future_module_grant_for_module8_contract():
    context = get_access_context_for_cabinet(
        {
            "userId": "platform-admin",
            "roleCode": "PLATFORM_ADMIN",
            "activeRegionCode": "KRASNODAR_KRAI",
            "moduleAccessRules": [
                {
                    "moduleCode": "MODULE_TEST_FUTURE_SANDBOX",
                    "accessLevel": "VIEW",
                    "accessScope": "GLOBAL",
                }
            ],
        }
    )

    assert "MODULE_TEST_FUTURE_SANDBOX" in context.allowedModuleCodes
    assert context.canViewModule("MODULE_TEST_FUTURE_SANDBOX")
    assert {
        "moduleCode": "MODULE_TEST_FUTURE_SANDBOX",
        "accessScope": "GLOBAL",
        "accessLevel": "VIEW",
    } in context.to_dict()["scopes"]
