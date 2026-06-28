from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.access_context_for_cabinet import AccessContextForCabinet


SOURCE_MODULE_CODE = "MODULE_08_PARTNER_PORTAL"
MODULE8_BRIDGE_WARNING = (
    "Кабинеты управляются Module №8. Module №3 показывает только preview через adapter/mock "
    "и продолжает управлять ролями, permissions, workspace, widget access и quick action access."
)
MODULE8_EMPTY_STATE = (
    "Кабинеты участников еще не подключены. После реализации Module №8 здесь будут отображаться "
    "активный кабинет, бизнес-роль, связанные объекты и настройки видимости."
)


@dataclass(frozen=True)
class Module8CabinetPreviewItem:
    cabinetId: str
    cabinetType: str
    title: str
    status: str
    isActive: bool
    businessRole: str | None = None
    workspaceId: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Module8LinkedObjectPreviewItem:
    objectId: str
    title: str
    relationType: str
    visibilityScope: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Module8DashboardContextPreview:
    mainFocus: str | None = None
    recommendedBlocks: list[str] = field(default_factory=list)
    recommendedWidgetCodes: list[str] = field(default_factory=list)
    recommendedQuickActionCodes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Module8CabinetAdminPreviewDTO:
    userId: str
    sourceModuleCode: str = SOURCE_MODULE_CODE
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    cabinets: list[Module8CabinetPreviewItem] = field(default_factory=list)
    activeCabinetId: str | None = None
    activeCabinetType: str | None = None
    linkedObjects: list[Module8LinkedObjectPreviewItem] = field(default_factory=list)
    dashboardContextPreview: Module8DashboardContextPreview = field(default_factory=Module8DashboardContextPreview)
    isModule8Connected: bool = False
    isMock: bool = True
    warning: str = MODULE8_BRIDGE_WARNING
    emptyState: str | None = MODULE8_EMPTY_STATE
    editableInModule03: list[str] = field(default_factory=lambda: [
        "roles",
        "permissions",
        "workspace",
        "module access",
        "widget access",
        "quick action access",
        "role/dashboard access profile",
        "preview role",
    ])
    module8OwnedEntities: list[str] = field(default_factory=lambda: [
        "ParticipantCabinet",
        "CustomerCabinet",
        "SupplierCabinet",
        "ConstructionCompanyCabinet",
        "SpecialistCabinet",
        "ActiveCabinetContext",
        "ObjectVisibilitySettings",
        "ObjectOfferSettings",
        "CabinetDashboardPreset",
        "CabinetBlockCatalog",
        "CabinetDocument",
        "CabinetBranch",
        "CabinetVerification",
    ])

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["cabinets"] = [item.to_dict() for item in self.cabinets]
        data["linkedObjects"] = [item.to_dict() for item in self.linkedObjects]
        data["dashboardContextPreview"] = self.dashboardContextPreview.to_dict()
        if self.cabinets:
            data["emptyState"] = None
        return data


def get_module8_cabinet_admin_preview(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
) -> Module8CabinetAdminPreviewDTO:
    data = _dict_value(user)
    access_data = _access_context_dict(access_context)
    user_id = _string_or_none(data.get("id") or data.get("userId") or access_data.get("userId")) or ""
    workspace_id = _string_or_none(data.get("workspaceId") or access_data.get("workspaceId"))
    active_region_code = _string_or_none(data.get("activeRegionCode") or access_data.get("activeRegionCode"))
    workspaces = _workspace_items(data)
    cabinets = [
        _cabinet_from_workspace(workspace, index=index)
        for index, workspace in enumerate(workspaces)
    ]
    active = next((cabinet for cabinet in cabinets if cabinet.isActive), None)

    return Module8CabinetAdminPreviewDTO(
        userId=user_id,
        workspaceId=workspace_id or (active.workspaceId if active else None),
        activeRegionCode=active_region_code,
        cabinets=cabinets,
        activeCabinetId=active.cabinetId if active else None,
        activeCabinetType=active.cabinetType if active else None,
        linkedObjects=[],
        dashboardContextPreview=Module8DashboardContextPreview(
            mainFocus=_main_focus(active),
            recommendedBlocks=_recommended_blocks(access_data),
            recommendedWidgetCodes=_list_strings(access_data.get("allowedWidgetCodes"))[:6],
            recommendedQuickActionCodes=_list_strings(access_data.get("allowedQuickActionCodes"))[:6],
        ),
    )


def getModule8CabinetAdminPreview(
    user: Any,
    *,
    access_context: AccessContextForCabinet | dict[str, Any] | None = None,
) -> Module8CabinetAdminPreviewDTO:
    return get_module8_cabinet_admin_preview(user, access_context=access_context)


def _cabinet_from_workspace(workspace: dict[str, Any], *, index: int) -> Module8CabinetPreviewItem:
    workspace_id = _string_or_none(workspace.get("workspaceId") or workspace.get("id")) or f"workspace-preview-{index + 1}"
    workspace_type = _string_or_none(workspace.get("workspaceType") or workspace.get("type")) or "SPECIALIST"
    role_code = _string_or_none(workspace.get("roleCode") or workspace.get("businessRole")) or _role_from_workspace_type(workspace_type)
    cabinet_type = _cabinet_type_from_workspace(workspace_type, role_code)
    title = _string_or_none(workspace.get("workspaceTitle") or workspace.get("title")) or "Кабинет участника"
    return Module8CabinetPreviewItem(
        cabinetId=f"module8-preview:{workspace_id}:{role_code}",
        cabinetType=cabinet_type,
        title=title,
        businessRole=role_code,
        status=_string_or_none(workspace.get("status")) or "PREVIEW",
        isActive=index == 0,
        workspaceId=workspace_id,
    )


def _workspace_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    workspaces = data.get("workspaces") or data.get("workspaceContexts") or []
    if isinstance(workspaces, list):
        return [item for item in workspaces if isinstance(item, dict)]
    return []


def _cabinet_type_from_workspace(workspace_type: str, role_code: str | None) -> str:
    normalized = (role_code or workspace_type or "").upper()
    if normalized in {"CUSTOMER", "PROJECT"}:
        return "CUSTOMER"
    if normalized in {"SUPPLIER", "MATERIAL_SUPPLIER"}:
        return "MATERIAL_SUPPLIER"
    if normalized in {"CONTRACTOR", "CONSTRUCTION_COMPANY", "ORGANIZATION"}:
        return "CONSTRUCTION_COMPANY"
    return "SPECIALIST"


def _role_from_workspace_type(workspace_type: str) -> str:
    normalized = workspace_type.upper()
    if normalized in {"SUPPLIER", "CUSTOMER", "CONTRACTOR"}:
        return normalized
    return "SPECIALIST"


def _main_focus(active: Module8CabinetPreviewItem | None) -> str | None:
    if not active:
        return None
    return f"Preview кабинета: {active.title}"


def _recommended_blocks(access_data: dict[str, Any]) -> list[str]:
    modules = _list_strings(access_data.get("allowedModuleCodes"))
    if not modules:
        return []
    return modules[:6]


def _access_context_dict(access_context: AccessContextForCabinet | dict[str, Any] | None) -> dict[str, Any]:
    if access_context is None:
        return {}
    if isinstance(access_context, dict):
        return access_context
    return access_context.to_dict()


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _list_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
