from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.dashboard_module_registry import get_canonical_module_code, get_dashboard_module_registry_item
from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT, DASHBOARD_ADMIN_SOURCE_MODULE

MODULE_REGISTRY_VERSION = "module03-sprint25-v1"

VERSIONED_REGISTRY_KEYS = (
    "module_registry",
    "role_matrix",
    "permissions",
    "widgets",
    "dashboard_profiles",
    "dashboard_layouts",
    "quick_actions",
    "module_lifecycle",
    "canonical_map",
    "legacy_aliases",
)


@dataclass(frozen=True)
class ModuleMigrationRule:
    legacyModuleCode: str
    canonicalModuleCode: str
    featureCode: str | None = None
    targetContextCode: str | None = None
    redirectRoute: str | None = None
    migrationStatus: str = "MAPPED"
    reviewNote: str = ""


@dataclass(frozen=True)
class VersionedModuleReference:
    originalModuleCode: str | None
    canonicalModuleCode: str | None
    targetCode: str | None
    featureCode: str | None = None
    legacyModuleCode: str | None = None
    contextCode: str | None = None
    redirectRoute: str | None = None
    registryVersion: str = MODULE_REGISTRY_VERSION
    isKnownLegacy: bool = False
    needsReview: bool = False
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "originalModuleCode": self.originalModuleCode,
            "canonicalModuleCode": self.canonicalModuleCode,
            "targetCode": self.targetCode,
            "featureCode": self.featureCode,
            "legacyModuleCode": self.legacyModuleCode,
            "contextCode": self.contextCode,
            "redirectRoute": self.redirectRoute,
            "registryVersion": self.registryVersion,
            "isKnownLegacy": self.isKnownLegacy,
            "needsReview": self.needsReview,
            "warning": self.warning,
        }


CANONICAL_MIGRATION_RULES: tuple[ModuleMigrationRule, ...] = (
    ModuleMigrationRule(
        legacyModuleCode="MODULE_07_DIGITAL_OBJECT",
        canonicalModuleCode="MODULE_07_DIGITAL_HOUSE",
        redirectRoute="/modules/digital-house",
        migrationStatus="MERGED",
        reviewNote="Digital Object is a legacy alias of Digital House.",
    ),
    ModuleMigrationRule(
        legacyModuleCode="MODULE_14_PRICE_HISTORY",
        canonicalModuleCode="MODULE_11_ANALYTICS",
        featureCode="PRICE_DYNAMICS",
        redirectRoute="/modules/analytics?section=price-dynamics",
        migrationStatus="MERGED",
        reviewNote="Price History is a feature inside Analytics.",
    ),
    ModuleMigrationRule(
        legacyModuleCode="MODULE_14_CONSTRUCTOR_LITE",
        canonicalModuleCode="MODULE_19_CONSTRUCTOR_LITE",
        redirectRoute="/modules/constructor-lite",
        migrationStatus="DEPRECATED",
        reviewNote="Constructor Lite moved to the canonical Module 19 code.",
    ),
    ModuleMigrationRule(
        legacyModuleCode="MODULE_15_CONSTRUCTION_GROUPS",
        canonicalModuleCode="MODULE_01_MATERIAL_HUB",
        featureCode="CONSTRUCTION_APPLICABILITY",
        redirectRoute="/api/v1/admin/material-hub/view?feature=construction-applicability",
        migrationStatus="DEPRECATED",
        reviewNote="Construction groups are a Material Hub applicability feature.",
    ),
    ModuleMigrationRule(
        legacyModuleCode="MODULE_16_ADMIN_CABINET",
        canonicalModuleCode=DASHBOARD_ADMIN_SOURCE_MODULE,
        targetContextCode=DASHBOARD_ADMIN_CONTEXT,
        redirectRoute="/api/v1/admin/cabinet/view",
        migrationStatus="DEPRECATED_CONTEXT",
        reviewNote="Admin Cabinet is a Dashboard context, not an active business module.",
    ),
)

_RULES_BY_LEGACY = {rule.legacyModuleCode: rule for rule in CANONICAL_MIGRATION_RULES}


def get_module_migration_rules() -> list[dict[str, Any]]:
    return [rule.__dict__.copy() for rule in CANONICAL_MIGRATION_RULES]


def get_versioned_registry_snapshots() -> list[dict[str, Any]]:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return [
        {
            "registryKey": key,
            "registryVersion": MODULE_REGISTRY_VERSION,
            "sourceModuleCode": DASHBOARD_ADMIN_SOURCE_MODULE,
            "createdAt": now,
            "description": _registry_description(key),
        }
        for key in VERSIONED_REGISTRY_KEYS
    ]


