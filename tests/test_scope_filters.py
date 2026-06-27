import pytest
from sqlalchemy import select

from app.core.exceptions import ForbiddenError
from app.core.scope_filters import (
    apply_permission_scope_filter,
    apply_scope_filter,
    build_scope_condition,
    filter_resources_by_scope,
    get_owner_scope_context,
    project_limited_fields,
    resource_matches_scope,
)
from app.models import SupplierAccount, SupplierPrice, SupplierUpload, WorkspaceMember


def test_owner_scope_context_collects_supplier_and_workspace_relations():
    user = {
        "userId": "user-1",
        "supplier_accounts": [SupplierAccount(user_id="user-1", supplier_id="supplier-1")],
        "workspace_members": [WorkspaceMember(user_id="user-1", workspace_id="workspace-1", role_key="SUPPLIER")],
    }

    context = get_owner_scope_context(user)

    assert context.userId == "user-1"
    assert context.supplierIds == ("supplier-1",)
    assert context.workspaceIds == ("workspace-1",)


def test_supplier_own_scope_matches_only_supplier_resources():
    supplier_user = {"userId": "user-1", "roleCode": "SUPPLIER", "supplierIds": ["supplier-1"]}
    resources = [
        {"id": "upload-1", "supplier_id": "supplier-1"},
        {"id": "upload-2", "supplier_id": "supplier-2"},
    ]

    visible = filter_resources_by_scope(resources, supplier_user, "OWN")

    assert visible == [{"id": "upload-1", "supplier_id": "supplier-1"}]
    assert resource_matches_scope(resources[0], supplier_user, "OWN")
    assert not resource_matches_scope(resources[1], supplier_user, "OWN")


def test_customer_own_scope_matches_owner_user_id():
    customer_user = {"userId": "customer-1", "roleCode": "CUSTOMER"}

    assert resource_matches_scope({"owner_user_id": "customer-1"}, customer_user, "OWN")
    assert not resource_matches_scope({"owner_user_id": "customer-2"}, customer_user, "OWN")


def test_contractor_own_scope_matches_contractor_id():
    contractor_user = {"roleCode": "CONTRACTOR", "contractorIds": ["contractor-1"]}

    assert resource_matches_scope({"contractor_id": "contractor-1"}, contractor_user, "OWN")
    assert not resource_matches_scope({"contractor_id": "contractor-2"}, contractor_user, "OWN")


def test_own_scope_fails_closed_when_user_has_no_owner_values():
    supplier_user = {"userId": "user-1", "roleCode": "SUPPLIER"}

    assert not resource_matches_scope({"supplier_id": "supplier-1"}, supplier_user, "OWN")


def test_relevant_scope_uses_relevant_project_and_organization_rules():
    user = {
        "roleCode": "CUSTOMER",
        "relevantProjectIds": ["project-1"],
        "relevantOrganizationIds": ["org-1"],
    }

    assert resource_matches_scope({"project_id": "project-1"}, user, "RELEVANT")
    assert resource_matches_scope({"organization_id": "org-1"}, user, "RELEVANT")
    assert not resource_matches_scope({"project_id": "project-2"}, user, "RELEVANT")


def test_limited_scope_projects_only_explicit_fields():
    payload = {
        "id": "material-1",
        "title": "Газоблок",
        "supplier_margin": "hidden",
        "internal_comment": "hidden",
    }

    assert project_limited_fields(payload, ["id", "title"]) == {
        "id": "material-1",
        "title": "Газоблок",
    }
    assert project_limited_fields({"secret": "hidden"}, []) == {}


def test_sqlalchemy_own_scope_builds_supplier_filter_condition():
    user = {"roleCode": "SUPPLIER", "supplierIds": ["supplier-1"]}

    condition = build_scope_condition(SupplierPrice, user, "OWN")
    statement = apply_scope_filter(select(SupplierPrice), SupplierPrice, user, "OWN")

    assert "supplier_prices.supplier_id" in str(condition)
    assert statement.whereclause is not None


def test_sqlalchemy_scope_fails_closed_without_supported_model_fields():
    class NoOwnerColumns:
        pass

    condition = build_scope_condition(NoOwnerColumns, {"userId": "user-1"}, "OWN")

    assert str(condition) == "false"


def test_permission_scope_filter_requires_permission_before_filtering():
    supplier_user = {"roleCode": "SUPPLIER", "supplierIds": ["supplier-1"]}

    statement = apply_permission_scope_filter(
        select(SupplierUpload),
        SupplierUpload,
        supplier_user,
        "MODULE_11_ANALYTICS",
        "VIEW",
        "OWN",
    )
    assert statement.whereclause is not None

    with pytest.raises(ForbiddenError):
        apply_permission_scope_filter(
            select(SupplierUpload),
            SupplierUpload,
            supplier_user,
            "MODULE_01_MATERIAL_HUB",
            "ADMIN",
            "GLOBAL",
        )
