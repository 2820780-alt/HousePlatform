from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Role, User, UserPreference, UserRoleAssignment, Workspace, WorkspaceMember
from app.models.enums import UserRole, UserStatus


MODULE3_DEMO_SEED_CODE = "MODULE3_DEMO_USERS_V1"
MODULE3_DEMO_ENVIRONMENTS = {"development", "demo", "staging"}
MODULE3_DEMO_METADATA_KEY = "module3_demo_seed_metadata"
MODULE3_DEMO_PASSWORD_HASH = "module3-demo-seed-password-hash"


@dataclass(frozen=True)
class Module3DemoMetadata:
    isDemo: bool = True
    isSeed: bool = True
    demoScenarioCode: str = MODULE3_DEMO_SEED_CODE
    environment: str = "development"
    sourceModuleCode: str = "MODULE_03_USERS_ROLES"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Module3DemoUserSpec:
    code: str
    email: str
    name: str
    role: UserRole
    status: UserStatus = UserStatus.ACTIVE
    role_codes: tuple[str, ...] = ()
    phone: str | None = None
    isSystemUser: bool = False
    typeCode: str = "USER"
    accessProfile: str = "standard"
    metadata: Module3DemoMetadata = field(default_factory=Module3DemoMetadata)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class Module3DemoCompanySpec:
    code: str
    slug: str
    name: str
    workspace_type: str
    status: str = "ACTIVE"
    owner_email: str | None = None
    organization_id: str | None = None
    city: str = "Краснодар"
    metadata: Module3DemoMetadata = field(default_factory=Module3DemoMetadata)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Module3DemoEmployeeSpec:
    user_email: str
    company_slug: str
    role_key: str
    status: str = "ACTIVE"
    metadata: Module3DemoMetadata = field(default_factory=Module3DemoMetadata)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Module3DemoSeedPlan:
    seedCode: str
    environment: str
    metadata: dict[str, Any]
    users: tuple[Module3DemoUserSpec, ...]
    companies: tuple[Module3DemoCompanySpec, ...]
    employees: tuple[Module3DemoEmployeeSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seedCode": self.seedCode,
            "environment": self.environment,
            "metadata": self.metadata,
            "users": [item.to_dict() for item in self.users],
            "companies": [item.to_dict() for item in self.companies],
            "employees": [item.to_dict() for item in self.employees],
        }


@dataclass(frozen=True)
class Module3DemoSeedResult:
    seedCode: str
    environment: str
    usersCreated: int = 0
    usersUpdated: int = 0
    companiesCreated: int = 0
    companiesUpdated: int = 0
    membershipsCreated: int = 0
    membershipsUpdated: int = 0
    rolesCreated: int = 0
    preferencesCreated: int = 0
    preferencesUpdated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Module3DemoSeedGuardError(RuntimeError):
    pass


def module3_demo_seed_is_allowed(
    *,
    app_env: str | None = None,
    node_env: str | None = None,
    enabled: bool | None = None,
) -> bool:
    effective_app_env = (app_env or os.getenv("APP_ENV") or settings.APP_ENV or "").lower()
    effective_node_env = (node_env if node_env is not None else os.getenv("NODE_ENV") or "").lower()
    effective_enabled = settings.ENABLE_MODULE3_DEMO_USERS if enabled is None else bool(enabled)
    if effective_node_env == "production" or effective_app_env == "production":
        return False
    return effective_enabled and effective_app_env in MODULE3_DEMO_ENVIRONMENTS


def require_module3_demo_seed_allowed(
    *,
    app_env: str | None = None,
    node_env: str | None = None,
    enabled: bool | None = None,
) -> None:
    if module3_demo_seed_is_allowed(app_env=app_env, node_env=node_env, enabled=enabled):
        return
    raise Module3DemoSeedGuardError(
        "Module №3 demo seed is disabled. Set ENABLE_MODULE3_DEMO_USERS=true in development/demo/staging."
    )


def build_module3_demo_seed_plan(environment: str = "development") -> Module3DemoSeedPlan:
    metadata = Module3DemoMetadata(environment=environment).to_dict()
    return Module3DemoSeedPlan(
        seedCode=MODULE3_DEMO_SEED_CODE,
        environment=environment,
        metadata=metadata,
        users=_demo_users(environment),
        companies=_demo_companies(environment),
        employees=_demo_employees(environment),
    )


