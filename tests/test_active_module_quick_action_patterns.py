from app.services.active_module_quick_action_patterns import (
    ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN,
    MODULE_UI_READY,
    PATTERN_READY_NO_UI,
    PLANNED_DOCUMENTATION_ONLY,
    PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY,
    PLANNED_NO_ACTIVE_ACTIONS,
    get_active_module_quick_action_patterns,
    get_planned_module_quick_action_compatibility_readiness,
    get_planned_module_quick_action_patterns,
    get_quick_action_pattern_readiness,
    get_quick_action_patterns_for_module,
)


def test_active_modules_have_quick_action_candidate_patterns():
    readiness = get_quick_action_pattern_readiness()
    module_codes = {item["sourceModuleCode"] for item in readiness}

    assert module_codes == set(ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN)
    assert all(item["candidateCount"] > 0 for item in readiness)
    assert all(item["patternLayer"] == "module_owned_user_quick_actions" for item in readiness)


def test_quick_action_patterns_keep_required_identity_and_owner_boundary():
    patterns = get_active_module_quick_action_patterns()

    assert patterns
    for pattern in patterns:
        assert pattern["sourceModuleCode"]
        assert pattern["featureCode"]
        assert pattern["actionKey"]
        assert pattern["title"]
        assert pattern["ownerModuleOwnsExecution"] is True
        assert "businessPayload" not in pattern
        assert "resultPayload" not in pattern
        assert "rawData" not in pattern
        assert "sourceRows" not in pattern


def test_only_existing_module_screens_are_marked_ui_ready():
    readiness_by_module = {
        item["sourceModuleCode"]: item["uiStatus"]
        for item in get_quick_action_pattern_readiness()
    }

    assert readiness_by_module["MODULE_03_USERS_ROLES"] == MODULE_UI_READY
    assert readiness_by_module["MODULE_11_ANALYTICS"] == MODULE_UI_READY
    assert readiness_by_module["MODULE_02_KNOWLEDGE_BASE"] == PATTERN_READY_NO_UI
    assert readiness_by_module["MODULE_04_WORKS_COSTS"] == PATTERN_READY_NO_UI
    assert readiness_by_module["MODULE_05_ESTIMATE_ENGINE"] == PATTERN_READY_NO_UI
    assert readiness_by_module["MODULE_06_ESTIMATE_AUDIT"] == PATTERN_READY_NO_UI
    assert readiness_by_module["MODULE_07_DIGITAL_HOUSE"] == PATTERN_READY_NO_UI
    assert readiness_by_module["MODULE_09_PROCUREMENT"] == PATTERN_READY_NO_UI
    assert readiness_by_module["MODULE_10_MARKETPLACE"] == PATTERN_READY_NO_UI


def test_module_11_current_slice_uses_config_snapshot_not_payload():
    patterns = {
        item["actionKey"]: item
        for item in get_quick_action_patterns_for_module("MODULE_11_ANALYTICS")
    }

    assert patterns["OPEN_PRICE_DYNAMICS"]["configMode"] == "NO_CONFIG"
    assert patterns["OPEN_CURRENT_PRICE_DYNAMICS_SLICE"]["configMode"] == "CONFIG_SNAPSHOT"
    assert patterns["OPEN_CURRENT_PRICE_DYNAMICS_SLICE"]["featureCode"] == "PRICE_DYNAMICS"


def test_planned_modules_have_documentation_only_quick_action_patterns():
    readiness = get_planned_module_quick_action_compatibility_readiness()
    module_codes = {item["sourceModuleCode"] for item in readiness}

    assert module_codes == set(PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY)
    assert all(item["uiStatus"] == PLANNED_NO_ACTIVE_ACTIONS for item in readiness)
    assert all(item["candidateCount"] > 0 for item in readiness)
    assert all(item["visibleToOrdinaryUsers"] is False for item in readiness)
    assert all(item["executable"] is False for item in readiness)


def test_planned_quick_action_patterns_are_not_active_or_pinnable():
    patterns = get_planned_module_quick_action_patterns()

    assert patterns
    for pattern in patterns:
        assert pattern["sourceModuleCode"] in PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY
        assert pattern["status"] == PLANNED_DOCUMENTATION_ONLY
        assert pattern["uiStatus"] == PLANNED_NO_ACTIVE_ACTIONS
        assert pattern["isVisibleToOrdinaryUsers"] is False
        assert pattern["isExecutable"] is False
        assert pattern["canPinToAtomCard"] is False
        assert pattern["ownerModuleOwnsExecution"] is True
        assert pattern["metadata"]["mustNotRenderAsActive"] is True
        assert "businessPayload" not in pattern
        assert "resultPayload" not in pattern
        assert "rawData" not in pattern


def test_planned_modules_do_not_leak_into_active_quick_action_readiness():
    active_modules = {
        item["sourceModuleCode"]
        for item in get_quick_action_pattern_readiness()
    }

    assert active_modules.isdisjoint(PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY)
