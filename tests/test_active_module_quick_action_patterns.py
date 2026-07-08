from app.services.active_module_quick_action_patterns import (
    ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN,
    MODULE_UI_READY,
    PLANNED_DOCUMENTATION_ONLY,
    PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY,
    PLANNED_NO_ACTIVE_ACTIONS,
    get_active_module_quick_action_patterns,
    get_planned_module_quick_action_compatibility_readiness,
    get_planned_module_quick_action_patterns,
    get_quick_action_pattern_readiness,
    get_quick_action_patterns_for_module,
)


def test_active_quick_action_pattern_catalog_documents_real_module_candidates_only():
    assert ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN == (
        "MODULE_01_MATERIAL_HUB",
        "MODULE_03_USERS_ROLES",
        "MODULE_11_ANALYTICS",
    )

    patterns = get_active_module_quick_action_patterns()
    assert len(patterns) == 9
    assert {item["sourceModuleCode"] for item in patterns} == set(ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN)
    assert all(item["ownerModuleOwnsExecution"] is True for item in patterns)
    assert all(item["isExecutable"] is True for item in patterns)
    assert all("quickActionCode" not in item for item in patterns)


def test_module_03_pattern_catalog_uses_safe_view_candidates_not_fixed_shortcuts():
    patterns = get_quick_action_patterns_for_module("MODULE_03_USERS_ROLES")

    assert {item["featureCode"] for item in patterns} == {"USERS_DIRECTORY", "ACCESS_MATRIX", "AUDIT_LOG"}
    assert {item["actionKey"] for item in patterns} == {"VIEW"}
    assert {item["route"] for item in patterns} == {
        "/api/v1/admin/users-roles/view#users",
        "/api/v1/admin/users-roles/view#access-matrix",
        "/api/v1/admin/users-roles/view/history",
    }
    assert all(item["uiStatus"] == MODULE_UI_READY for item in patterns)
    assert all(item["configMode"] == "NO_CONFIG" for item in patterns)


def test_active_quick_action_pattern_readiness_is_documentation_not_registry_source():
    readiness = get_quick_action_pattern_readiness()

    assert {item["sourceModuleCode"] for item in readiness} == set(ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN)
    assert all(item["uiStatus"] == MODULE_UI_READY for item in readiness)
    assert {item["candidateCount"] for item in readiness} == {2, 3, 4}
    assert all(item["patternLayer"] == "module_owned_user_quick_actions" for item in readiness)
    assert all(item["requiresModuleUi"] is False for item in readiness)


def test_planned_quick_action_pattern_placeholders_are_not_global_presets():
    assert PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY == (
        "MODULE_12_AI_ASSISTANT",
        "MODULE_13_PROJECT_COLLABORATION",
        "MODULE_15_CONTRACTS",
        "MODULE_16_LOGISTICS_DELIVERY",
        "MODULE_17_FINANCE_PAYMENTS",
        "MODULE_18_QUALITY_CONTROL",
        "MODULE_19_CONSTRUCTOR_LITE",
        "MODULE_20_SITE_SUPERVISION",
        "MODULE_21_WARRANTY_SERVICE",
    )

    patterns = get_planned_module_quick_action_patterns()
    readiness = get_planned_module_quick_action_compatibility_readiness()

    assert {item["sourceModuleCode"] for item in patterns} == set(PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY)
    assert all(item["status"] == PLANNED_DOCUMENTATION_ONLY for item in patterns)
    assert all(item["uiStatus"] == PLANNED_NO_ACTIVE_ACTIONS for item in patterns)
    assert all(item["isVisibleToOrdinaryUsers"] is False for item in patterns)
    assert all(item["isExecutable"] is False for item in patterns)
    assert all(item["canPinToAtomCard"] is False for item in patterns)
    assert all(item["metadata"]["compatibilityOnly"] is True for item in patterns)
    assert {item["sourceModuleCode"] for item in readiness} == set(PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY)
    assert all(item["candidateCount"] == 1 for item in readiness)