async def seed_module3_demo_data(
    db: AsyncSession,
    *,
    environment: str | None = None,
    enabled: bool | None = None,
    node_env: str | None = None,
) -> Module3DemoSeedResult:
    effective_environment = environment or settings.APP_ENV
    require_module3_demo_seed_allowed(app_env=effective_environment, node_env=node_env, enabled=enabled)
    plan = build_module3_demo_seed_plan(effective_environment)
    result = _MutableSeedResult(seedCode=plan.seedCode, environment=plan.environment)

    roles = await _ensure_roles(db, plan, result)
    users_by_email: dict[str, User] = {}
    for user_spec in plan.users:
        user, created = await _get_or_create_user(db, user_spec)
        users_by_email[user_spec.email] = user
        if created:
            result.usersCreated += 1
        else:
            result.usersUpdated += 1
        await _upsert_user_demo_metadata(db, user, user_spec, result)
        await _ensure_user_roles(db, user, user_spec, roles)

    companies_by_slug: dict[str, Workspace] = {}
    for company_spec in plan.companies:
        owner = users_by_email.get(company_spec.owner_email or "")
        company, created = await _get_or_create_company(db, company_spec, owner)
        companies_by_slug[company_spec.slug] = company
        if created:
            result.companiesCreated += 1
        else:
            result.companiesUpdated += 1

    for employee_spec in plan.employees:
        user = users_by_email[employee_spec.user_email]
        company = companies_by_slug[employee_spec.company_slug]
        _, created = await _get_or_create_workspace_member(db, company, user, employee_spec)
        if created:
            result.membershipsCreated += 1
        else:
            result.membershipsUpdated += 1

    await db.flush()
    return result.freeze()


async def _ensure_roles(
    db: AsyncSession,
    plan: Module3DemoSeedPlan,
    result: "_MutableSeedResult",
) -> dict[str, Role]:
    role_codes = sorted({role for user in plan.users for role in user.role_codes})
    roles: dict[str, Role] = {}
    for role_code in role_codes:
        role = await _find_role(db, role_code)
        if role is None:
            role = Role(
                role_key=role_code,
                name=_role_title(role_code),
                description="DemoSeed role for Module №3 UI verification.",
                is_system=True,
                settings={"demoSeed": plan.metadata},
                status="ACTIVE",
            )
            db.add(role)
            await db.flush()
            result.rolesCreated += 1
        roles[role_code] = role
    return roles


async def _get_or_create_user(db: AsyncSession, spec: Module3DemoUserSpec) -> tuple[User, bool]:
    user = await _find_user_by_email(db, spec.email)
    created = user is None
    if user is None:
        user = User(
            email=spec.email,
            phone=spec.phone,
            name=spec.name,
            password_hash=MODULE3_DEMO_PASSWORD_HASH,
            role=spec.role,
            status=spec.status,
        )
        db.add(user)
        await db.flush()
    else:
        user.name = spec.name
        user.phone = spec.phone
        user.role = spec.role
        user.status = spec.status
        db.add(user)
    return user, created


async def _get_or_create_company(
    db: AsyncSession,
    spec: Module3DemoCompanySpec,
    owner: User | None,
) -> tuple[Workspace, bool]:
    workspace = await _find_workspace_by_slug(db, spec.slug)
    created = workspace is None
    settings_payload = {
        **spec.metadata.to_dict(),
        "demoCompanyCode": spec.code,
        "city": spec.city,
        "companyType": spec.workspace_type,
    }
    if workspace is None:
        workspace = Workspace(
            name=spec.name,
            slug=spec.slug,
            workspace_type=spec.workspace_type,
            owner_user_id=owner.id if owner else None,
            organization_id=spec.organization_id,
            is_active=spec.status == "ACTIVE",
            status=spec.status,
            description="DemoSeed company for Module №3 UI verification.",
            settings=settings_payload,
        )
        db.add(workspace)
        await db.flush()
    else:
        workspace.name = spec.name
        workspace.workspace_type = spec.workspace_type
        workspace.owner_user_id = owner.id if owner else workspace.owner_user_id
        workspace.organization_id = spec.organization_id
        workspace.is_active = spec.status == "ACTIVE"
        workspace.status = spec.status
        workspace.settings = {**(workspace.settings or {}), **settings_payload}
        db.add(workspace)
    return workspace, created


