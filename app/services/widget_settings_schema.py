from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.audit_log_service import AuditLogType


SCHEMA_STATUS_PLACEHOLDER = "OWNER_MODULE_PLACEHOLDER"
SETTINGS_STORAGE_LAYER = "UserDashboardLayout.widgets[].userSettings"
SETTINGS_SCHEMA_NOTE = (
    "Widget settings schema is provided by the widget owning module. Module 03 only previews "
    "the schema, checks access and records layout/settings changes when an admin changes another "
    "user's widget instance."
)


@dataclass(frozen=True)
class WidgetSettingsFieldPreview:
    settingCode: str
    title: str
    valueType: str
    sourceModuleCode: str
    isAllowed: bool
    isHidden: bool
    unavailableReason: str | None = None
    featureCode: str | None = None
    requiresModule8Context: bool = False
    requiresPermission: str | None = None
    isMock: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WidgetSettingsSchemaPreview:
    widgetCode: str
    sourceModuleCode: str
    canonicalModuleCode: str
    schemaSourceModuleCode: str
    settingsInstanceKey: str
    schemaStatus: str
    storageLayer: str
    auditEventType: str
    canOpenSettings: bool
    warning: str
    fields: list[WidgetSettingsFieldPreview] = field(default_factory=list)
    featureCode: str | None = None
    module8ContextPolicy: str = (
        "Module 08 may narrow available settings by activeCabinetId, cabinetType, activeObjectId "
        "and visibility/offer policies."
    )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fields"] = [field.to_dict() for field in self.fields]
        data["allowedParameters"] = [field.settingCode for field in self.fields if field.isAllowed]
        data["hiddenParameters"] = [field.settingCode for field in self.fields if field.isHidden]
        return data


def build_widget_settings_schema_preview(
    widget: Any,
    *,
    access_context: dict[str, Any] | None = None,
    module8_preview: dict[str, Any] | None = None,
    is_widget_allowed: bool = False,
) -> dict[str, Any]:
    widget_data = _dict_value(widget)
    access_data = access_context or {}
    module8_data = module8_preview or {}
    widget_code = str(widget_data.get("widgetCode") or widget_data.get("widget_code") or "")
    source_module_code = str(widget_data.get("sourceModuleCode") or widget_data.get("source_module_code") or "UNKNOWN")
    feature_code = _string_or_none(widget_data.get("featureCode") or widget_data.get("feature_code"))
    canonical_module_code = str(widget_data.get("canonicalModuleCode") or widget_data.get("canonical_module_code") or source_module_code)
    active_cabinet_id = module8_data.get("activeCabinetId") or access_data.get("activeCabinetId")
    fields = [
        _field_preview(
            field,
            source_module_code=source_module_code,
            feature_code=feature_code,
            is_widget_allowed=is_widget_allowed,
            has_active_cabinet=bool(active_cabinet_id),
        )
        for field in _owner_module_fields(source_module_code, feature_code)
    ]
    return WidgetSettingsSchemaPreview(
        widgetCode=widget_code,
        sourceModuleCode=source_module_code,
        canonicalModuleCode=canonical_module_code,
        featureCode=feature_code,
        schemaSourceModuleCode=source_module_code,
        settingsInstanceKey=_settings_instance_key(access_data, widget_code),
        schemaStatus=SCHEMA_STATUS_PLACEHOLDER,
        storageLayer=SETTINGS_STORAGE_LAYER,
        auditEventType=AuditLogType.USER_DASHBOARD_LAYOUT_CHANGED.value,
        canOpenSettings=is_widget_allowed,
        warning=SETTINGS_SCHEMA_NOTE,
        fields=fields,
    ).to_dict()


def _field_preview(
    field: dict[str, Any],
    *,
    source_module_code: str,
    feature_code: str | None,
    is_widget_allowed: bool,
    has_active_cabinet: bool,
) -> WidgetSettingsFieldPreview:
    requires_module8_context = bool(field.get("requiresModule8Context"))
    is_hidden = False
    reason: str | None = None
    if not is_widget_allowed:
        is_hidden = True
        reason = "Widget Permission does not allow this widget instance."
    elif requires_module8_context and not has_active_cabinet:
        is_hidden = True
        reason = "ActiveCabinetContext is required and will come from Module 08."
    return WidgetSettingsFieldPreview(
        settingCode=field["settingCode"],
        title=field["title"],
        valueType=field["valueType"],
        sourceModuleCode=source_module_code,
        featureCode=feature_code,
        requiresModule8Context=requires_module8_context,
        requiresPermission=field.get("requiresPermission"),
        isAllowed=not is_hidden,
        isHidden=is_hidden,
        unavailableReason=reason,
    )


def _owner_module_fields(source_module_code: str, feature_code: str | None) -> list[dict[str, Any]]:
    if source_module_code == "MODULE_01_MATERIAL_HUB":
        return [
            _field("source", "Источник", "select"),
            _field("analysis_scenario", "Сценарий анализа", "select"),
            _field("region", "Регион", "region"),
            _field("write_mode", "Режим записи", "select", requires_permission="EDIT"),
        ]
    if source_module_code == "MODULE_07_DIGITAL_HOUSE":
        return [
            _field("object", "Объект", "object_ref", requires_module8=True),
            _field("zone", "Зона", "select"),
            _field("storage", "Склад", "select"),
            _field("stage", "Этап", "select"),
        ]
    if source_module_code == "MODULE_09_PROCUREMENT":
        return [
            _field("procurement", "Закупка", "procurement_ref"),
            _field("request_status", "Статус заявки", "select"),
            _field("supplier", "Поставщик", "supplier_ref"),
        ]
    if source_module_code == "MODULE_11_ANALYTICS":
        fields = [
            _field("period", "Период", "period"),
            _field("object", "Объект", "object_ref", requires_module8=True),
            _field("region", "Регион", "region"),
            _field("chart_type", "Тип графика", "select"),
        ]
        if feature_code == "PRICE_DYNAMICS":
            fields.insert(2, _field("material", "Материал", "material_ref"))
        return fields
    if source_module_code == "MODULE_08_PARTNER_PORTAL":
        return [
            _field("cabinet", "Кабинет", "cabinet_ref", requires_module8=True),
            _field("linked_objects", "Связанные объекты", "object_list", requires_module8=True),
            _field("visibility_policy", "Настройки видимости", "policy_ref", requires_module8=True),
            _field("offer_policy", "Настройки предложений", "policy_ref", requires_module8=True),
        ]
    return [
        _field("region", "Регион", "region"),
        _field("display_mode", "Режим отображения", "select"),
        _field("row_limit", "Лимит строк", "number"),
    ]


def _field(
    setting_code: str,
    title: str,
    value_type: str,
    *,
    requires_module8: bool = False,
    requires_permission: str | None = None,
) -> dict[str, Any]:
    return {
        "settingCode": setting_code,
        "title": title,
        "valueType": value_type,
        "requiresModule8Context": requires_module8,
        "requiresPermission": requires_permission,
    }


def _settings_instance_key(access_data: dict[str, Any], widget_code: str) -> str:
    user_id = access_data.get("userId") or "preview-user"
    workspace_id = access_data.get("workspaceId") or "workspace"
    return f"{user_id}:{workspace_id}:{widget_code}:default"


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
