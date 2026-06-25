from app.core.access_levels import AccessLevel, is_valid_access_level
from app.core.access_scopes import ACCESS_SCOPES, AccessScope, is_valid_access_scope


def test_access_scopes_describe_data_boundaries():
    assert ACCESS_SCOPES == (
        "NONE",
        "GLOBAL",
        "OWN",
        "RELEVANT",
        "LIMITED",
    )
    assert AccessScope.GLOBAL == "GLOBAL"


def test_access_scope_is_not_action_level():
    assert is_valid_access_scope("OWN") is True
    assert is_valid_access_level("OWN") is False
    assert is_valid_access_scope("ADMIN") is False
    assert is_valid_access_level("ADMIN") is True


def test_access_level_and_scope_can_be_combined():
    supplier_prices = (AccessLevel.ADMIN, AccessScope.OWN)
    material_hub_supplier = (AccessLevel.VIEW, AccessScope.LIMITED)
    platform_admin_material_hub = (AccessLevel.ADMIN, AccessScope.GLOBAL)

    assert supplier_prices == ("ADMIN", "OWN")
    assert material_hub_supplier == ("VIEW", "LIMITED")
    assert platform_admin_material_hub == ("ADMIN", "GLOBAL")
