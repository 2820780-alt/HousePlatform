from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.dashboard_module_registry import (
    get_canonical_module_code,
    get_dashboard_module_registry_item_by_number,
)


WIDGET_TYPES = {
    "KPI",
    "CHART",
    "LIST",
    "STATUS",
    "TASK_QUEUE",
    "ALERTS",
    "ACTIONS",
    "ATOM_MAP",
}

BOTTOM_WIDGET_GRID = "BOTTOM_WIDGET_GRID"
TOP_WIDGET_GRID = "TOP_WIDGET_GRID"
RIGHT_RAIL = "RIGHT_RAIL"
ATOM_CARD_ACTIONS = "ATOM_CARD_ACTIONS"
WIDGET_ZONES = {TOP_WIDGET_GRID, BOTTOM_WIDGET_GRID, RIGHT_RAIL, ATOM_CARD_ACTIONS, "ATOM_MAP"}
WIDGET_SIZES = {"small", "medium", "large", "wide"}

LEGACY_SIZE_MAP = {
    "S": "small",
    "M": "medium",
    "L": "large",
    "W": "wide",
}

SIZE_GRID_SPANS = {
    "small": 3,
    "medium": 4,
    "large": 6,
    "wide": 12,
}


@dataclass
class DashboardWidgetConfig:
    widgetCode: str
    title: str
    type: str
    sourceModuleCode: str
    enabled: bool
    size: str
    position: int
    zoneCode: str = BOTTOM_WIDGET_GRID
    description: str | None = None
    canonicalModuleCode: str | None = None
    featureCode: str | None = None
    legacyModuleCode: str | None = None
    period: str | None = None
    dataSource: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dashboard_widget_config_from_model(widget: Any, position: int = 100) -> DashboardWidgetConfig:
    registry_item = get_dashboard_module_registry_item_by_number(getattr(widget, "module_number", None))
    module_code = registry_item.moduleCode if registry_item else "MODULE_16_ADMIN_CABINET"
    feature_code = registry_item.featureCodes[0] if registry_item and registry_item.featureCodes else None
    config_schema = getattr(widget, "config_schema", None) or {}
    return build_dashboard_widget_config(
        widget_code=getattr(widget, "widget_key", None),
        title=getattr(widget, "title", ""),
        description=getattr(widget, "description", None) or "",
        widget_type=getattr(widget, "widget_type", "STATUS"),
        source_module_code=module_code,
        feature_code=config_schema.get("featureCode") or feature_code,
        enabled=getattr(widget, "status", "ACTIVE") == "ACTIVE",
        size=getattr(widget, "default_size", "M"),
        position=position,
        zone_code=(config_schema.get("zoneCode") or BOTTOM_WIDGET_GRID),
        period=config_schema.get("period"),
        data_source=config_schema.get("dataSource"),
        settings=config_schema.get("settings") or {},
    )


def build_dashboard_widget_config(
    *,
    widget_code: str | None,
    title: str,
    description: str | None = None,
    widget_type: str,
    source_module_code: str | None,
    feature_code: str | None = None,
    enabled: bool = True,
    size: str = "medium",
    position: int = 100,
    zone_code: str = BOTTOM_WIDGET_GRID,
    period: str | None = None,
    data_source: str | None = None,
    settings: dict[str, Any] | None = None,
) -> DashboardWidgetConfig:
    normalized_type = _normalize_widget_type(widget_type)
    source_code = source_module_code or "MODULE_16_ADMIN_CABINET"
    canonical_code = get_canonical_module_code(source_code) or source_code
    legacy_module_code = source_code if source_code != canonical_code else None
    normalized_size = _normalize_size(size)
    stable_widget_code = widget_code or _make_widget_code(canonical_code, normalized_type, title)
    return DashboardWidgetConfig(
        widgetCode=stable_widget_code,
        title=title,
        description=description or "",
        type=normalized_type,
        sourceModuleCode=canonical_code,
        canonicalModuleCode=canonical_code,
        featureCode=feature_code,
        legacyModuleCode=legacy_module_code,
        enabled=enabled,
        size=normalized_size,
        position=position,
        zoneCode=_normalize_zone(zone_code),
        period=period,
        dataSource=data_source,
        settings=settings or {},
    )


def widget_config_from_dict(widget: dict[str, Any], position: int = 100) -> DashboardWidgetConfig:
    source_code = widget.get("sourceModuleCode") or widget.get("moduleCode")
    if not source_code and widget.get("module_number") is not None:
        registry_item = get_dashboard_module_registry_item_by_number(widget.get("module_number"))
        source_code = registry_item.moduleCode if registry_item else None
    if not source_code and widget.get("moduleNumberLegacy") is not None:
        registry_item = get_dashboard_module_registry_item_by_number(widget.get("moduleNumberLegacy"))
        source_code = registry_item.moduleCode if registry_item else None
    return build_dashboard_widget_config(
        widget_code=widget.get("widgetCode") or widget.get("widget_code"),
        title=widget.get("title", ""),
        description=widget.get("description", ""),
        widget_type=widget.get("type", "STATUS"),
        source_module_code=source_code,
        feature_code=widget.get("featureCode"),
        enabled=widget.get("enabled", True),
        size=widget.get("size", "medium"),
        position=int(widget.get("position", position)),
        zone_code=widget.get("zoneCode") or widget.get("zone") or BOTTOM_WIDGET_GRID,
        period=widget.get("period"),
        data_source=widget.get("dataSource"),
        settings=widget.get("settings") or {},
    )


def _normalize_widget_type(widget_type: str) -> str:
    normalized = (widget_type or "STATUS").upper()
    if normalized == "TASK":
        normalized = "TASK_QUEUE"
    return normalized if normalized in WIDGET_TYPES else "STATUS"


def _normalize_size(size: str) -> str:
    normalized = LEGACY_SIZE_MAP.get(size, size or "medium")
    return normalized if normalized in WIDGET_SIZES else "medium"


def _normalize_zone(zone_code: str | None) -> str:
    normalized = (zone_code or BOTTOM_WIDGET_GRID).upper()
    legacy_map = {
        "MAIN": BOTTOM_WIDGET_GRID,
        "TOP": TOP_WIDGET_GRID,
        "HEADER": TOP_WIDGET_GRID,
        "BELOW": BOTTOM_WIDGET_GRID,
        "BOTTOM": BOTTOM_WIDGET_GRID,
        "RIGHT": RIGHT_RAIL,
        "RIGHT_COLUMN": RIGHT_RAIL,
        "ATOM_CARD": ATOM_CARD_ACTIONS,
        "ATOM_ACTIONS": ATOM_CARD_ACTIONS,
    }
    normalized = legacy_map.get(normalized, normalized)
    return normalized if normalized in WIDGET_ZONES else BOTTOM_WIDGET_GRID


def _make_widget_code(module_code: str, widget_type: str, title: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in title).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{module_code}.{widget_type}.{slug or 'widget'}"
