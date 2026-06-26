from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.services.dashboard_module_registry import get_canonical_module_code


PAYLOAD_STATUSES = {"ok", "info", "attention", "error", "disabled"}
PAYLOAD_SEVERITIES = {"low", "medium", "high", "critical"}
TREND_DIRECTIONS = {"up", "down", "flat"}
MINI_CHART_TYPES = {"line", "bar", "donut", "sparkline"}
ITEM_STATUSES = {"ok", "info", "attention", "error"}
ATTENTION_SEVERITIES = {"info", "attention", "error"}


@dataclass
class WidgetTrendPayload:
    direction: str
    value: str
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WidgetProgressPayload:
    current: int | float
    total: int | float
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WidgetMiniChartPayload:
    type: str
    points: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WidgetItemPayload:
    label: str
    value: str | int | float | None = None
    status: str | None = None
    route: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WidgetAttentionItemPayload:
    title: str
    severity: str
    targetRoute: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WidgetCtaPayload:
    label: str
    route: str
    actionCode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AtomWidgetPayload:
    widgetCode: str
    sourceModuleCode: str
    title: str
    status: str
    updatedAt: str
    featureCode: str | None = None
    subtitle: str | None = None
    severity: str | None = None
    primaryValue: str | int | float | None = None
    primaryLabel: str | None = None
    secondaryValue: str | int | float | None = None
    secondaryLabel: str | None = None
    trend: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None
    miniChart: dict[str, Any] | None = None
    items: list[dict[str, Any]] = field(default_factory=list)
    attentionItems: list[dict[str, Any]] = field(default_factory=list)
    cta: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_atom_widget_payload(
    *,
    widget_code: str,
    source_module_code: str,
    title: str,
    status: str = "info",
    updated_at: str | datetime | None = None,
    feature_code: str | None = None,
    subtitle: str | None = None,
    severity: str | None = None,
    primary_value: str | int | float | None = None,
    primary_label: str | None = None,
    secondary_value: str | int | float | None = None,
    secondary_label: str | None = None,
    trend: dict[str, Any] | None = None,
    progress: dict[str, Any] | None = None,
    mini_chart: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    attention_items: list[dict[str, Any]] | None = None,
    cta: dict[str, Any] | None = None,
) -> AtomWidgetPayload:
    canonical_code = get_canonical_module_code(source_module_code) or source_module_code
    return AtomWidgetPayload(
        widgetCode=widget_code,
        sourceModuleCode=canonical_code,
        featureCode=feature_code,
        title=title,
        subtitle=subtitle,
        status=_normalize_status(status),
        severity=_normalize_optional(severity, PAYLOAD_SEVERITIES),
        primaryValue=primary_value,
        primaryLabel=primary_label,
        secondaryValue=secondary_value,
        secondaryLabel=secondary_label,
        trend=_normalize_trend(trend),
        progress=_normalize_progress(progress),
        miniChart=_normalize_mini_chart(mini_chart),
        items=_normalize_items(items or []),
        attentionItems=_normalize_attention_items(attention_items or []),
        cta=_normalize_cta(cta),
        updatedAt=_format_updated_at(updated_at),
    )


def atom_widget_payload_from_admin_widget(widget: dict[str, Any], *, updated_at: str | datetime | None = None) -> dict[str, Any]:
    items = [
        {
            "label": item.get("label", ""),
            "value": item.get("value"),
            "status": _item_status_from_tone(item.get("tone")),
        }
        for item in widget.get("items", [])
    ]
    attention_items = [
        {
            "title": item.get("label", ""),
            "severity": _attention_severity_from_tone(item.get("tone")),
        }
        for item in widget.get("items", [])
        if item.get("tone") in {"warn", "danger"} or item.get("mock")
    ]
    return build_atom_widget_payload(
        widget_code=_widget_code_from_admin_widget(widget),
        source_module_code=widget.get("module_code", "MODULE_16_ADMIN_CABINET"),
        feature_code=widget.get("feature_code"),
        title=widget.get("title", "Виджет"),
        subtitle=widget.get("type"),
        status=_payload_status_from_widget(widget),
        severity="medium" if attention_items else None,
        primary_value=items[0]["value"] if items else None,
        primary_label=items[0]["label"] if items else None,
        items=items,
        attention_items=attention_items,
        updated_at=updated_at,
    ).to_dict()


def _normalize_status(status: str) -> str:
    return status if status in PAYLOAD_STATUSES else "info"


def _normalize_optional(value: str | None, allowed: set[str]) -> str | None:
    return value if value in allowed else None


def _normalize_trend(trend: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trend:
        return None
    direction = trend.get("direction")
    return WidgetTrendPayload(
        direction=direction if direction in TREND_DIRECTIONS else "flat",
        value=str(trend.get("value", "")),
        label=trend.get("label"),
    ).to_dict()


def _normalize_progress(progress: dict[str, Any] | None) -> dict[str, Any] | None:
    if not progress:
        return None
    return WidgetProgressPayload(
        current=progress.get("current", 0),
        total=progress.get("total", 0),
        label=progress.get("label"),
    ).to_dict()


def _normalize_mini_chart(mini_chart: dict[str, Any] | None) -> dict[str, Any] | None:
    if not mini_chart:
        return None
    chart_type = mini_chart.get("type")
    return WidgetMiniChartPayload(
        type=chart_type if chart_type in MINI_CHART_TYPES else "sparkline",
        points=list(mini_chart.get("points") or []),
    ).to_dict()


def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        WidgetItemPayload(
            label=str(item.get("label", "")),
            value=item.get("value"),
            status=_normalize_optional(item.get("status"), ITEM_STATUSES),
            route=item.get("route"),
        ).to_dict()
        for item in items
    ]


def _normalize_attention_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        WidgetAttentionItemPayload(
            title=str(item.get("title", "")),
            severity=item.get("severity") if item.get("severity") in ATTENTION_SEVERITIES else "info",
            targetRoute=item.get("targetRoute"),
        ).to_dict()
        for item in items
    ]


def _normalize_cta(cta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cta:
        return None
    route = cta.get("route")
    if not route:
        return None
    return WidgetCtaPayload(
        label=str(cta.get("label", "Открыть")),
        route=route,
        actionCode=cta.get("actionCode"),
    ).to_dict()


def _format_updated_at(value: str | datetime | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str) and value:
        return value
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")


def _widget_code_from_admin_widget(widget: dict[str, Any]) -> str:
    source = get_canonical_module_code(widget.get("module_code")) or widget.get("module_code", "MODULE_16_ADMIN_CABINET")
    feature = widget.get("feature_code") or widget.get("type", "STATUS")
    slug = "".join(char.lower() if char.isalnum() else "-" for char in widget.get("title", "widget")).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{source}.{feature}.{slug or 'widget'}"


def _payload_status_from_widget(widget: dict[str, Any]) -> str:
    if widget.get("mock"):
        return "info"
    tones = {item.get("tone") for item in widget.get("items", [])}
    if "danger" in tones:
        return "error"
    if "warn" in tones:
        return "attention"
    return "info"


def _item_status_from_tone(tone: str | None) -> str | None:
    return {
        "success": "ok",
        "info": "info",
        "warn": "attention",
        "danger": "error",
    }.get(tone)


def _attention_severity_from_tone(tone: str | None) -> str:
    return "error" if tone == "danger" else "attention"
