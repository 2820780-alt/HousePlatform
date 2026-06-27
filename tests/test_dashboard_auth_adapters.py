from app.services.dashboard_auth_adapters import (
    can_access_module,
    can_access_widget,
    can_change_region,
    can_edit_dashboard_layout,
    can_preview_dashboard_roles,
    can_use_action,
    can_see_planned_modules,
    can_use_feature,
    get_dashboard_user_context,
)


def test_dashboard_user_context_mock_uses_module_codes_and_region_registry_data():
    context = get_dashboard_user_context(
        personalization={
            "active_workspace": "Администрирование",
            "favorite_modules": [
                {"module_code": "MODULE_01_MATERIAL_HUB"},
                {"module_code": "MODULE_14_PRICE_HISTORY"},
            ],
            "widgets": [
                {"type": "KPI", "title": "Материалы", "size": "S", "module_number": 1},
                {"type": "CHART", "title": "Динамика цен", "size": "M", "module_number": 14},
            ],
        },
        active_region={"code": "KRASNODAR_KRAI", "name": "Краснодарский край"},
        cards=[
            {
                "module_code": "MODULE_01_MATERIAL_HUB",
                "canonical_module_code": "MODULE_01_MATERIAL_HUB",
                "atom_status": "active",
            },
            {
                "module_code": "MODULE_02_KNOWLEDGE_BASE",
                "canonical_module_code": "MODULE_02_KNOWLEDGE_BASE",
                "atom_status": "planned",
            },
        ],
    )

    assert context.authMode == "mock"
    assert context.roleCode == "ADMIN"
    assert context.activeRegionCode == "KRASNODAR_KRAI"
    assert context.activeCabinetId == "cabinet-admin-mock"
    assert context.activeCabinetType == "ADMIN"
    assert "MODULE_01_MATERIAL_HUB" in context.allowedModuleCodes
    assert "MODULE_02_KNOWLEDGE_BASE" in context.allowedModuleCodes
    assert "DASHBOARD_CONFIGURE" in context.allowedActionCodes
    assert context.favoriteModuleCodes == ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"]
    assert context.dashboardLayout["widgets"][1]["moduleCode"] == "MODULE_11_ANALYTICS"
    assert context.dashboardLayout["widgets"][1]["legacyModuleCode"] == "MODULE_14_PRICE_HISTORY"


def test_dashboard_permission_helpers_work_over_mock_context():
    context = get_dashboard_user_context(
        personalization={
            "active_workspace": "Администрирование",
            "favorite_modules": [{"module_code": "MODULE_01_MATERIAL_HUB"}],
            "widgets": [{"type": "KPI", "title": "Материалы", "size": "S", "module_number": 1}],
        },
        active_region={"code": "KRASNODAR_KRAI", "name": "Краснодарский край"},
        cards=[
            {
                "module_code": "MODULE_01_MATERIAL_HUB",
                "canonical_module_code": "MODULE_01_MATERIAL_HUB",
                "atom_status": "active",
            }
        ],
    )

    assert can_access_module(context, "MODULE_01_MATERIAL_HUB")
    assert not can_access_module(context, "MODULE_99_UNKNOWN")
    assert can_access_widget(context, "KPI:Материалы")
    assert can_use_feature(context, "DASHBOARD_PERSONALIZE")
    assert can_use_action(context, "DASHBOARD_CONFIGURE")
    assert not can_use_action(context, "UNKNOWN_ACTION")
    assert can_edit_dashboard_layout(context)
    assert can_see_planned_modules(context)
    assert context.to_template_dict()["canPreviewDashboardRoles"] is True
    assert not can_change_region(context)
    assert can_preview_dashboard_roles({"roleCode": "SUPER_ADMIN"})
    assert not can_preview_dashboard_roles({"roleCode": "SUPPLIER"})


def test_dashboard_permission_helpers_normalize_legacy_digital_object_access():
    context = {
        "allowedModuleCodes": ["MODULE_07_DIGITAL_OBJECT"],
    }

    assert can_access_module(context, "MODULE_07_DIGITAL_HOUSE")
    assert can_access_module(context, "MODULE_07_DIGITAL_OBJECT")


def test_preview_role_changes_effective_access_without_changing_real_role():
    context = get_dashboard_user_context(
        personalization={
            "active_workspace": "Администрирование",
            "favorite_modules": [{"module_code": "MODULE_01_MATERIAL_HUB"}],
            "widgets": [],
        },
        active_region={"code": "KRASNODAR_KRAI", "name": "Краснодарский край"},
        cards=[
            {
                "module_code": "MODULE_01_MATERIAL_HUB",
                "canonical_module_code": "MODULE_01_MATERIAL_HUB",
                "atom_status": "active",
            },
            {
                "module_code": "MODULE_11_ANALYTICS",
                "canonical_module_code": "MODULE_11_ANALYTICS",
                "atom_status": "active",
            },
        ],
        preview_role_code="SUPPLIER",
    )

    assert context.roleCode == "ADMIN"
    assert context.previewRoleCode == "SUPPLIER"
    assert context.effectiveRoleCode == "SUPPLIER"
    assert context.activeCabinetType == "SUPPLIER"
    assert "MODULE_09_TENDERS" in context.allowedModuleCodes
    assert "MODULE_11_ANALYTICS" not in context.allowedModuleCodes
    assert can_use_action(context, "SUPPLIER_PRICE_UPLOAD")
    assert not can_see_planned_modules(context)
    assert context.to_template_dict()["canPreviewDashboardRoles"] is True
