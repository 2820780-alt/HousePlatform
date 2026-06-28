from app.services.access_context_for_cabinet import build_access_context_for_cabinet
from app.services.module8_cabinet_admin_preview import (
    MODULE8_EMPTY_STATE,
    SOURCE_MODULE_CODE,
    getModule8CabinetAdminPreview,
    get_module8_cabinet_admin_preview,
)


def test_module8_admin_preview_empty_state_does_not_create_module8_entities():
    access_context = build_access_context_for_cabinet(
        {
            "userId": "user-empty",
            "roleCode": "VIEWER",
            "activeRegionCode": "KRASNODAR_KRAI",
        }
    )

    preview = get_module8_cabinet_admin_preview(
        {"id": "user-empty", "roleCodes": ["VIEWER"], "workspaces": []},
        access_context=access_context,
    ).to_dict()

    assert preview["sourceModuleCode"] == SOURCE_MODULE_CODE
    assert preview["cabinets"] == []
    assert preview["linkedObjects"] == []
    assert preview["emptyState"] == MODULE8_EMPTY_STATE
    assert preview["isModule8Connected"] is False
    assert preview["isMock"] is True
    assert "CustomerCabinet" in preview["module8OwnedEntities"]
    assert "CabinetDashboardPreset" in preview["module8OwnedEntities"]
    assert "roles" in preview["editableInModule03"]
    assert "permissions" in preview["editableInModule03"]


def test_module8_admin_preview_uses_workspace_as_mock_preview_not_source_of_truth():
    access_context = build_access_context_for_cabinet(
        {
            "userId": "supplier-user",
            "roleCode": "SUPPLIER",
            "activeRegionCode": "KRASNODAR_KRAI",
        }
    )
    preview = getModule8CabinetAdminPreview(
        {
            "id": "supplier-user",
            "workspaces": [
                {
                    "workspaceId": "workspace-supplier",
                    "workspaceTitle": "Поставщик Бауснаб",
                    "workspaceType": "SUPPLIER",
                    "roleCode": "SUPPLIER",
                    "status": "ACTIVE",
                }
            ],
        },
        access_context=access_context,
    ).to_dict()

    assert preview["sourceModuleCode"] == "MODULE_08_PARTNER_PORTAL"
    assert preview["activeCabinetId"] == "module8-preview:workspace-supplier:SUPPLIER"
    assert preview["activeCabinetType"] == "MATERIAL_SUPPLIER"
    assert preview["cabinets"][0]["businessRole"] == "SUPPLIER"
    assert preview["cabinets"][0]["isActive"] is True
    assert preview["emptyState"] is None
    assert preview["dashboardContextPreview"]["recommendedBlocks"]
    assert "materials-kpi" in preview["dashboardContextPreview"]["recommendedWidgetCodes"]
    assert "SUPPLIER_PRICE_UPLOAD" in preview["dashboardContextPreview"]["recommendedQuickActionCodes"]


def test_module8_admin_preview_does_not_leak_cabinet_settings_into_module3_access_context():
    access_context = build_access_context_for_cabinet(
        {
            "userId": "customer-user",
            "roleCode": "CUSTOMER",
            "activeRegionCode": "KRASNODAR_KRAI",
            "activeCabinetId": "module8-real-cabinet",
            "activeCabinetType": "CUSTOMER",
            "cabinetDashboardPreset": {"must": "not leak"},
        }
    )

    access_data = access_context.to_dict()
    preview = get_module8_cabinet_admin_preview(
        {
            "id": "customer-user",
            "workspaces": [
                {
                    "workspaceId": "workspace-customer",
                    "workspaceTitle": "Заказчик",
                    "workspaceType": "CUSTOMER",
                    "roleCode": "CUSTOMER",
                    "status": "ACTIVE",
                }
            ],
        },
        access_context=access_context,
    ).to_dict()

    assert "activeCabinetId" not in access_data
    assert "activeCabinetType" not in access_data
    assert "cabinetDashboardPreset" not in access_data
    assert preview["activeCabinetType"] == "CUSTOMER"
    assert preview["dashboardContextPreview"]["mainFocus"] == "Preview кабинета: Заказчик"
