import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


MODULE_08_PARTNER_PORTAL = "MODULE_08_PARTNER_PORTAL"
PARTICIPANT_CABINET_CONTEXT_CODE = "PARTICIPANT_CABINET_CONTEXT"
PARTNER_PORTAL_BOUNDARY_STATUS = "LEGACY_DRAFT_BOUNDARY"
PARTNER_PORTAL_BOUNDARY_NOTE = (
    "Participant cabinets are a future separate contour; MODULE_08_PARTNER_PORTAL "
    "is a legacy draft source code and is not the final Module 8 boundary."
)
PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE = (
    "Deprecated compatibility field. Module 8 cabinet presets must not seed, "
    "recommend, or render quick actions; saved/pinned actions live in user_module_quick_actions."
)



class Module8RecordMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_code: Mapped[str] = mapped_column(
        String(120),
        default=MODULE_08_PARTNER_PORTAL,
        nullable=False,
        index=True,
    )
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    active_region_code: Mapped[str | None] = mapped_column(String(80), index=True)
    source_module_code: Mapped[str | None] = mapped_column(String(120), index=True)
    target_module_code: Mapped[str | None] = mapped_column(String(120), index=True)


class ParticipantCabinet(Module8RecordMixin, Base):
    __tablename__ = "module08_participant_cabinets"

    cabinet_code: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    cabinet_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    business_role: Mapped[str | None] = mapped_column(String(120), index=True)
    primary_goal_code: Mapped[str | None] = mapped_column(String(160), index=True)
    main_focus_code: Mapped[str | None] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CustomerCabinet(Module8RecordMixin, Base):
    __tablename__ = "module08_customer_cabinets"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    active_object_id: Mapped[str | None] = mapped_column(String(160), index=True)
    default_preset_code: Mapped[str] = mapped_column(
        String(160),
        default="CustomerDashboardPreset",
        nullable=False,
        index=True,
    )
    main_focus_code: Mapped[str] = mapped_column(
        String(160),
        default="OBJECT_IMAGE",
        nullable=False,
        index=True,
    )
    object_visibility_settings: Mapped[dict | None] = mapped_column(JSON)
    offer_settings: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class SupplierCabinet(Module8RecordMixin, Base):
    __tablename__ = "module08_supplier_cabinets"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    organization_id: Mapped[str | None] = mapped_column(String(160), index=True)
    default_preset_code: Mapped[str] = mapped_column(
        String(160),
        default="SupplierDashboardPreset",
        nullable=False,
        index=True,
    )
    main_focus_code: Mapped[str] = mapped_column(
        String(160),
        default="SALES_PRICES_REQUESTS",
        nullable=False,
        index=True,
    )
    mvp_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    supply_region_settings: Mapped[dict | None] = mapped_column(JSON)
    branch_settings: Mapped[dict | None] = mapped_column(JSON)
    contact_settings: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class SupplierCabinetLink(Module8RecordMixin, Base):
    __tablename__ = "module08_supplier_cabinet_links"

    supplier_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    link_status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(
        String(40),
        default="UNVERIFIED",
        nullable=False,
        index=True,
    )
    source_module_code: Mapped[str] = mapped_column(
        String(120),
        default="MODULE_01_MATERIAL_HUB",
        nullable=False,
        index=True,
    )
    target_module_code: Mapped[str] = mapped_column(
        String(120),
        default=MODULE_08_PARTNER_PORTAL,
        nullable=False,
        index=True,
    )
    link_payload: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class WorksCostsCabinetLink(Module8RecordMixin, Base):
    __tablename__ = "module08_works_costs_cabinet_links"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    work_rate_source_id: Mapped[str | None] = mapped_column(String(160), index=True)
    contractor_profile_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    work_producer_ref: Mapped[str | None] = mapped_column(String(160), index=True)
    link_status: Mapped[str] = mapped_column(String(40), default="PENDING", nullable=False, index=True)
    source_module_code: Mapped[str] = mapped_column(
        String(120),
        default="MODULE_04_WORKS_COSTS",
        nullable=False,
        index=True,
    )
    target_module_code: Mapped[str] = mapped_column(
        String(120),
        default=MODULE_08_PARTNER_PORTAL,
        nullable=False,
        index=True,
    )
    link_payload: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class ConstructionCompanyCabinet(Module8RecordMixin, Base):
    __tablename__ = "module08_construction_company_cabinets"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    organization_id: Mapped[str | None] = mapped_column(String(160), index=True)
    default_preset_code: Mapped[str] = mapped_column(
        String(160),
        default="ConstructionCompanyDashboardPreset",
        nullable=False,
        index=True,
    )
    main_focus_code: Mapped[str] = mapped_column(
        String(160),
        default="COMPANY_PROJECTS_OBJECTS",
        nullable=False,
        index=True,
    )
    mvp_roles: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    project_visibility_settings: Mapped[dict | None] = mapped_column(JSON)
    employee_settings: Mapped[dict | None] = mapped_column(JSON)
    object_access_settings: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class SpecialistCabinet(Module8RecordMixin, Base):
    __tablename__ = "module08_specialist_cabinets"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    specialization_code: Mapped[str | None] = mapped_column(String(120), index=True)
    default_preset_code: Mapped[str] = mapped_column(
        String(160),
        default="SpecialistDashboardPreset",
        nullable=False,
        index=True,
    )
    main_focus_code: Mapped[str] = mapped_column(
        String(160),
        default="SPECIALIST_WORKFLOW",
        nullable=False,
        index=True,
    )
    specialization_presets: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    assigned_object_settings: Mapped[dict | None] = mapped_column(JSON)
    task_context_settings: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetUpgradeRequest(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_upgrade_requests"

    upgrade_request_code: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    source_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    source_cabinet_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_cabinet_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    target_company_title: Mapped[str | None] = mapped_column(String(255))
    request_status: Mapped[str] = mapped_column(String(40), default="REQUESTED", nullable=False, index=True)
    preserve_source_cabinet: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    approved_at: Mapped[datetime | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    request_payload: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetUpgradeHistory(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_upgrade_history"

    upgrade_request_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    source_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    target_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    previous_status: Mapped[str | None] = mapped_column(String(40), index=True)
    new_status: Mapped[str | None] = mapped_column(String(40), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    event_payload: Mapped[dict | None] = mapped_column(JSON)


class SpecialistToCompanyLink(Module8RecordMixin, Base):
    __tablename__ = "module08_specialist_to_company_links"

    specialist_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    construction_company_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    relation_type: Mapped[str] = mapped_column(
        String(80),
        default="FOUNDER_OWNER",
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    linked_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetVerification(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_verifications"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    verification_status: Mapped[str] = mapped_column(
        String(40),
        default="DRAFT",
        nullable=False,
        index=True,
    )
    verification_level: Mapped[str] = mapped_column(
        String(40),
        default="NOT_VERIFIED",
        nullable=False,
        index=True,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column()
    next_review_at: Mapped[datetime | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    verification_payload: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetModerationLog(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_moderation_logs"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    moderation_event: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(40), index=True)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    previous_level: Mapped[str | None] = mapped_column(String(40), index=True)
    new_level: Mapped[str | None] = mapped_column(String(40), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    event_payload: Mapped[dict | None] = mapped_column(JSON)


class CabinetEmployee(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_employees"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(80), index=True)
    position_title: Mapped[str | None] = mapped_column(String(160), index=True)
    employee_status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    business_role_code: Mapped[str | None] = mapped_column(String(120), index=True)
    profile_payload: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetEmployeeRole(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_employee_roles"

    role_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    user_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_default_for_cabinet_type: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetMembership(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_memberships"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    business_role_code: Mapped[str | None] = mapped_column(String(120), index=True)
    membership_status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    joined_at: Mapped[datetime | None] = mapped_column()
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetContact(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_contacts"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    contact_type: Mapped[str] = mapped_column(String(80), default="GENERAL", nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    contact_person: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(80), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    messenger: Mapped[str | None] = mapped_column(String(160))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    visibility_scope: Mapped[str] = mapped_column(String(80), default="CABINET", nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetBranch(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_branches"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    branch_code: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    branch_type: Mapped[str | None] = mapped_column(String(80), index=True)
    region_code: Mapped[str | None] = mapped_column(String(80), index=True)
    city_id: Mapped[str | None] = mapped_column(String(160), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    contact_payload: Mapped[dict | None] = mapped_column(JSON)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetServiceRegion(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_service_regions"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    region_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    region_title: Mapped[str | None] = mapped_column(String(255))
    service_type: Mapped[str | None] = mapped_column(String(120), index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    rules: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetDeliveryZone(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_delivery_zones"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    delivery_zone_code: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    region_code: Mapped[str | None] = mapped_column(String(80), index=True)
    city_id: Mapped[str | None] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_type: Mapped[str | None] = mapped_column(String(120), index=True)
    coverage_payload: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetDocument(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_documents"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    document_code: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    document_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ref: Mapped[str | None] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(500))
    document_status: Mapped[str] = mapped_column(String(40), default="DRAFT", nullable=False, index=True)
    issued_at: Mapped[datetime | None] = mapped_column()
    expires_at: Mapped[datetime | None] = mapped_column()
    visibility_scope: Mapped[str] = mapped_column(String(80), default="CABINET", nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class UserCabinetLink(Module8RecordMixin, Base):
    __tablename__ = "module08_user_cabinet_links"

    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    role_code: Mapped[str | None] = mapped_column(String(120), index=True)
    business_role: Mapped[str | None] = mapped_column(String(120), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class ActiveCabinetContext(Module8RecordMixin, Base):
    __tablename__ = "module08_active_cabinet_contexts"

    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    cabinet_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    business_role: Mapped[str | None] = mapped_column(String(120), index=True)
    active_object_id: Mapped[str | None] = mapped_column(String(160), index=True)
    current_block_code: Mapped[str | None] = mapped_column(String(160), index=True)
    primary_goal_code: Mapped[str | None] = mapped_column(String(160), index=True)
    main_focus_code: Mapped[str | None] = mapped_column(String(160), index=True)
    context_payload: Mapped[dict | None] = mapped_column(JSON)


class CabinetDashboardContext(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_dashboard_contexts"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    preset_code: Mapped[str | None] = mapped_column(String(160), index=True)
    layout_code: Mapped[str | None] = mapped_column(String(160), index=True)
    dashboard_mode: Mapped[str | None] = mapped_column(String(80), index=True)
    topbar_context: Mapped[dict | None] = mapped_column(JSON)
    widget_context: Mapped[dict | None] = mapped_column(JSON)
    atom_map_context: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetDashboardPreset(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_dashboard_presets"

    preset_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    topbar: Mapped[dict | None] = mapped_column(JSON)
    widget_zones: Mapped[dict | None] = mapped_column(JSON)
    atom_card_actions: Mapped[dict | None] = mapped_column(
        JSON,
        info={"deprecated": PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE},
    )
    quick_action_codes: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        info={"deprecated": PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE},
    )
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetBlockCatalog(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_block_catalogs"

    catalog_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    block_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetBlockRule(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_block_rules"

    rule_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    block_code: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    required_feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    required_widget_code: Mapped[str | None] = mapped_column(String(160), index=True)
    required_quick_action_code: Mapped[str | None] = mapped_column(
        String(160),
        index=True,
        info={"deprecated": PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE},
    )
    visibility_rule: Mapped[dict | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetPrimaryGoal(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_primary_goals"

    goal_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetMainFocus(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_main_focuses"

    focus_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    primary_goal_code: Mapped[str | None] = mapped_column(String(160), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetQuickAction(Module8RecordMixin, Base):
    """Legacy compatibility table; not an active source for shortcuts."""

    __tablename__ = "module08_cabinet_quick_actions"

    quick_action_code: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        index=True,
        info={"deprecated": PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE},
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    required_action_code: Mapped[str | None] = mapped_column(
        String(120),
        index=True,
        info={"deprecated": PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE},
    )
    route: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    is_recommended: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        info={"deprecated": PARTNER_PORTAL_QUICK_ACTION_COMPATIBILITY_NOTE},
    )
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetWidgetPreference(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_widget_preferences"

    widget_code: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    zone_code: Mapped[str | None] = mapped_column(String(80), index=True)
    default_size: Mapped[str | None] = mapped_column(String(30), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    is_visible_by_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetModuleShortcut(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_module_shortcuts"

    shortcut_code: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    route: Mapped[str | None] = mapped_column(String(255))
    icon: Mapped[str | None] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=1000, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetObjectLink(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_object_links"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    object_type: Mapped[str | None] = mapped_column(String(80), index=True)
    relation_type: Mapped[str | None] = mapped_column(String(80), index=True)
    visibility_scope: Mapped[str | None] = mapped_column(String(80), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    settings: Mapped[dict | None] = mapped_column(JSON)


class ParticipantObjectAccess(Module8RecordMixin, Base):
    __tablename__ = "module08_participant_object_access"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    participant_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    participant_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    object_type: Mapped[str | None] = mapped_column(String(80), index=True)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    visibility_scope: Mapped[str] = mapped_column(String(80), default="LIMITED", nullable=False, index=True)
    access_status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    allowed_data_scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    denied_data_scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_owner_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    permission_source_module_code: Mapped[str] = mapped_column(
        String(120),
        default="MODULE_03_USERS_ROLES",
        nullable=False,
        index=True,
    )
    visibility_source_module_code: Mapped[str] = mapped_column(
        String(120),
        default=MODULE_08_PARTNER_PORTAL,
        nullable=False,
        index=True,
    )
    rules: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class ObjectVisibilitySettings(Module8RecordMixin, Base):
    __tablename__ = "module08_object_visibility_settings"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    visibility_scope: Mapped[str] = mapped_column(String(80), default="PRIVATE", nullable=False, index=True)
    visible_to_cabinet_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    visible_to_role_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    show_in_selections: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_region: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    show_exact_address: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_technology: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_estimate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_procurement_need: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_customer_contacts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_financial_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    show_personal_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    rules: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class ObjectOfferSettings(Module8RecordMixin, Base):
    __tablename__ = "module08_object_offer_settings"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    target_object_id: Mapped[str | None] = mapped_column(String(160), index=True)
    target_cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    offer_scope: Mapped[str] = mapped_column(String(80), default="NONE", nullable=False, index=True)
    allowed_offer_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    can_send_offer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    can_receive_offers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    offer_visibility_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    offer_contact_policy: Mapped[str] = mapped_column(String(80), default="HIDDEN", nullable=False, index=True)
    offer_source_module: Mapped[str] = mapped_column(
        String(120),
        default=MODULE_08_PARTNER_PORTAL,
        nullable=False,
        index=True,
    )
    receive_supplier_offers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    receive_construction_company_offers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    receive_specialist_offers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    rules: Mapped[dict | None] = mapped_column(JSON)
    settings: Mapped[dict | None] = mapped_column(JSON)


class CabinetSummaryDTO(Module8RecordMixin, Base):
    __tablename__ = "module08_cabinet_summary_dtos"

    cabinet_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    cabinet_type: Mapped[str | None] = mapped_column(String(80), index=True)
    business_role: Mapped[str | None] = mapped_column(String(120), index=True)
    primary_goal_code: Mapped[str | None] = mapped_column(String(160), index=True)
    main_focus_code: Mapped[str | None] = mapped_column(String(160), index=True)
    linked_object_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    summary_payload: Mapped[dict | None] = mapped_column(JSON)


__all__ = [
    "MODULE_08_PARTNER_PORTAL",
    "ParticipantCabinet",
    "CustomerCabinet",
    "SupplierCabinet",
    "SupplierCabinetLink",
    "WorksCostsCabinetLink",
    "ConstructionCompanyCabinet",
    "SpecialistCabinet",
    "CabinetUpgradeRequest",
    "CabinetUpgradeHistory",
    "SpecialistToCompanyLink",
    "CabinetVerification",
    "CabinetModerationLog",
    "CabinetEmployee",
    "CabinetEmployeeRole",
    "CabinetMembership",
    "CabinetContact",
    "CabinetBranch",
    "CabinetServiceRegion",
    "CabinetDeliveryZone",
    "CabinetDocument",
    "UserCabinetLink",
    "ActiveCabinetContext",
    "CabinetDashboardContext",
    "CabinetDashboardPreset",
    "CabinetBlockCatalog",
    "CabinetBlockRule",
    "CabinetPrimaryGoal",
    "CabinetMainFocus",
    "CabinetQuickAction",
    "CabinetWidgetPreference",
    "CabinetModuleShortcut",
    "CabinetObjectLink",
    "ParticipantObjectAccess",
    "ObjectVisibilitySettings",
    "ObjectOfferSettings",
    "CabinetSummaryDTO",
]