async def _get_or_create_workspace_member(
    db: AsyncSession,
    company: Workspace,
    user: User,
    spec: Module3DemoEmployeeSpec,
) -> tuple[WorkspaceMember, bool]:
    member = await _find_workspace_member(db, company, user)
    created = member is None
    permissions = {**spec.metadata.to_dict(), "demoEmployeeRole": spec.role_key}
    if member is None:
        member = WorkspaceMember(
            workspace_id=company.id,
            user_id=user.id,
            role_key=spec.role_key,
            role_code=spec.role_key,
            permissions=permissions,
            status=spec.status,
        )
        db.add(member)
        await db.flush()
    else:
        member.role_key = spec.role_key
        member.role_code = spec.role_key
        member.permissions = {**(member.permissions or {}), **permissions}
        member.status = spec.status
        db.add(member)
    return member, created


async def _ensure_user_roles(
    db: AsyncSession,
    user: User,
    spec: Module3DemoUserSpec,
    roles: dict[str, Role],
) -> None:
    for role_code in spec.role_codes:
        role = roles[role_code]
        existing = await _find_user_role_assignment(db, user, role)
        if existing is None:
            db.add(UserRoleAssignment(user_id=user.id, role_id=role.id, status="ACTIVE"))


async def _upsert_user_demo_metadata(
    db: AsyncSession,
    user: User,
    spec: Module3DemoUserSpec,
    result: "_MutableSeedResult",
) -> None:
    preference = await _find_user_demo_metadata(db, user)
    payload = {
        **spec.metadata.to_dict(),
        "demoUserCode": spec.code,
        "isSystemUser": spec.isSystemUser,
        "typeCode": spec.typeCode,
        "accessProfile": spec.accessProfile,
        "email": spec.email,
    }
    if preference is None:
        preference = UserPreference(
            user_id=user.id,
            preference_key=MODULE3_DEMO_METADATA_KEY,
            value=payload,
            status="ACTIVE",
        )
        db.add(preference)
        await db.flush()
        result.preferencesCreated += 1
    else:
        preference.value = {**(preference.value or {}), **payload}
        preference.status = "ACTIVE"
        db.add(preference)
        result.preferencesUpdated += 1


async def _find_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def _find_workspace_by_slug(db: AsyncSession, slug: str) -> Workspace | None:
    result = await db.execute(select(Workspace).where(Workspace.slug == slug))
    return result.scalar_one_or_none()


async def _find_workspace_member(db: AsyncSession, company: Workspace, user: User) -> WorkspaceMember | None:
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == company.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    return result.scalar_one_or_none()


async def _find_role(db: AsyncSession, role_code: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.role_key == role_code))
    return result.scalar_one_or_none()


async def _find_user_role_assignment(db: AsyncSession, user: User, role: Role) -> UserRoleAssignment | None:
    result = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user.id,
            UserRoleAssignment.role_id == role.id,
        )
    )
    return result.scalar_one_or_none()


async def _find_user_demo_metadata(db: AsyncSession, user: User) -> UserPreference | None:
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == user.id,
            UserPreference.preference_key == MODULE3_DEMO_METADATA_KEY,
        )
    )
    return result.scalar_one_or_none()


