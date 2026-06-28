from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_levels import AccessLevel
from app.core.access_scopes import AccessScope
from app.core.permission_guard import can, canonical_module_code
from app.models.active_region import ActiveRegion
from app.models.dashboard_profile import DashboardProfile
from app.models.enums import RegionStatus
from app.models.module_action_registry import ModuleActionRegistry
from app.models.platform_module_registry import PlatformModuleRegistry
from app.models.platform_region import PlatformRegion
from app.services.platform_region_registry import get_default_active_region, get_platform_region_registry_item


HIDDEN_ACTIVE_STATUSES: set[str] = {"MERGED", "ARCHIVED"}
VISIBLE_MODULE_STATUSES: set[str] = {"ACTIVE", "DEPRECATED"}
ACCESS_LEVELS_DESC: tuple[str, ...] = (
    AccessLevel.ADMIN,
    AccessLevel.APPROVE,
    AccessLevel.EDIT,
    AccessLevel.CREATE,
    AccessLevel.VIEW,
)
SCOPES_BY_VISIBILITY_PRIORITY: tuple[str, ...] = (
    AccessScope.GLOBAL,
    AccessScope.OWN,
    AccessScope.RELEVANT,
    AccessScope.LIMITED,
)
DEFAULT_ACTIONS_BY_ACCESS_LEVEL: dict[str, tuple[str, ...]] = {
    AccessLevel.VIEW: ("VIEW",),
    AccessLevel.CREATE: ("VIEW", "CREATE"),
    AccessLevel.EDIT: ("VIEW", "CREATE", "EDIT"),
    AccessLevel.APPROVE: ("VIEW", "CREATE", "EDIT", "APPROVE"),
    AccessLevel.ADMIN: ("VIEW", "CREATE", "EDIT", "APPROVE", "ADMIN"),
}


@dataclass(frozen=True)
class ActiveRegionContext:
    activeRegionCode: str | None = None
    activeRegionName: str | None = None
    isActive: bool = False
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "activeRegionCode": self.activeRegionCode,
            "activeRegionName": self.activeRegionName,
            "isActive": self.isActive,
            "source": self.source,
        }


@dataclass
class ModuleVisibilityItem:
    moduleCode: str
    canonicalModuleCode: str
    title: str
    route: str | None
    icon: str | None
    accessLevel: str
    scope: str
    availableActions: list[str]
    visible: bool
    status: str
    featureCodes: list[str] = field(default_factory=list)
    legacyModuleCodes: list[str] = field(default_factory=list)
    activeRegionCode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "moduleCode": self.moduleCode,
            "canonicalModuleCode": self.canonicalModuleCode,
            "title": self.title,
            "route": self.route,
            "icon": self.icon,
            "accessLevel": self.accessLevel,
            "scope": self.scope,
            "availableActions": self.availableActions,
            "visible": self.visible,
            "status": self.status,
            "featureCodes": self.featureCodes,
            "legacyModuleCodes": self.legacyModuleCodes,
            "activeRegionCode": self.activeRegionCode,
        }


async def get_visible_modules_for_user(db: AsyncSession, user: Any) -> list[dict[str, Any]]:
    active_region = await resolve_active_region_context(db, user)
    registry_result = await db.execute(
        select(PlatformModuleRegistry).order_by(
            PlatformModuleRegistry.display_order,
            PlatformModuleRegistry.module_code,
        )
    )
    action_result = await db.execute(
        select(ModuleActionRegistry).where(ModuleActionRegistry.is_active.is_(True))
    )
    return [
        item.to_dict()
        for item in build_visible_module_items(
            registry_result.scalars().all(),
            user,
            active_region,
            action_result.scalars().all(),
        )
    ]


