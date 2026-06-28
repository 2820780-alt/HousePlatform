from app.models.audit_event import AuditEvent
from app.models.audit_log import AuditLog
from app.models.access_change_suggestion import AccessChangeSuggestion
from app.models.ai_recommendation import AIRecommendation
from app.models.brand import Brand
from app.models.catalog_product import CatalogProduct
from app.models.classification_rule import ClassificationRule
from app.models.construction_group import ConstructionGroup
from app.models.active_region import ActiveRegion
from app.models.dashboard_profile import DashboardProfile
from app.models.dashboard_widget import DashboardWidget
from app.models.dashboard_widget_placement import DashboardWidgetPlacement
from app.models.delivery_zone import DeliveryZone
from app.models.enums import (
    AccessStatus,
    AdminDecision,
    CatalogProductStatus,
    DocumentStatus,
    DocumentType,
    MatchCandidateStatus,
    MaterialStatus,
    RegionStatus,
    SourceActionType,
    SourceStatus,
    SourceType,
    SupplierStatus,
    TaskLogLevel,
    TaskResultType,
    TaskStatus,
    UnitType,
    UploadFileType,
    UploadRowStatus,
    UploadStatus,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from app.models.manufacturer import Manufacturer
from app.models.material import Material
from app.models.material_alias import MaterialAlias
from app.models.material_attribute import MaterialAttribute
from app.models.material_category import MaterialCategory
from app.models.material_category_schema import MaterialCategorySchema
from app.models.material_document import MaterialDocument
from app.models.material_match_candidate import MaterialMatchCandidate
from app.models.material_quality_issue import MaterialQualityIssue
from app.models.material_specification import MaterialSpecification
from app.models.material_type import MaterialType
from app.models.module_action_registry import ModuleActionRegistry
from app.models.module_migration_warning import ModuleMigrationWarning
from app.models.module_registry_version import ModuleRegistryVersion
from app.models.favorite_module import FavoriteModule
from app.models.function_access import FunctionAccess
from app.models.knowledge_candidate import KnowledgeCandidate
from app.models.knowledge_resource import KnowledgeResource
from app.models.knowledge_resource_link import KnowledgeResourceLink
from app.models.material_analog import MaterialAnalog
from app.models.module_access import ModuleAccess
from app.models.permission import Permission
from app.models.platform_module_registry import PlatformModuleRegistry
from app.models.platform_city import PlatformCity
from app.models.platform_region import PlatformRegion
from app.models.pilot_region import PilotRegion
from app.models.price_history import PriceHistory
from app.models.quick_action_registry_item import QuickActionRegistryItem
from app.models.role import Role
from app.models.role_dashboard_access_profile import RoleDashboardAccessProfile
from app.models.role_permission import RolePermission
from app.models.role_template import RoleTemplate
from app.models.rule_memory import RuleMemory
from app.models.source import Source
from app.models.source_task import SourceTask
from app.models.source_task_log import SourceTaskLog
from app.models.source_task_result import SourceTaskResult
from app.models.specification_template import SpecificationTemplate
from app.models.supplier import Supplier
from app.models.supplier_account import SupplierAccount
from app.models.supplier_branch import SupplierBranch
from app.models.supplier_price import SupplierPrice
from app.models.supplier_upload import SupplierUpload
from app.models.supplier_upload_row import SupplierUploadRow
from app.models.unit import Unit
from app.models.unit_alias import UnitAlias
from app.models.unit_conversion import UnitConversion
from app.models.unit_conversion_rule import UnitConversionRule
from app.models.user import User
from app.models.user_dashboard_layout import UserDashboardLayout
from app.models.user_preference import UserPreference
from app.models.user_role_assignment import UserRoleAssignment
from app.models.user_session import UserSession
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_role import WorkspaceRole
from app.models.widget_registry_item import WidgetRegistryItem

__all__ = [
    "AccessStatus",
    "AccessChangeSuggestion",
    "AdminDecision",
    "AIRecommendation",
    "ActiveRegion",
    "AuditEvent",
    "AuditLog",
    "Brand",
    "CatalogProduct",
    "CatalogProductStatus",
    "ClassificationRule",
    "ConstructionGroup",
    "DashboardProfile",
    "DashboardWidget",
    "DashboardWidgetPlacement",
    "DeliveryZone",
    "DocumentStatus",
    "DocumentType",
    "FavoriteModule",
    "FunctionAccess",
    "Manufacturer",
    "MatchCandidateStatus",
    "Material",
    "MaterialAlias",
    "MaterialAttribute",
    "MaterialCategory",
    "MaterialCategorySchema",
    "MaterialDocument",
    "MaterialMatchCandidate",
    "MaterialQualityIssue",
    "MaterialSpecification",
    "KnowledgeCandidate",
    "KnowledgeResource",
    "KnowledgeResourceLink",
    "MaterialAnalog",
    "MaterialType",
    "MaterialStatus",
    "ModuleAccess",
    "ModuleActionRegistry",
    "ModuleMigrationWarning",
    "ModuleRegistryVersion",
    "Permission",
    "PilotRegion",
    "PlatformCity",
    "PlatformModuleRegistry",
    "PlatformRegion",
    "PriceHistory",
    "QuickActionRegistryItem",
    "RegionStatus",
    "Role",
    "RoleDashboardAccessProfile",
    "RolePermission",
    "RoleTemplate",
    "RuleMemory",
    "Source",
    "SourceActionType",
    "SourceStatus",
    "SourceTask",
    "SourceTaskLog",
    "SourceTaskResult",
    "SourceType",
    "SpecificationTemplate",
    "Supplier",
    "SupplierAccount",
    "SupplierBranch",
    "SupplierPrice",
    "SupplierStatus",
    "SupplierUpload",
    "SupplierUploadRow",
    "TaskLogLevel",
    "TaskResultType",
    "TaskStatus",
    "Unit",
    "UnitAlias",
    "UnitConversion",
    "UnitConversionRule",
    "UnitType",
    "UploadFileType",
    "UploadRowStatus",
    "UploadStatus",
    "User",
    "UserDashboardLayout",
    "UserPreference",
    "UserRole",
    "UserRoleAssignment",
    "UserSession",
    "UserStatus",
    "VerificationStatus",
    "Workspace",
    "WorkspaceMember",
    "WorkspaceRole",
    "WidgetRegistryItem",
]
