from app.services.partner_portal_active_cabinet_context import get_active_cabinet_context
from app.services.partner_portal_cabinet_types import (
    CONSTRUCTION_COMPANY,
    CUSTOMER,
    MATERIAL_SUPPLIER,
    SPECIALIST,
    get_cabinet_type_catalog,
    get_cabinet_type_definition,
    normalize_cabinet_type,
)


def test_cabinet_type_catalog_contains_four_supported_types():
    catalog = get_cabinet_type_catalog()
    codes = {item["cabinetType"] for item in catalog}

    assert codes == {
        CUSTOMER,
        MATERIAL_SUPPLIER,
        CONSTRUCTION_COMPANY,
        SPECIALIST,
    }

    for item in catalog:
        assert item["userTitle"]
        assert item["description"]
        assert item["primaryGoal"]
        assert item["mainFocus"]
        assert item["recommendedModules"]
        assert "MODULE_08_PARTNER_PORTAL" not in item["recommendedModules"]
        assert item["recommendedBlocks"]
        assert item["quickActions"] == []
        assert item["futureBlocks"]
        assert item["sourceModuleCode"] == "MODULE_08_PARTNER_PORTAL"


def test_cabinet_type_aliases_normalize_to_canonical_types():
    assert normalize_cabinet_type("SUPPLIER") == MATERIAL_SUPPLIER
    assert normalize_cabinet_type("CONTRACTOR") == CONSTRUCTION_COMPANY
    assert normalize_cabinet_type("PROJECT") == CUSTOMER
    assert normalize_cabinet_type("ESTIMATOR") == SPECIALIST


def test_customer_cabinet_type_recommends_customer_workflow_modules():
    definition = get_cabinet_type_definition(CUSTOMER)

    assert definition is not None
    assert definition.userTitle == "Заказчик"
    assert "MODULE_07_DIGITAL_HOUSE" in definition.recommendedModules
    assert "MODULE_09_PROCUREMENT" in definition.recommendedModules
    assert definition.quickActions == []


def test_active_cabinet_context_includes_cabinet_type_recommendations():
    context = get_active_cabinet_context(
        {
            "userId": "supplier-user",
            "activeRegionCode": "KRASNODAR_KRAI",
            "workspaces": [
                {
                    "workspaceId": "workspace-supplier",
                    "workspaceTitle": "Бауснаб",
                    "workspaceType": "SUPPLIER",
                    "roleCode": "SUPPLIER",
                }
            ],
        }
    ).to_dict()

    assert context["activeCabinetType"] == MATERIAL_SUPPLIER
    assert context["primaryGoal"]
    assert context["mainFocus"]
    assert "MODULE_01_MATERIAL_HUB" in context["recommendedModules"]
    assert "SUPPLIER_PRICE_LIST_BLOCK" in context["recommendedBlocks"]
    assert context["quickActions"] == []
    assert context["futureBlocks"]