async def resolve_active_region_context(db: AsyncSession, user: Any | None = None) -> ActiveRegionContext:
    profile_region_code = await _load_profile_active_region_code(db, user)
    if profile_region_code:
        profile_region = await _load_active_platform_region(db, profile_region_code)
        if profile_region:
            return ActiveRegionContext(
                activeRegionCode=profile_region.code,
                activeRegionName=profile_region.name,
                isActive=True,
                source="UserDashboardProfile",
            )

    active_region_result = await db.execute(
        select(PlatformRegion)
        .join(ActiveRegion, ActiveRegion.region_id == PlatformRegion.id)
        .where(
            ActiveRegion.status == RegionStatus.ACTIVE,
            PlatformRegion.status == RegionStatus.ACTIVE,
            PlatformRegion.is_active.is_(True),
        )
        .order_by(PlatformRegion.display_order, PlatformRegion.code)
    )
    active_region = active_region_result.scalars().first()
    if active_region:
        return ActiveRegionContext(
            activeRegionCode=active_region.code,
            activeRegionName=active_region.name,
            isActive=True,
            source="PlatformRegionRegistry",
        )

    registry_default = get_default_active_region()
    registry_item = get_platform_region_registry_item(registry_default.get("activeRegionCode"))
    return ActiveRegionContext(
        activeRegionCode=registry_default.get("activeRegionCode"),
        activeRegionName=registry_default.get("activeRegionName"),
        isActive=bool(registry_item and registry_item.isActive and registry_item.status == "ACTIVE"),
        source="PlatformRegionRegistryMock",
    )


def build_visible_module_items(
    registry_items: Sequence[Any],
    user: Any,
    active_region: ActiveRegionContext | dict[str, Any],
    action_items: Sequence[Any] = (),
) -> list[ModuleVisibilityItem]:
    region = _region_context(active_region)
    if not region.isActive or not region.activeRegionCode:
        return []

    action_codes_by_module = _action_codes_by_canonical_module(action_items)
    legacy_codes_by_canonical = _legacy_codes_by_canonical_module(registry_items)
    result_by_canonical: dict[str, ModuleVisibilityItem] = {}

    for registry_item in registry_items:
        status = _status(registry_item)
        canonical_code = _canonical_registry_code(registry_item)
        if status in HIDDEN_ACTIVE_STATUSES:
            continue
        if status not in VISIBLE_MODULE_STATUSES:
            continue
        if not _bool_value(registry_item, "is_active"):
            continue

        access_grant = _best_access_grant(user, canonical_code)
        if not access_grant:
            access_grant = _best_access_grant(user, _get_value(registry_item, "module_code"))
        if not access_grant:
            continue

        available_actions = _available_actions_for_module(
            user=user,
            module_code=canonical_code,
            access_level=access_grant["accessLevel"],
            scope=access_grant["scope"],
            registry_actions=_list_value(_get_value(registry_item, "available_actions"))
            or action_codes_by_module.get(canonical_code, []),
        )
        if not available_actions:
            continue

        existing = result_by_canonical.get(canonical_code)
        candidate = ModuleVisibilityItem(
            moduleCode=canonical_code,
            canonicalModuleCode=canonical_code,
            title=_get_value(registry_item, "title"),
            route=_get_value(registry_item, "route") or _get_value(registry_item, "redirect_route"),
            icon=_get_value(registry_item, "icon"),
            accessLevel=access_grant["accessLevel"],
            scope=access_grant["scope"],
            availableActions=available_actions,
            visible=True,
            status=status,
            featureCodes=_unique_strings(_list_value(_get_value(registry_item, "feature_codes"))),
            legacyModuleCodes=legacy_codes_by_canonical.get(canonical_code, []),
            activeRegionCode=region.activeRegionCode,
        )
        if not existing or _display_order(registry_item) < _display_order(existing):
            result_by_canonical[canonical_code] = candidate

    return sorted(result_by_canonical.values(), key=lambda item: (item.title or "", item.moduleCode))


def normalize_legacy_module_mapping(
    module_code: str,
    registry_items: Sequence[Any],
) -> dict[str, Any]:
    canonical_code = canonical_module_code(module_code)
    feature_codes: list[str] = []
    redirect_route: str | None = None
    for item in registry_items:
        if _get_value(item, "module_code") == module_code:
            canonical_code = _canonical_registry_code(item)
            feature_codes = _unique_strings(_list_value(_get_value(item, "feature_codes")))
            redirect_route = _get_value(item, "redirect_route")
            break
    return {
        "moduleCode": module_code,
        "canonicalModuleCode": canonical_code,
        "featureCodes": feature_codes,
        "redirectRoute": redirect_route,
    }


