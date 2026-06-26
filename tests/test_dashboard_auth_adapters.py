from app.services.dashboard_auth_adapters import (
    can_access_module,
    can_access_widget,
    can_change_region,
    can_edit_dashboard_layout,
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
                {"module_code": "MODULE_11_ANALYTICS"},
            ],
            "widgets": [
                {"type": "KPI", "title": "Материалы", "size": "S", "module_number": 1},
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
    assert "MODULE_01_MATERIAL_HUB" in context.allowedModuleCodes
    assert "MODULE_02_KNOWLEDGE_BASE" in context.allowedModuleCodes
    assert context.favoriteModuleCodes == ["MODULE_01_MATERIAL_HUB", "MODULE_11_ANALYTICS"]


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
    assert can_edit_dashboard_layout(context)
    assert can_see_planned_modules(context)
    assert not can_change_region(context)