def _demo_users(environment: str) -> tuple[Module3DemoUserSpec, ...]:
    meta = lambda code: Module3DemoMetadata(demoScenarioCode=code, environment=environment)
    return (
        Module3DemoUserSpec("customer_active", "demo.customer.active@atom.local", "Заказчик Активный", UserRole.CUSTOMER, role_codes=("CUSTOMER",), typeCode="CUSTOMER", metadata=meta("MODULE3_CUSTOMER_ACTIVE")),
        Module3DemoUserSpec("customer_blocked", "demo.customer.blocked@atom.local", "Заказчик Заблокированный", UserRole.CUSTOMER, UserStatus.BLOCKED, role_codes=("CUSTOMER",), typeCode="CUSTOMER", metadata=meta("MODULE3_CUSTOMER_BLOCKED")),
        Module3DemoUserSpec("supplier_active", "demo.supplier.active@atom.local", "Кубань Материалы", UserRole.SUPPLIER, role_codes=("SUPPLIER",), typeCode="SUPPLIER", metadata=meta("MODULE3_SUPPLIER_ACTIVE")),
        Module3DemoUserSpec("supplier_moderation", "demo.supplier.moderation@atom.local", "БетонПоставка Кубань", UserRole.SUPPLIER, UserStatus.INACTIVE, role_codes=("SUPPLIER",), typeCode="SUPPLIER", metadata=meta("MODULE3_SUPPLIER_MODERATION")),
        Module3DemoUserSpec("supplier_blocked", "demo.supplier.blocked@atom.local", "Поставщик Заблокированный", UserRole.SUPPLIER, UserStatus.BLOCKED, role_codes=("SUPPLIER",), typeCode="SUPPLIER", metadata=meta("MODULE3_SUPPLIER_BLOCKED")),
        Module3DemoUserSpec("construction_company_active", "demo.company.active@atom.local", "СтройПроект Юг", UserRole.CONTRACTOR, role_codes=("CONTRACTOR", "COMPANY_ADMIN"), typeCode="CONSTRUCTION_COMPANY", metadata=meta("MODULE3_COMPANY_ACTIVE")),
        Module3DemoUserSpec("construction_company_moderation", "demo.company.moderation@atom.local", "Строительная Компания На Модерации", UserRole.CONTRACTOR, UserStatus.INACTIVE, role_codes=("CONTRACTOR",), typeCode="CONSTRUCTION_COMPANY", metadata=meta("MODULE3_COMPANY_MODERATION")),
        Module3DemoUserSpec("construction_company_blocked", "demo.company.blocked@atom.local", "МонолитСтрой", UserRole.CONTRACTOR, UserStatus.BLOCKED, role_codes=("CONTRACTOR",), typeCode="CONSTRUCTION_COMPANY", metadata=meta("MODULE3_COMPANY_BLOCKED")),
        Module3DemoUserSpec("independent_engineer_active", "demo.engineer.active@atom.local", "Инженер Самостоятельный", UserRole.CONTRACTOR, role_codes=("ENGINEER_DESIGNER",), typeCode="SPECIALIST", metadata=meta("MODULE3_ENGINEER_ACTIVE")),
        Module3DemoUserSpec("independent_engineer_limited", "demo.engineer.limited@atom.local", "Инженер Ограниченный", UserRole.CONTRACTOR, role_codes=("ENGINEER_DESIGNER",), typeCode="SPECIALIST", accessProfile="limited", metadata=meta("MODULE3_ENGINEER_LIMITED")),
        Module3DemoUserSpec("platform_admin", "platform-admin@atom.local", "platform-admin", UserRole.ADMIN, role_codes=("PLATFORM_ADMIN",), isSystemUser=True, typeCode="SYSTEM_USER", metadata=meta("MODULE3_SYSTEM_PLATFORM_ADMIN")),
        Module3DemoUserSpec("super_admin", "super-admin@atom.local", "super-admin", UserRole.ADMIN, role_codes=("SUPER_ADMIN",), isSystemUser=True, typeCode="SYSTEM_USER", metadata=meta("MODULE3_SYSTEM_SUPER_ADMIN")),
        Module3DemoUserSpec("moderator", "moderator@atom.local", "moderator", UserRole.ADMIN, role_codes=("MODERATOR",), isSystemUser=True, typeCode="SYSTEM_USER", metadata=meta("MODULE3_SYSTEM_MODERATOR")),
        Module3DemoUserSpec("support_admin", "support-admin@atom.local", "support-admin", UserRole.ADMIN, role_codes=("SUPPORT_ADMIN", "PLATFORM_ADMIN"), isSystemUser=True, typeCode="SYSTEM_USER", metadata=meta("MODULE3_SYSTEM_SUPPORT_ADMIN")),
        Module3DemoUserSpec("employee_lead", "demo.spug.lead@atom.local", "Иванов Петр Сергеевич", UserRole.CONTRACTOR, role_codes=("CONTRACTOR",), typeCode="SPECIALIST", metadata=meta("MODULE3_SPUG_EMPLOYEE_LEAD")),
        Module3DemoUserSpec("employee_engineer", "demo.spug.engineer@atom.local", "Петрова Елена Викторовна", UserRole.CONTRACTOR, role_codes=("ENGINEER_DESIGNER",), typeCode="SPECIALIST", metadata=meta("MODULE3_SPUG_EMPLOYEE_ENGINEER")),
        Module3DemoUserSpec("employee_buyer", "demo.spug.buyer@atom.local", "Кузнецов Андрей Михайлович", UserRole.SUPPLIER, role_codes=("BUYER",), typeCode="SPECIALIST", metadata=meta("MODULE3_SPUG_EMPLOYEE_BUYER")),
        Module3DemoUserSpec("employee_manager", "demo.spug.manager@atom.local", "Смирнова Ольга Николаевна", UserRole.CONTRACTOR, role_codes=("PROJECT_MANAGER",), typeCode="SPECIALIST", metadata=meta("MODULE3_SPUG_EMPLOYEE_MANAGER")),
        Module3DemoUserSpec("employee_estimator", "demo.spug.estimator@atom.local", "Волков Дмитрий Алексеевич", UserRole.CONTRACTOR, role_codes=("ESTIMATOR",), typeCode="SPECIALIST", accessProfile="limited", metadata=meta("MODULE3_SPUG_EMPLOYEE_ESTIMATOR")),
    )