def normalize_module_reference(module_code: Any, feature_code: str | None = None) -> VersionedModuleReference:
    if module_code is None:
        return VersionedModuleReference(None, None, None, featureCode=feature_code)

    original = str(module_code)
    rule = _RULES_BY_LEGACY.get(original)
    if rule:
        target_code = rule.targetContextCode or rule.canonicalModuleCode
        return VersionedModuleReference(
            originalModuleCode=original,
            canonicalModuleCode=rule.canonicalModuleCode,
            targetCode=target_code,
            featureCode=feature_code or rule.featureCode,
            legacyModuleCode=original,
            contextCode=rule.targetContextCode,
            redirectRoute=rule.redirectRoute,
            isKnownLegacy=True,
        )

    canonical = get_canonical_module_code(original)
    registry_item = get_dashboard_module_registry_item(original) or get_dashboard_module_registry_item(canonical)
    if registry_item:
        canonical = canonical or registry_item.canonicalModuleCode or registry_item.moduleCode
        return VersionedModuleReference(
            originalModuleCode=original,
            canonicalModuleCode=canonical,
            targetCode=canonical,
            featureCode=feature_code,
            legacyModuleCode=original if original != canonical else None,
            redirectRoute=registry_item.redirectRoute if original != canonical else None,
            isKnownLegacy=original != canonical,
        )

    warning = f"Unknown module reference '{original}' was preserved for review."
    return VersionedModuleReference(
        originalModuleCode=original,
        canonicalModuleCode=original,
        targetCode=original,
        featureCode=feature_code,
        needsReview=True,
        warning=warning,
    )


def normalize_module_code_for_storage(module_code: Any, feature_code: str | None = None) -> str | None:
    return normalize_module_reference(module_code, feature_code).targetCode


def normalize_module_code_list(module_codes: list[Any] | tuple[Any, ...]) -> list[str]:
    normalized: list[str] = []
    for module_code in module_codes:
        target = normalize_module_code_for_storage(module_code)
        if target and target not in normalized:
            normalized.append(target)
    return normalized


def normalize_versioned_layout(layout: Any) -> Any:
    normalized = deepcopy(layout)
    if not isinstance(normalized, dict):
        return normalized

    for key in ("favoriteModules", "favoriteModuleCodes", "allowedModules", "allowedModuleCodes"):
        if isinstance(normalized.get(key), list):
            normalized[key] = normalize_module_code_list(normalized[key])

    widgets = normalized.get("widgets")
    if isinstance(widgets, list):
        normalized["widgets"] = [
            normalize_versioned_widget_reference(widget)
            for widget in widgets
            if isinstance(widget, dict)
        ]

    quick_actions = normalized.get("quickActions")
    if isinstance(quick_actions, list):
        normalized["quickActions"] = [
            normalize_versioned_quick_action_reference(action)
            for action in quick_actions
            if isinstance(action, dict)
        ]

    return normalized


def normalize_versioned_widget_reference(widget: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(widget)
    source = normalized.get("sourceModuleCode") or normalized.get("source_module_code")
    feature = normalized.get("featureCode") or normalized.get("feature_code")
    reference = normalize_module_reference(source, feature)
    if reference.originalModuleCode:
        normalized["sourceModuleCode"] = reference.canonicalModuleCode
        normalized["canonicalModuleCode"] = reference.canonicalModuleCode
    if reference.featureCode:
        normalized["featureCode"] = reference.featureCode
    if reference.legacyModuleCode:
        normalized["legacyModuleCode"] = reference.legacyModuleCode
    if reference.contextCode:
        normalized["contextCode"] = reference.contextCode
    if reference.needsReview:
        normalized["migrationWarning"] = reference.warning
    normalized.pop("sourceModuleNumber", None)
    normalized.pop("moduleNumber", None)
    return normalized


def normalize_versioned_quick_action_reference(action: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(action)
    source = normalized.get("sourceModuleCode") or normalized.get("moduleCode")
    feature = normalized.get("featureCode")
    reference = normalize_module_reference(source, feature)
    if reference.originalModuleCode:
        normalized["sourceModuleCode"] = reference.canonicalModuleCode
        normalized["canonicalModuleCode"] = reference.canonicalModuleCode
    if reference.featureCode:
        normalized["featureCode"] = reference.featureCode
    if reference.legacyModuleCode:
        normalized["legacyModuleCode"] = reference.legacyModuleCode
    if reference.contextCode:
        normalized["contextCode"] = reference.contextCode
    if reference.needsReview:
        normalized["migrationWarning"] = reference.warning
    normalized.pop("moduleNumber", None)
    return normalized


def collect_module_migration_warnings(payload: Any, *, entity_type: str = "payload") -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"moduleCode", "sourceModuleCode", "canonicalModuleCode", "targetModuleCode"}:
                    reference = normalize_module_reference(item)
                    if reference.needsReview:
                        warnings.append(
                            {
                                "entityType": entity_type,
                                "path": f"{path}.{key}".strip("."),
                                "sourceValue": item,
                                "targetValue": reference.targetCode,
                                "warning": reference.warning,
                                "status": "REVIEW",
                            }
                        )
                visit(item, f"{path}.{key}".strip("."))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")

    visit(payload, "")
    return warnings


def _registry_description(registry_key: str) -> str:
    return {
        "module_registry": "Versioned PlatformModuleRegistry / DashboardModuleRegistry compatibility state.",
        "role_matrix": "Versioned role access matrix by moduleCode and scope.",
        "permissions": "Versioned permission references and canonical module mappings.",
        "widgets": "Versioned WidgetRegistry compatibility state.",
        "dashboard_profiles": "Versioned role dashboard access profiles.",
        "dashboard_layouts": "Versioned UserDashboardLayout compatibility state.",
        "quick_actions": "Versioned QuickActionRegistry compatibility state.",
        "module_lifecycle": "Versioned module lifecycle rules.",
        "canonical_map": "Versioned canonical module map.",
        "legacy_aliases": "Versioned legacy alias and redirect rules.",
    }.get(registry_key, registry_key)
