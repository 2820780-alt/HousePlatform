from app.services.active_module_quick_action_patterns import (
    ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN,
    PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY,
    get_active_module_quick_action_patterns,
    get_planned_module_quick_action_compatibility_readiness,
    get_planned_module_quick_action_patterns,
    get_quick_action_pattern_readiness,
    get_quick_action_patterns_for_module,
)


def test_global_quick_action_pattern_registry_is_empty():
    assert ACTIVE_MODULE_CODES_FOR_QUICK_ACTION_PATTERN == ()
    assert PLANNED_MODULE_CODES_FOR_QUICK_ACTION_COMPATIBILITY == ()
    assert get_active_module_quick_action_patterns() == []
    assert get_quick_action_pattern_readiness() == []
    assert get_quick_action_patterns_for_module("MODULE_11_ANALYTICS") == []


def test_planned_quick_action_pattern_placeholders_are_not_global_presets():
    assert get_planned_module_quick_action_patterns() == []
    assert get_planned_module_quick_action_compatibility_readiness() == []