async def _load_profile_active_region_code(db: AsyncSession, user: Any | None) -> str | None:
    user_id = _get_value(user, "id")
    if not user_id:
        return None
    result = await db.execute(
        select(DashboardProfile)
        .where(DashboardProfile.user_id == user_id, DashboardProfile.status == "ACTIVE")
        .order_by(DashboardProfile.is_default.desc(), DashboardProfile.updated_at.desc())
    )
    for profile in result.scalars().all():
        code = _find_region_code_in_mapping(profile.layout or {})
        if code:
            return code
    return None


async def _load_active_platform_region(db: AsyncSession, region_code: str) -> PlatformRegion | None:
    result = await db.execute(
        select(PlatformRegion).where(
            PlatformRegion.code == region_code,
            PlatformRegion.status == RegionStatus.ACTIVE,
            PlatformRegion.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


def _find_region_code_in_mapping(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("activeRegionCode", "region_id", "price_region_id", "object_region_id"):
        value = data.get(key)
        if value:
            return str(value)
    for value in data.values():
        nested = _find_region_code_in_mapping(value)
        if nested:
            return nested
    return None


def _best_access_grant(user: Any, module_code: str | None) -> dict[str, str] | None:
    if not module_code:
        return None
    for access_level in ACCESS_LEVELS_DESC:
        for scope in SCOPES_BY_VISIBILITY_PRIORITY:
            if can(user, module_code, access_level, scope):
                return {"accessLevel": str(access_level), "scope": str(scope)}
    return None


def _available_actions_for_module(
    *,
    user: Any,
    module_code: str,
    access_level: str,
    scope: str,
    registry_actions: Sequence[str],
) -> list[str]:
    actions = list(registry_actions) if registry_actions else list(DEFAULT_ACTIONS_BY_ACCESS_LEVEL.get(access_level, ("VIEW",)))
    visible_actions = [
        action_code
        for action_code in _unique_strings(actions)
        if can(user, module_code, action_code, scope)
    ]
    if "VIEW" not in visible_actions and can(user, module_code, "VIEW", scope):
        visible_actions.insert(0, "VIEW")
    return visible_actions


def _legacy_codes_by_canonical_module(registry_items: Sequence[Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for item in registry_items:
        module_code = _get_value(item, "module_code")
        canonical_code = _canonical_registry_code(item)
        legacy_codes = [
            module_code,
            *_list_value(_get_value(item, "legacy_codes")),
        ]
        if module_code == canonical_code and _status(item) == "ACTIVE":
            legacy_codes = _list_value(_get_value(item, "legacy_codes"))
        for legacy_code in legacy_codes:
            if legacy_code and legacy_code != canonical_code:
                mapping.setdefault(canonical_code, [])
                if legacy_code not in mapping[canonical_code]:
                    mapping[canonical_code].append(legacy_code)
    return mapping


def _action_codes_by_canonical_module(action_items: Sequence[Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for item in action_items:
        module_code = canonical_module_code(_get_value(item, "module_code") or "")
        action_code = _get_value(item, "action_code")
        if module_code and action_code:
            mapping.setdefault(module_code, [])
            if action_code not in mapping[module_code]:
                mapping[module_code].append(action_code)
    return mapping


def _canonical_registry_code(item: Any) -> str:
    return canonical_module_code(_get_value(item, "canonical_module_code") or _get_value(item, "module_code"))


def _region_context(active_region: ActiveRegionContext | dict[str, Any]) -> ActiveRegionContext:
    if isinstance(active_region, ActiveRegionContext):
        return active_region
    return ActiveRegionContext(
        activeRegionCode=active_region.get("activeRegionCode"),
        activeRegionName=active_region.get("activeRegionName"),
        isActive=bool(active_region.get("isActive")),
        source=active_region.get("source", "unknown"),
    )


def _display_order(item: Any) -> int:
    value = _get_value(item, "display_order")
    return int(value if value is not None else 1000)


def _status(item: Any) -> str:
    return _enum_value(_get_value(item, "status")).upper()


def _bool_value(item: Any, field_name: str) -> bool:
    return bool(_get_value(item, field_name))


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _list_value(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return []


def _unique_strings(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        string_value = str(value)
        if string_value and string_value not in seen:
            result.append(string_value)
            seen.add(string_value)
    return result


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
