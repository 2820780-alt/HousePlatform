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
from app.models.partner_portal import MODULE_08_PARTNER_PORTAL, PARTNER_PORTAL_BOUNDARY_STATUS


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
