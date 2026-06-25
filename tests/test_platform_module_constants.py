from app.core.platform_modules import (
    SYSTEM_MODULE_CONSTANTS_ARE_NOT_SOURCE_OF_TRUTH,
    SYSTEM_MODULES,
    SystemModuleCode,
    is_known_system_module_constant,
)


def test_system_module_constants_cover_core_codes_without_claiming_registry_truth():
    assert SYSTEM_MODULES["MATERIAL_HUB"] == "MODULE_01_MATERIAL_HUB"
    assert SYSTEM_MODULES["KNOWLEDGE_BASE"] == "MODULE_02_KNOWLEDGE_BASE"
    assert SYSTEM_MODULES["USERS_ROLES"] == "MODULE_03_USERS_ROLES"
    assert SYSTEM_MODULES["ANALYTICS"] == "MODULE_11_ANALYTICS"
    assert SYSTEM_MODULES["PRICE_HISTORY_LEGACY"] == "MODULE_14_PRICE_HISTORY"
    assert SystemModuleCode.PRICE_HISTORY_LEGACY == "MODULE_14_PRICE_HISTORY"
    assert SYSTEM_MODULE_CONSTANTS_ARE_NOT_SOURCE_OF_TRUTH is True


def test_unknown_future_module_can_exist_outside_constants():
    assert is_known_system_module_constant("MODULE_18_QUALITY_CONTROL") is False
