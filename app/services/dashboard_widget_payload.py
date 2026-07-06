from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.services.dashboard_module_registry import get_canonical_module_code
from app.services.dashboard_system_contexts import (
    DASHBOARD_ADMIN_CONTEXT,
    DASHBOARD_ADMIN_SOURCE_MODULE,
    LEGACY_ADMIN_CABINET_MODULE,
)


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
    contextCode: str | None = None
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
    context_code: str | None = None,
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
    normalized_context_code = context_code or (
        DASHBOARD_ADMIN_CONTEXT
        if source_module_code in {DASHBOARD_ADMIN_SOURCE_MODULE, LEGACY_ADMIN_CABINET_MODULE}
        else None
    )
    return AtomWidgetPayload(
        widgetCode=widget_code,
        sourceModuleCode=canonical_code,
        featureCode=feature_code,
        contextCode=normalized_context_code,
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
    source_module_code = widget.get("module_code", DASHBOARD_ADMIN_SOURCE_MODULE)
    context_code = widget.get("context_code") or widget.get("contextCode")
    if not context_code and source_module_code in {DASHBOARD_ADMIN_SOURCE_MODULE, LEGACY_ADMIN_CABINET_MODULE}:
        context_code = DASHBOARD_ADMIN_CONTEXT
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
        source_module_code=source_module_code,
        feature_code=widget.get("feature_code"),
        context_code=context_code,
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
    source_code = widget.get("module_code", DASHBOARD_ADMIN_SOURCE_MODULE)
    source = get_canonical_module_code(source_code) or source_code
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
MODULE_03_DASHBOARD_WIDGET_CODES: tuple[str, ...] = (
    "MODULE_03_USERS_SUMMARY_WIDGET",
    "MODULE_03_MODERATION_QUEUE_WIDGET",
    "MODULE_03_AUDIT_LOG_WIDGET",
    "MODULE_03_MODULES_STATUS_WIDGET",
    "MODULE_03_WIDGETS_STATUS_WIDGET",
)


def build_module3_dashboard_widget_payloads(
    *,
    users: list[Any] | None = None,
    workspaces: list[Any] | None = None,
    history: list[Any] | None = None,
    updated_at: str | datetime | None = None,
) -> list[dict[str, Any]]:
    return [
        build_module3_dashboard_widget_payload(
            widget_code=widget_code,
            users=users,
            workspaces=workspaces,
            history=history,
            updated_at=updated_at,
        )
        for widget_code in MODULE_03_DASHBOARD_WIDGET_CODES
    ]


def build_module3_dashboard_widget_payload(
    *,
    widget_code: str,
    users: list[Any] | None = None,
    workspaces: list[Any] | None = None,
    history: list[Any] | None = None,
    updated_at: str | datetime | None = None,
) -> dict[str, Any]:
    users_list = list(users or [])
    workspaces_list = list(workspaces or [])
    history_list = list(history or [])
    if widget_code == "MODULE_03_USERS_SUMMARY_WIDGET":
        return _module3_users_summary_payload(users_list, workspaces_list, updated_at=updated_at)
    if widget_code == "MODULE_03_MODERATION_QUEUE_WIDGET":
        return _module3_moderation_queue_payload(users_list, workspaces_list, updated_at=updated_at)
    if widget_code == "MODULE_03_AUDIT_LOG_WIDGET":
        return _module3_audit_log_payload(history_list, users_list, workspaces_list, updated_at=updated_at)
    if widget_code == "MODULE_03_MODULES_STATUS_WIDGET":
        return _module3_modules_status_payload(updated_at=updated_at)
    if widget_code == "MODULE_03_WIDGETS_STATUS_WIDGET":
        return _module3_widgets_status_payload(updated_at=updated_at)
    return build_atom_widget_payload(
        widget_code=widget_code,
        source_module_code="MODULE_03_USERS_ROLES",
        title=widget_code,
        status="disabled",
        subtitle="Unknown Module 3 widget code.",
        updated_at=updated_at,
    ).to_dict()


def _module3_users_summary_payload(users: list[Any], workspaces: list[Any], *, updated_at: str | datetime | None) -> dict[str, Any]:
    from app.services.admin_user_role_management import user_directory_rows, user_directory_summary_chips

    rows = user_directory_rows(users, workspaces)
    chips = {item["typeCode"]: item["count"] for item in user_directory_summary_chips(rows)}
    active_count = len([row for row in rows if str(row.get("status") or "").lower() in {"active", "approved"}])
    blocked_count = len([row for row in rows if row.get("blocking") == "blocked"])
    invited_count = len([row for row in rows if str(row.get("status") or "").lower() in {"invited", "pending"}])
    return build_atom_widget_payload(
        widget_code="MODULE_03_USERS_SUMMARY_WIDGET",
        source_module_code="MODULE_03_USERS_ROLES",
        feature_code="MODULE_03_USERS_SUMMARY",
        title="\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438",
        status="ok" if rows else "info",
        primary_value=chips.get("ALL", 0),
        primary_label="\u0412\u0441\u0435\u0433\u043e \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439",
        items=[
            {"label": "\u041a\u043e\u043c\u043f\u0430\u043d\u0438\u0438", "value": chips.get("COMPANY", 0), "status": "info"},
            {"label": "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0438", "value": chips.get("SUPPLIER", 0), "status": "info"},
            {"label": "\u0417\u0430\u043a\u0430\u0437\u0447\u0438\u043a\u0438", "value": chips.get("CUSTOMER", 0), "status": "info"},
            {"label": "\u0421\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\u044b", "value": chips.get("SPECIALIST", 0), "status": "info"},
            {"label": "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435", "value": active_count, "status": "ok"},
            {"label": "\u0417\u0430\u0431\u043b\u043e\u043a\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0435", "value": blocked_count, "status": "error"},
            {"label": "\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u043d\u044b\u0435", "value": invited_count, "status": "attention"},
        ],
        updated_at=updated_at,
    ).to_dict()


def _module3_moderation_queue_payload(users: list[Any], workspaces: list[Any], *, updated_at: str | datetime | None) -> dict[str, Any]:
    from app.services.admin_user_role_management import verification_queue_summary

    queue = verification_queue_summary(users, workspaces)
    items = list(queue.get("allItems") or [])
    companies_count = len([item for item in items if str(item.get("companyType") or "").upper() not in {"SUPPLIER", "MATERIAL_SUPPLIER"}])
    suppliers_count = len([item for item in items if str(item.get("companyType") or "").upper() in {"SUPPLIER", "MATERIAL_SUPPLIER"}])
    deferred_count = len([item for item in items if str(item.get("priority") or "").lower() == "low"])
    total = int(queue.get("summary", {}).get("total") or 0)
    return build_atom_widget_payload(
        widget_code="MODULE_03_MODERATION_QUEUE_WIDGET",
        source_module_code="MODULE_03_USERS_ROLES",
        feature_code="MODULE_03_MODERATION_QUEUE",
        title="\u041e\u0447\u0435\u0440\u0435\u0434\u044c \u043d\u0430 \u043c\u043e\u0434\u0435\u0440\u0430\u0446\u0438\u044e",
        status="attention" if total else "ok",
        severity="medium" if total else None,
        primary_value=total,
        primary_label="\u041e\u0436\u0438\u0434\u0430\u044e\u0442 \u0440\u0435\u0448\u0435\u043d\u0438\u044f" if total else "\u041d\u0435\u0442 \u0437\u0430\u044f\u0432\u043e\u043a",
        items=[
            {"label": "\u041a\u043e\u043c\u043f\u0430\u043d\u0438\u0438", "value": companies_count, "status": "info"},
            {"label": "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a\u0438", "value": suppliers_count, "status": "info"},
            {"label": "\u041e\u0442\u043b\u043e\u0436\u0435\u043d\u043d\u044b\u0435", "value": deferred_count, "status": "attention"},
        ],
        updated_at=updated_at,
    ).to_dict()


def _module3_audit_log_payload(history: list[Any], users: list[Any], workspaces: list[Any], *, updated_at: str | datetime | None) -> dict[str, Any]:
    from app.services.admin_user_role_management import audit_panel_summary

    audit = audit_panel_summary(history, users=users, workspaces=workspaces)
    rows = list(audit.get("rows") or [])
    total = int(audit.get("summary", {}).get("total") or 0)
    latest_items = [
        {
            "label": str(row.get("action") or row.get("actionType") or ""),
            "value": str(row.get("objectName") or row.get("subjectLabel") or row.get("objectId") or ""),
            "status": "ok" if str(row.get("result") or "SUCCESS").upper() == "SUCCESS" else "error",
        }
        for row in rows[:2]
    ]
    return build_atom_widget_payload(
        widget_code="MODULE_03_AUDIT_LOG_WIDGET",
        source_module_code="MODULE_03_USERS_ROLES",
        feature_code="MODULE_03_AUDIT_LOG",
        title="\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0439",
        status="info" if total else "ok",
        primary_value=total,
        primary_label="\u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0439",
        items=latest_items,
        updated_at=updated_at,
    ).to_dict()


def _module3_modules_status_payload(*, updated_at: str | datetime | None) -> dict[str, Any]:
    from app.services.admin_user_role_management import module_registry_overview_summary

    summary = module_registry_overview_summary()
    return build_atom_widget_payload(
        widget_code="MODULE_03_MODULES_STATUS_WIDGET",
        source_module_code="MODULE_03_USERS_ROLES",
        feature_code="MODULE_03_MODULES_STATUS",
        title="\u041c\u043e\u0434\u0443\u043b\u0438 \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435",
        status="info",
        primary_value=summary.get("total", 0),
        primary_label="\u0412\u0441\u0435\u0433\u043e \u043c\u043e\u0434\u0443\u043b\u0435\u0439",
        items=_module3_registry_status_items(summary),
        mini_chart={"type": "donut", "points": [summary.get("active", 0), summary.get("inDevelopment", 0), summary.get("archived", 0)]},
        updated_at=updated_at,
    ).to_dict()


def _module3_widgets_status_payload(*, updated_at: str | datetime | None) -> dict[str, Any]:
    from app.services.admin_user_role_management import widget_registry_overview_summary

    summary = widget_registry_overview_summary()
    return build_atom_widget_payload(
        widget_code="MODULE_03_WIDGETS_STATUS_WIDGET",
        source_module_code="MODULE_03_USERS_ROLES",
        feature_code="MODULE_03_WIDGETS_STATUS",
        title="\u0412\u0438\u0434\u0436\u0435\u0442\u044b \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0435",
        status="info",
        primary_value=summary.get("total", 0),
        primary_label="\u0412\u0441\u0435\u0433\u043e \u0432\u0438\u0434\u0436\u0435\u0442\u043e\u0432",
        items=_module3_registry_status_items(summary),
        mini_chart={"type": "donut", "points": [summary.get("active", 0), summary.get("inDevelopment", 0), summary.get("archived", 0)]},
        updated_at=updated_at,
    ).to_dict()


def _module3_registry_status_items(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": "\u0410\u043a\u0442\u0438\u0432\u043d\u044b\u0435", "value": summary.get("active", 0), "status": "ok"},
        {"label": "\u0412 \u0440\u0430\u0437\u0440\u0430\u0431\u043e\u0442\u043a\u0435", "value": summary.get("inDevelopment", 0), "status": "info"},
        {"label": "\u0410\u0440\u0445\u0438\u0432\u043d\u044b\u0435", "value": summary.get("archived", 0), "status": "attention"},
    ]
