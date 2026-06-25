from app.models import ModuleActionRegistry


def test_module_action_registry_model_uses_module_code_and_action_code():
    item = ModuleActionRegistry(
        module_code="MODULE_01_MATERIAL_HUB",
        action_code="RUN_ANALYSIS",
        title="Run analysis",
        is_system=True,
        is_active=True,
    )

    assert item.module_code == "MODULE_01_MATERIAL_HUB"
    assert item.action_code == "RUN_ANALYSIS"
    assert item.is_active is True
