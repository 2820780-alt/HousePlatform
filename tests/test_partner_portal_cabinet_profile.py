from app.models import (
    CabinetBranch,
    CabinetContact,
    CabinetDeliveryZone,
    CabinetDocument,
    CabinetServiceRegion,
)
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_block_catalog import get_cabinet_block_definition
from app.services.partner_portal_cabinet_profile import (
    CABINET_DOCUMENTS_FEATURE,
    MATERIAL_DOCUMENTS_SOURCE_MODULE,
    build_cabinet_profile,
)


def test_cabinet_profile_models_are_module8_entities():
    models = (
        CabinetContact,
        CabinetBranch,
        CabinetServiceRegion,
        CabinetDeliveryZone,
        CabinetDocument,
    )

    for model in models:
        assert model.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL

    assert CabinetContact.__tablename__ == "module08_cabinet_contacts"
    assert CabinetBranch.__tablename__ == "module08_cabinet_branches"
    assert CabinetServiceRegion.__tablename__ == "module08_cabinet_service_regions"
    assert CabinetDeliveryZone.__tablename__ == "module08_cabinet_delivery_zones"
    assert CabinetDocument.__tablename__ == "module08_cabinet_documents"


def test_cabinet_document_is_not_material_document_from_module1():
    document_columns = set(CabinetDocument.__table__.columns.keys())
    cabinet_documents_block = get_cabinet_block_definition("CABINET_DOCUMENTS_BLOCK")
    material_documents_block = get_cabinet_block_definition("DOCUMENTS_BLOCK")

    assert "document_type" in document_columns
    assert cabinet_documents_block is not None
    assert cabinet_documents_block.sourceModuleCode == MODULE_08_PARTNER_PORTAL
    assert cabinet_documents_block.featureCode == CABINET_DOCUMENTS_FEATURE
    assert material_documents_block is not None
    assert material_documents_block.sourceModuleCode == MATERIAL_DOCUMENTS_SOURCE_MODULE
    assert material_documents_block.featureCode == "DOCUMENTS"


def test_build_cabinet_profile_groups_contacts_branches_regions_zones_and_documents():
    profile = build_cabinet_profile(
        cabinet_id="cabinet-1",
        contacts=[
            {
                "contactType": "SALES",
                "title": "Отдел продаж",
                "contactPerson": "Анна",
                "phone": "+7 900 000-00-00",
                "isPrimary": True,
            }
        ],
        branches=[
            {
                "branchCode": "branch-1",
                "title": "Краснодарский филиал",
                "regionCode": "KRASNODAR_KRAI",
                "cityId": "krasnodar",
            }
        ],
        service_regions=[
            {
                "regionCode": "KRASNODAR_KRAI",
                "regionTitle": "Краснодарский край",
                "serviceType": "SUPPLY",
                "isPrimary": True,
            }
        ],
        delivery_zones=[
            {
                "deliveryZoneCode": "zone-1",
                "regionCode": "KRASNODAR_KRAI",
                "title": "Краснодар и пригород",
                "deliveryType": "LOCAL_DELIVERY",
            }
        ],
        documents=[
            {
                "documentCode": "doc-1",
                "documentType": "COMPANY_CARD",
                "title": "Карточка компании",
                "documentStatus": "ACTIVE",
            }
        ],
    ).to_dict()

    assert profile["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert profile["contacts"][0]["sourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert profile["branches"][0]["regionCode"] == "KRASNODAR_KRAI"
    assert profile["serviceRegions"][0]["serviceType"] == "SUPPLY"
    assert profile["deliveryZones"][0]["deliveryType"] == "LOCAL_DELIVERY"
    assert profile["documents"][0]["featureCode"] == CABINET_DOCUMENTS_FEATURE
    assert profile["documents"][0]["materialDocumentsSourceModuleCode"] == MATERIAL_DOCUMENTS_SOURCE_MODULE
