from typing import Final


class SystemModuleCode:
    MATERIAL_HUB: Final[str] = "MODULE_01_MATERIAL_HUB"
    KNOWLEDGE_BASE: Final[str] = "MODULE_02_KNOWLEDGE_BASE"
    USERS_ROLES: Final[str] = "MODULE_03_USERS_ROLES"
    ANALYTICS: Final[str] = "MODULE_11_ANALYTICS"
    PRICE_HISTORY_LEGACY: Final[str] = "MODULE_14_PRICE_HISTORY"


SYSTEM_MODULES: Final[dict[str, str]] = {
    "MATERIAL_HUB": SystemModuleCode.MATERIAL_HUB,
    "KNOWLEDGE_BASE": SystemModuleCode.KNOWLEDGE_BASE,
    "USERS_ROLES": SystemModuleCode.USERS_ROLES,
    "ANALYTICS": SystemModuleCode.ANALYTICS,
    "PRICE_HISTORY_LEGACY": SystemModuleCode.PRICE_HISTORY_LEGACY,
}

SYSTEM_MODULE_CONSTANTS_ARE_NOT_SOURCE_OF_TRUTH: Final[bool] = True


def is_known_system_module_constant(module_code: str) -> bool:
    return module_code in SYSTEM_MODULES.values()
