from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.models import FavoriteModule, FunctionAccess, ModuleAccess, Permission, WorkspaceRole


def test_permission_uses_module_code_action_code_level_and_scope():
    permission = Permission(
        permission_key="MODULE_01_MATERIAL_HUB_VIEW_GLOBAL",
        name="View Material Hub globally",
        module_code="MODULE_01_MATERIAL_HUB",
        action_code="VIEW",
        access_level=AccessLevel.VIEW,
        access_scope=AccessScope.GLOBAL,
        conditions={"region_id": "KRASNODAR_KRAI"},
        is_active=True,
    )

    assert permission.module_code == "MODULE_01_MATERIAL_HUB"
    assert permission.action_code == "VIEW"
    assert permission.access_level == "VIEW"
    assert permission.access_scope == "GLOBAL"
    assert permission.conditions == {"region_id": "KRASNODAR_KRAI"}
    assert permission.module_number is None


def test_legacy_module_number_can_coexist_with_code_first_access_models():
    module_access = ModuleAccess(
        module_number=15,
        module_code="MODULE_15_CONSTRUCTION_GROUPS",
        canonical_module_code="MODULE_01_MATERIAL_HUB",
        access_level=AccessLevel.VIEW,
    )
    function_access = FunctionAccess(
        module_number=15,
        module_code="MODULE_15_CONSTRUCTION_GROUPS",
        canonical_module_code="MODULE_01_MATERIAL_HUB",
        feature_code="CONSTRUCTION_APPLICABILITY",
        function_key="CONSTRUCTION_APPLICABILITY_VIEW",
        access_level=AccessLevel.VIEW,
    )
    favorite_module = FavoriteModule(
        module_number=15,
        module_code="MODULE_15_CONSTRUCTION_GROUPS",
        canonical_module_code="MODULE_01_MATERIAL_HUB",
    )

    assert module_access.module_number == 15
    assert module_access.module_code == "MODULE_15_CONSTRUCTION_GROUPS"
    assert module_access.canonical_module_code == "MODULE_01_MATERIAL_HUB"
    assert function_access.feature_code == "CONSTRUCTION_APPLICABILITY"
    assert favorite_module.module_number == 15
    assert favorite_module.canonical_module_code == "MODULE_01_MATERIAL_HUB"


def test_workspace_role_links_workspace_and_role_without_user_assignment_duplication():
    workspace_role = WorkspaceRole(
        workspace_id="00000000-0000-0000-0000-000000000001",
        role_id="00000000-0000-0000-0000-000000000002",
        status="ACTIVE",
    )

    assert str(workspace_role.workspace_id) == "00000000-0000-0000-0000-000000000001"
    assert str(workspace_role.role_id) == "00000000-0000-0000-0000-000000000002"
    assert workspace_role.status == "ACTIVE"
