from app.services.partner_portal_block_catalog import (
    get_blocks_for_cabinet_type,
    get_cabinet_block_catalog,
    get_cabinet_block_definition,
)
from app.services.partner_portal_cabinet_types import (
    CONSTRUCTION_COMPANY,
    CUSTOMER,
    MATERIAL_SUPPLIER,
    SPECIALIST,
    get_cabinet_type_definitions,
)


EXPECTED_BLOCK_CODES = {
    "OBJECT_IMAGE_BLOCK",
    "ESTIMATES_BLOCK",
    "ESTIMATE_AUDIT_BLOCK",
    "OBJECT_STORAGE_BLOCK",
    "PROCUREMENT_BLOCK",
    "DOCUMENTS_BLOCK",
    "TECHNOLOGY_KNOWLEDGE_BLOCK",
    "PRICE_ANALYTICS_BLOCK",
    "SUPPLIER_PRICE_LIST_BLOCK",
    "SUPPLIER_REQUESTS_BLOCK",
    "COMPANY_PROJECTS_BLOCK",
    "COMPANY_EMPLOYEES_BLOCK",
    "SPECIALIST_SPECIFICATIONS_BLOCK",
    "WORKS_BLOCK",
    "CONTACTS_BLOCK",
    "BRANCHES_BLOCK",
    "OFFER_SETTINGS_BLOCK",
    "VISIBILITY_SETTINGS_BLOCK",
}


def test_cabinet_block_catalog_contains_required_blocks_and_fields():
    catalog = get_cabinet_block_catalog()
    codes = {item["blockCode"] for item in catalog}

    assert EXPECTED_BLOCK_CODES.issubset(codes)
    for item in catalog:
        assert item["blockCode"]
        assert item["sourceModuleCode"]
        assert item["featureCode"]
        assert item["userTitle"]
        assert item["description"]
        assert item["allowedCabinetTypes"]
        assert item["allowedBusinessRoles"]
        assert "requiresPermission" in item
        assert "isFuture" in item
        assert "isPremiumFeature" in item
        if item["requiresPermission"]:
            assert item["requiresPermission"]["moduleCode"]
            assert item["requiresPermission"]["actionCode"]
            assert item["requiresPermission"]["scope"]


def test_cabinet_blocks_filter_by_cabinet_type_and_future_flag():
    supplier_blocks = get_blocks_for_cabinet_type(MATERIAL_SUPPLIER)
    supplier_codes = {item["blockCode"] for item in supplier_blocks}

    assert "SUPPLIER_PRICE_LIST_BLOCK" in supplier_codes
    assert "COMPANY_EMPLOYEES_BLOCK" not in supplier_codes
    assert "SUPPLIER_REQUESTS_BLOCK" not in supplier_codes

    supplier_future_blocks = get_blocks_for_cabinet_type(MATERIAL_SUPPLIER, include_future=True)
    supplier_future_codes = {item["blockCode"] for item in supplier_future_blocks}
    assert "SUPPLIER_REQUESTS_BLOCK" in supplier_future_codes


def test_block_catalog_has_expected_ownership_boundaries():
    assert get_cabinet_block_definition("OBJECT_IMAGE_BLOCK").sourceModuleCode == "MODULE_07_DIGITAL_HOUSE"
    assert get_cabinet_block_definition("WORKS_BLOCK").sourceModuleCode == "MODULE_04_WORKS_COSTS"
    assert get_cabinet_block_definition("PROCUREMENT_BLOCK").sourceModuleCode == "MODULE_09_PROCUREMENT"
    assert get_cabinet_block_definition("PRICE_ANALYTICS_BLOCK").featureCode == "PRICE_DYNAMICS"
    visibility_block = get_cabinet_block_definition("VISIBILITY_SETTINGS_BLOCK")
    assert visibility_block.sourceModuleCode == "MODULE_08_PARTNER_PORTAL"
    assert visibility_block.sourceContextModuleCode == "PARTICIPANT_CABINET_CONTEXT"
    assert visibility_block.requiresPermission.moduleCode == "PARTICIPANT_CABINET_CONTEXT"


def test_cabinet_type_recommendations_reference_known_block_codes():
    known_codes = {item["blockCode"] for item in get_cabinet_block_catalog()}

    for cabinet_type in get_cabinet_type_definitions():
        for block_code in [*cabinet_type.recommendedBlocks, *cabinet_type.futureBlocks]:
            assert block_code in known_codes, f"{cabinet_type.cabinetType}: {block_code}"


def test_block_catalog_covers_all_supported_cabinet_types():
    for cabinet_type in (CUSTOMER, MATERIAL_SUPPLIER, CONSTRUCTION_COMPANY, SPECIALIST):
        blocks = get_blocks_for_cabinet_type(cabinet_type, include_future=True)
        assert blocks, cabinet_type
