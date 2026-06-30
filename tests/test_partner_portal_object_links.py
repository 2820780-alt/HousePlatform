from app.models import CabinetObjectLink, ParticipantObjectAccess
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL
from app.services.partner_portal_object_links import (
    MODULE_03_USERS_ROLES,
    MODULE_07_DIGITAL_HOUSE,
    NON_OWNING_OBJECT_RELATION_TYPES,
    OBJECT_LINK_RELATION_TYPES,
    OBJECT_RELATION_ACTIVE_SUPPLY,
    OBJECT_RELATION_ACTIVE_WORK,
    OBJECT_RELATION_ARCHIVED,
    OBJECT_RELATION_COMPLETED_DEAL,
    OBJECT_RELATION_CONTRACTOR_REQUEST,
    OBJECT_RELATION_INVITED,
    OBJECT_RELATION_OFFER_ALLOWED,
    OBJECT_RELATION_OWNER,
    OBJECT_RELATION_SUPPLIER_REQUEST,
    build_cabinet_object_link,
    build_participant_object_access,
    normalize_object_relation_type,
)


def test_participant_object_access_model_is_module8_entity():
    columns = set(ParticipantObjectAccess.__table__.columns.keys())

    assert CabinetObjectLink.__tablename__ == "module08_cabinet_object_links"
    assert ParticipantObjectAccess.__tablename__ == "module08_participant_object_access"
    assert CabinetObjectLink.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert ParticipantObjectAccess.__table__.columns["module_code"].default.arg == MODULE_08_PARTNER_PORTAL
    assert "relation_type" in columns
    assert "visibility_scope" in columns
    assert "permission_source_module_code" in columns
    assert "is_owner_access" in columns


def test_object_relation_types_are_explicit_and_non_owner_links_are_not_ownership():
    assert OBJECT_LINK_RELATION_TYPES == (
        OBJECT_RELATION_OWNER,
        OBJECT_RELATION_INVITED,
        OBJECT_RELATION_SUPPLIER_REQUEST,
        OBJECT_RELATION_CONTRACTOR_REQUEST,
        OBJECT_RELATION_ACTIVE_SUPPLY,
        OBJECT_RELATION_ACTIVE_WORK,
        OBJECT_RELATION_COMPLETED_DEAL,
        OBJECT_RELATION_OFFER_ALLOWED,
        OBJECT_RELATION_ARCHIVED,
    )
    assert OBJECT_RELATION_OWNER not in NON_OWNING_OBJECT_RELATION_TYPES
    assert set(NON_OWNING_OBJECT_RELATION_TYPES) == set(OBJECT_LINK_RELATION_TYPES) - {OBJECT_RELATION_OWNER}


def test_build_cabinet_object_link_marks_only_owner_as_ownership():
    owner_link = build_cabinet_object_link(
        {
            "objectId": "object-1",
            "relationType": "OWNER",
            "visibilityScope": "PRIVATE",
        },
        cabinet_id="cabinet-customer-1",
    ).to_dict()
    supply_link = build_cabinet_object_link(
        {
            "objectId": "object-1",
            "relationType": "ACTIVE_SUPPLY",
            "visibilityScope": "LIMITED",
        },
        cabinet_id="cabinet-supplier-1",
    ).to_dict()

    assert owner_link["isOwnershipRelation"] is True
    assert supply_link["isOwnershipRelation"] is False
    assert supply_link["targetModuleCode"] == MODULE_07_DIGITAL_HOUSE
    assert "owned" not in supply_link


def test_participant_object_access_uses_visibility_context_not_permission_logic():
    access = build_participant_object_access(
        {
            "objectId": "object-1",
            "relationType": "CONTRACTOR_REQUEST",
            "visibilityScope": "LIMITED",
        },
        cabinet_id="cabinet-company-1",
        participant_user_id="user-contractor-1",
        participant_cabinet_id="participant-cabinet-1",
    ).to_dict()

    assert access["isOwnerAccess"] is False
    assert access["allowedDataScopes"] == ["REQUEST_SUMMARY", "WORK_CONTEXT"]
    assert access["permissionSourceModuleCode"] == MODULE_03_USERS_ROLES
    assert access["visibilitySourceModuleCode"] == MODULE_08_PARTNER_PORTAL
    assert access["targetModuleCode"] == MODULE_07_DIGITAL_HOUSE
    assert "permissionCode" not in access
    assert "accessLevel" not in access


def test_archived_relation_has_no_active_data_scope():
    access = build_participant_object_access(
        {
            "objectId": "object-1",
            "relationType": "ARCHIVED",
            "visibilityScope": "ARCHIVED",
        },
        cabinet_id="cabinet-1",
    ).to_dict()

    assert access["allowedDataScopes"] == []
    assert access["deniedDataScopes"] == ["ACTIVE_DATA"]
    assert access["isOwnerAccess"] is False


def test_relation_normalization_keeps_known_values_and_safely_defaults_unknown():
    assert normalize_object_relation_type("request_supplier") == OBJECT_RELATION_SUPPLIER_REQUEST
    assert normalize_object_relation_type("work") == OBJECT_RELATION_ACTIVE_WORK
    assert normalize_object_relation_type("strange") == OBJECT_RELATION_INVITED
