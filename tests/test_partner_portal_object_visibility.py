from app.models import ObjectOfferSettings, ObjectVisibilitySettings
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_object_visibility import (
    MODULE_03_USERS_ROLES,
    MODULE_07_DIGITAL_HOUSE,
    build_object_offer_settings,
    build_object_visibility_settings,
    get_default_object_offer_settings,
    get_default_object_visibility_settings,
)


def test_object_visibility_and_offer_models_are_module8_entities_with_explicit_privacy_fields():
    visibility_columns = set(ObjectVisibilitySettings.__table__.columns.keys())
    offer_columns = set(ObjectOfferSettings.__table__.columns.keys())

    assert ObjectVisibilitySettings.__tablename__ == "module08_object_visibility_settings"
    assert ObjectOfferSettings.__tablename__ == "module08_object_offer_settings"
    assert ObjectVisibilitySettings.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert ObjectOfferSettings.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    for column in (
        "show_in_selections",
        "show_region",
        "show_exact_address",
        "show_technology",
        "show_estimate",
        "show_procurement_need",
        "show_customer_contacts",
        "show_financial_data",
        "show_personal_data",
    ):
        assert column in visibility_columns
    for column in (
        "target_object_id",
        "target_cabinet_id",
        "can_send_offer",
        "can_receive_offers",
        "offer_visibility_enabled",
        "offer_contact_policy",
        "offer_source_module",
        "receive_supplier_offers",
        "receive_construction_company_offers",
        "receive_specialist_offers",
    ):
        assert column in offer_columns


def test_default_object_visibility_is_privacy_first():
    settings = get_default_object_visibility_settings(
        cabinet_id="cabinet-customer-1",
        object_id="object-1",
    ).to_dict()

    assert settings["visibilityScope"] == "PRIVATE"
    assert settings["showInSelections"] is False
    assert settings["showRegion"] is True
    assert settings["showExactAddress"] is False
    assert settings["showEstimate"] is False
    assert settings["showCustomerContacts"] is False
    assert settings["showFinancialData"] is False
    assert settings["showPersonalData"] is False
    assert settings["targetModuleCode"] == MODULE_07_DIGITAL_HOUSE
    assert settings["permissionSourceModuleCode"] == MODULE_03_USERS_ROLES


def test_default_object_offer_settings_are_opt_in():
    settings = get_default_object_offer_settings(
        cabinet_id="cabinet-customer-1",
        object_id="object-1",
    ).to_dict()

    assert settings["offerScope"] == "NONE"
    assert settings["allowedOfferTypes"] == []
    assert settings["canSendOffer"] is False
    assert settings["canReceiveOffers"] is False
    assert settings["offerVisibilityEnabled"] is False
    assert settings["offerContactPolicy"] == "HIDDEN"
    assert settings["offerSourceModule"] == MODULE_08_PARTNER_PORTAL
    assert settings["targetObjectId"] == "object-1"
    assert settings["targetCabinetId"] == "cabinet-customer-1"
    assert settings["receiveSupplierOffers"] is False
    assert settings["receiveConstructionCompanyOffers"] is False
    assert settings["receiveSpecialistOffers"] is False
    assert settings["targetModuleCode"] == MODULE_07_DIGITAL_HOUSE
    assert settings["permissionSourceModuleCode"] == MODULE_03_USERS_ROLES


def test_build_visibility_settings_accepts_safe_opt_in_without_exposing_private_defaults():
    settings = build_object_visibility_settings(
        {
            "visibilityScope": "REGION",
            "showInSelections": True,
            "showTechnology": True,
            "showProcurementNeed": True,
        },
        cabinet_id="cabinet-customer-1",
        object_id="object-1",
    ).to_dict()

    assert settings["visibilityScope"] == "REGION"
    assert settings["showInSelections"] is True
    assert settings["showTechnology"] is True
    assert settings["showProcurementNeed"] is True
    assert settings["showExactAddress"] is False
    assert settings["showCustomerContacts"] is False
    assert settings["showEstimate"] is False
    assert settings["showFinancialData"] is False
    assert settings["showPersonalData"] is False


def test_build_offer_settings_derives_allowed_offer_types_from_opt_in_flags():
    settings = build_object_offer_settings(
        {
            "receiveSupplierOffers": True,
            "receiveConstructionCompanyOffers": True,
            "receiveSpecialistOffers": False,
            "offerContactPolicy": "after_approval",
        },
        cabinet_id="cabinet-customer-1",
        object_id="object-1",
    ).to_dict()

    assert settings["offerScope"] == "SELECTED_TYPES"
    assert settings["allowedOfferTypes"] == ["SUPPLIER", "CONSTRUCTION_COMPANY"]
    assert settings["canSendOffer"] is False
    assert settings["canReceiveOffers"] is True
    assert settings["offerVisibilityEnabled"] is True
    assert settings["offerContactPolicy"] == "AFTER_APPROVAL"
    assert settings["targetObjectId"] == "object-1"
    assert settings["targetCabinetId"] == "cabinet-customer-1"
    assert settings["receiveSupplierOffers"] is True
    assert settings["receiveConstructionCompanyOffers"] is True
    assert settings["receiveSpecialistOffers"] is False
    assert "showCustomerContacts" not in settings
    assert "showFinancialData" not in settings


def test_offer_ready_layer_does_not_create_business_offer_entities():
    settings = build_object_offer_settings(
        {
            "targetObjectId": "object-42",
            "targetCabinetId": "cabinet-supplier-1",
            "canSendOffer": True,
            "offerVisibilityEnabled": True,
            "offerContactPolicy": "direct",
            "offerSourceModule": "MODULE_08_PARTNER_PORTAL",
        }
    ).to_dict()

    assert settings["targetObjectId"] == "object-42"
    assert settings["targetCabinetId"] == "cabinet-supplier-1"
    assert settings["canSendOffer"] is True
    assert settings["canReceiveOffers"] is False
    assert settings["offerVisibilityEnabled"] is True
    assert settings["offerContactPolicy"] == "DIRECT"
    assert settings["offerSourceModule"] == MODULE_08_PARTNER_PORTAL
    for forbidden_key in (
        "dealId",
        "commercialProposalId",
        "procurementId",
        "marketplaceOfferId",
        "negotiationId",
    ):
        assert forbidden_key not in settings