def _demo_companies(environment: str) -> tuple[Module3DemoCompanySpec, ...]:
    meta = lambda code: Module3DemoMetadata(demoScenarioCode=code, environment=environment)
    return (
        Module3DemoCompanySpec("spug_active", "demo-stroyproekt-yug", "ООО «СтройПроект Юг»", "CONSTRUCTION_COMPANY", owner_email="demo.company.active@atom.local", organization_id="2312345678", metadata=meta("MODULE3_COMPANY_STROYPROEKT_YUG_ACTIVE")),
        Module3DemoCompanySpec("kuban_materials_active", "demo-kuban-materials", "ООО «Кубань Материалы»", "SUPPLIER", owner_email="demo.supplier.active@atom.local", organization_id="2311111111", metadata=meta("MODULE3_SUPPLIER_KUBAN_MATERIALS_ACTIVE")),
        Module3DemoCompanySpec("betonpostavka_moderation", "demo-betonpostavka-kuban", "ООО «БетонПоставка Кубань»", "SUPPLIER", status="PENDING_REVIEW", owner_email="demo.supplier.moderation@atom.local", organization_id="2322222222", metadata=meta("MODULE3_SUPPLIER_BETONPOSTAVKA_MODERATION")),
        Module3DemoCompanySpec("monolit_blocked", "demo-monolitstroy", "ООО «МонолитСтрой»", "CONSTRUCTION_COMPANY", status="BLOCKED", owner_email="demo.company.blocked@atom.local", organization_id="2333333333", metadata=meta("MODULE3_COMPANY_MONOLITSTROY_BLOCKED")),
    )


def _demo_employees(environment: str) -> tuple[Module3DemoEmployeeSpec, ...]:
    meta = lambda code: Module3DemoMetadata(demoScenarioCode=code, environment=environment)
    return (
        Module3DemoEmployeeSpec("demo.spug.lead@atom.local", "demo-stroyproekt-yug", "COMPANY_LEAD", metadata=meta("MODULE3_SPUG_ROLE_LEAD")),
        Module3DemoEmployeeSpec("demo.spug.engineer@atom.local", "demo-stroyproekt-yug", "ENGINEER", metadata=meta("MODULE3_SPUG_ROLE_ENGINEER")),
        Module3DemoEmployeeSpec("demo.spug.buyer@atom.local", "demo-stroyproekt-yug", "BUYER", metadata=meta("MODULE3_SPUG_ROLE_BUYER")),
        Module3DemoEmployeeSpec("demo.spug.manager@atom.local", "demo-stroyproekt-yug", "PROJECT_MANAGER", metadata=meta("MODULE3_SPUG_ROLE_MANAGER")),
        Module3DemoEmployeeSpec("demo.spug.estimator@atom.local", "demo-stroyproekt-yug", "ESTIMATOR", metadata=meta("MODULE3_SPUG_ROLE_ESTIMATOR")),
    )


def _role_title(role_code: str) -> str:
    return role_code.replace("_", " ").title()


@dataclass
class _MutableSeedResult:
    seedCode: str
    environment: str
    usersCreated: int = 0
    usersUpdated: int = 0
    companiesCreated: int = 0
    companiesUpdated: int = 0
    membershipsCreated: int = 0
    membershipsUpdated: int = 0
    rolesCreated: int = 0
    preferencesCreated: int = 0
    preferencesUpdated: int = 0

    def freeze(self) -> Module3DemoSeedResult:
        return Module3DemoSeedResult(**asdict(self))
