from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.role_access_matrix import (
    ACTIVE_STARTER_MODULE_CODES,
    get_starter_role_feature_access,
    get_starter_role_module_access,
)
from app.core.system_roles import SYSTEM_ROLE_CODES
from app.models import FunctionAccess, ModuleAccess


def test_role_access_matrix_uses_module_codes_not_module_numbers():
    matrix = get_starter_role_module_access()

    assert matrix
    assert all("moduleCode" in rule for rule in matrix)
    assert all("moduleNumber" not in rule for rule in matrix)
    assert all(rule["roleCode"] in SYSTEM_ROLE_CODES for rule in matrix)
    assert all(rule["accessLevel"] in AccessLevel._value2member_map_ for rule in matrix)
    assert all(rule["accessScope"] in AccessScope._value2member_map_ for rule in matrix)
    assert "MODULE_14_PRICE_HISTORY" not in {rule["moduleCode"] for rule in matrix}


def test_super_admin_gets_admin_global_for_all_active_starter_modules():
    matrix = get_starter_role_module_access()
    super_admin_rules = {
        rule["moduleCode"]: (rule["accessLevel"], rule["accessScope"])
        for rule in matrix
        if rule["roleCode"] == "SUPER_ADMIN"
    }

    assert set(super_admin_rules) == set(ACTIVE_STARTER_MODULE_CODES)
    assert all(value == ("ADMIN", "GLOBAL") for value in super_admin_rules.values())


def test_price_history_access_is_feature_access_inside_analytics():
    feature_matrix = get_starter_role_feature_access()
    price_rules = [rule for rule in feature_matrix if rule["featureCode"] == "PRICE_DYNAMICS"]

    assert price_rules
    assert all(rule["moduleCode"] == "MODULE_11_ANALYTICS" for rule in price_rules)
    assert all(rule["accessLevel"] in {"VIEW", "ADMIN"} for rule in price_rules)
    assert any(rule["roleCode"] == "MODERATOR" for rule in price_rules)
    assert "MODULE_14_PRICE_HISTORY" not in {rule["moduleCode"] for rule in price_rules}


def test_module_and_feature_access_models_support_code_first_scope_without_number():
    module_access = ModuleAccess(
        module_number=None,
        module_code="MODULE_11_ANALYTICS",
        canonical_module_code="MODULE_11_ANALYTICS",
        access_level=AccessLevel.ADMIN,
        access_scope=AccessScope.GLOBAL,
    )
    feature_access = FunctionAccess(
        module_number=None,
        module_code="MODULE_11_ANALYTICS",
        canonical_module_code="MODULE_11_ANALYTICS",
        feature_code="PRICE_DYNAMICS",
        function_key="PRICE_DYNAMICS",
        access_level=AccessLevel.VIEW,
        access_scope=AccessScope.OWN,
    )

    assert module_access.module_number is None
    assert module_access.module_code == "MODULE_11_ANALYTICS"
    assert module_access.access_scope == "GLOBAL"
    assert feature_access.module_number is None
    assert feature_access.feature_code == "PRICE_DYNAMICS"
    assert feature_access.access_scope == "OWN"
