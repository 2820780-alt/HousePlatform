from app.models import (
    ActiveCabinetContext,
    CabinetBlockCatalog,
    CabinetBlockRule,
    CabinetBranch,
    CabinetContact,
    CabinetDashboardContext,
    CabinetDashboardPreset,
    CabinetDeliveryZone,
    CabinetDocument,
    CabinetEmployee,
    CabinetEmployeeRole,
    CabinetMainFocus,
    CabinetMembership,
    CabinetModuleShortcut,
    CabinetModerationLog,
    CabinetObjectLink,
    CabinetPrimaryGoal,
    CabinetQuickAction,
    CabinetServiceRegion,
    CabinetSummaryDTO,
    CabinetUpgradeHistory,
    CabinetUpgradeRequest,
    CabinetVerification,
    CabinetWidgetPreference,
    ConstructionCompanyCabinet,
    CustomerCabinet,
    ObjectOfferSettings,
    ObjectVisibilitySettings,
    ParticipantObjectAccess,
    ParticipantCabinet,
    SpecialistCabinet,
    SpecialistToCompanyLink,
    SupplierCabinet,
    SupplierCabinetLink,
    UserCabinetLink,
    WorksCostsCabinetLink,
)
from app.models.partner_portal import (
    MODULE_08_PARTNER_PORTAL,
    PARTNER_PORTAL_BOUNDARY_STATUS,
    PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE,
)


MODULE8_TYPES = (
    ParticipantCabinet,
    CustomerCabinet,
    SupplierCabinet,
    SupplierCabinetLink,
    WorksCostsCabinetLink,
    ConstructionCompanyCabinet,
    SpecialistCabinet,
    CabinetUpgradeRequest,
    CabinetUpgradeHistory,
    SpecialistToCompanyLink,
    CabinetVerification,
    CabinetModerationLog,
    CabinetEmployee,
    CabinetEmployeeRole,
    CabinetMembership,
    CabinetContact,
    CabinetBranch,
    CabinetServiceRegion,
    CabinetDeliveryZone,
    CabinetDocument,
    UserCabinetLink,
    ActiveCabinetContext,
    CabinetDashboardContext,
    CabinetDashboardPreset,
    CabinetBlockCatalog,
    CabinetBlockRule,
    CabinetPrimaryGoal,
    CabinetMainFocus,
    CabinetQuickAction,
    CabinetWidgetPreference,
    CabinetModuleShortcut,
    CabinetObjectLink,
    ParticipantObjectAccess,
    ObjectVisibilitySettings,
    ObjectOfferSettings,
    CabinetSummaryDTO,
)

REQUIRED_COLUMNS = {
    "id",
    "module_code",
    "feature_code",
    "status",
    "created_at",
    "updated_at",
    "workspace_id",
    "active_region_code",
    "source_module_code",
    "target_module_code",
}


def test_module8_types_have_required_boundary_columns():
    for model in MODULE8_TYPES:
        columns = set(model.__table__.columns.keys())
        assert REQUIRED_COLUMNS.issubset(columns), model.__name__


def test_module8_types_use_partner_portal_module_code_by_default():
    for model in MODULE8_TYPES:
        default = model.__table__.columns["module_code"].default
        assert default is not None, model.__name__
        assert default.arg == MODULE_08_PARTNER_PORTAL


def test_partner_portal_module_code_is_legacy_draft_boundary_marker():
    assert PARTNER_PORTAL_BOUNDARY_STATUS == "LEGACY_DRAFT_BOUNDARY"


def test_module8_quick_action_fields_are_deprecated_compatibility_only():
    preset_columns = CabinetDashboardPreset.__table__.columns
    rule_columns = CabinetBlockRule.__table__.columns
    action_columns = CabinetQuickAction.__table__.columns

    for column in (
        preset_columns["atom_card_actions"],
        preset_columns["quick_action_codes"],
        rule_columns["required_quick_action_code"],
        action_columns["quick_action_code"],
        action_columns["required_action_code"],
        action_columns["is_recommended"],
    ):
        assert column.info["deprecated"] == PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE

    assert CabinetQuickAction.__doc__
    assert "not an active source" in CabinetQuickAction.__doc__