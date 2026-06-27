from sqlalchemy import select

from app.core.workspace_context import (
    can_access_workspace,
    get_user_workspace_contexts,
    normalize_workspace_member_status,
    normalize_workspace_type,
    restrict_to_user_workspaces,
    role_code_for_workspace,
    workspace_member_to_dict,
    workspace_to_dict,
)
from app.models import FavoriteModule, User, Workspace, WorkspaceMember
from app.models.enums import UserRole


def test_workspace_model_exposes_target_dto_aliases():
    workspace = Workspace(
        name="Административное пространство",
        slug="admin-default",
        workspace_type="ADMIN",
        status="ACTIVE",
        is_active=True,
        organization_id="org-1",
    )

    assert workspace.title == "Административное пространство"
    assert workspace.type == "INTERNAL"
    assert workspace.organizationId == "org-1"
    assert workspace.isActive is True

    workspace.title = "Поставщик"
    workspace.type = "SUPPLIER"
    workspace.organizationId = "org-2"

    assert workspace.name == "Поставщик"
    assert workspace.workspace_type == "SUPPLIER"
    assert workspace.organization_id == "org-2"


def test_workspace_member_model_exposes_role_code_alias():
    member = WorkspaceMember(
        workspace_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        role_key="SUPPLIER",
        status="ACTIVE",
    )

    assert member.roleCode == "SUPPLIER"

    member.roleCode = "CUSTOMER"

    assert member.role_code == "CUSTOMER"
    assert member.role_key == "CUSTOMER"


def test_workspace_helpers_normalize_types_and_statuses():
    assert normalize_workspace_type("ADMIN") == "INTERNAL"
    assert normalize_workspace_type("supplier") == "SUPPLIER"
    assert normalize_workspace_type("unknown") == "INTERNAL"
    assert normalize_workspace_member_status("INVITED") == "INVITED"
    assert normalize_workspace_member_status("unknown") == "DISABLED"


def test_workspace_to_dict_and_member_to_dict_match_sprint_contract():
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Дом 120 м2",
        slug="house-120",
        workspace_type="PROJECT",
        status="ACTIVE",
        is_active=True,
        owner_user_id="00000000-0000-0000-0000-000000000002",
        organization_id="org-1",
    )
    member = WorkspaceMember(
        id="00000000-0000-0000-0000-000000000003",
        workspace_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        role_key="CUSTOMER",
        role_code="CUSTOMER",
        status="ACTIVE",
    )

    assert workspace_to_dict(workspace) == {
        "id": "00000000-0000-0000-0000-000000000001",
        "type": "PROJECT",
        "title": "Дом 120 м2",
        "ownerUserId": "00000000-0000-0000-0000-000000000002",
        "organizationId": "org-1",
        "isActive": True,
    }
    assert workspace_member_to_dict(member) == {
        "id": "00000000-0000-0000-0000-000000000003",
        "workspaceId": "00000000-0000-0000-0000-000000000001",
        "userId": "00000000-0000-0000-0000-000000000002",
        "roleCode": "CUSTOMER",
        "status": "ACTIVE",
    }


def test_user_workspace_contexts_use_active_memberships_only():
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Поставщик",
        slug="supplier",
        workspace_type="SUPPLIER",
        status="ACTIVE",
        is_active=True,
    )
    active_member = WorkspaceMember(
        workspace_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        role_key="SUPPLIER",
        role_code="SUPPLIER",
        status="ACTIVE",
    )
    invited_member = WorkspaceMember(
        workspace_id="00000000-0000-0000-0000-000000000004",
        user_id="00000000-0000-0000-0000-000000000002",
        role_key="CUSTOMER",
        status="INVITED",
    )
    active_member.workspace = workspace
    invited_member.workspace = Workspace(
        id="00000000-0000-0000-0000-000000000004",
        name="Черновик",
        slug="draft",
        workspace_type="CUSTOMER",
        status="ACTIVE",
        is_active=True,
    )
    user = User(email="supplier@example.com", password_hash="x", role=UserRole.SUPPLIER)
    user.workspace_members = [active_member, invited_member]

    contexts = get_user_workspace_contexts(user)

    assert len(contexts) == 1
    assert contexts[0].workspaceId == "00000000-0000-0000-0000-000000000001"
    assert contexts[0].type == "SUPPLIER"
    assert contexts[0].roleCode == "SUPPLIER"
    assert can_access_workspace(user, "00000000-0000-0000-0000-000000000001")
    assert not can_access_workspace(user, "00000000-0000-0000-0000-000000000004")
    assert role_code_for_workspace(user, "00000000-0000-0000-0000-000000000001") == "SUPPLIER"


def test_restrict_to_user_workspaces_adds_workspace_filter():
    workspace = Workspace(
        id="00000000-0000-0000-0000-000000000001",
        name="Админ",
        slug="admin",
        workspace_type="INTERNAL",
        status="ACTIVE",
        is_active=True,
    )
    member = WorkspaceMember(
        workspace_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        role_key="PLATFORM_ADMIN",
        role_code="PLATFORM_ADMIN",
        status="ACTIVE",
    )
    member.workspace = workspace
    user = {"workspace_members": [member]}

    statement = restrict_to_user_workspaces(select(FavoriteModule), FavoriteModule, user)

    assert statement.whereclause is not None
    assert "favorite_modules.workspace_id" in str(statement.whereclause)
