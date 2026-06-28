from app.services.dashboard_system_contexts import DASHBOARD_ADMIN_CONTEXT
from app.services.module_versioning import (
    MODULE_REGISTRY_VERSION,
    collect_module_migration_warnings,
    get_module_migration_rules,
    get_versioned_registry_snapshots,
    normalize_module_code_list,
    normalize_module_reference,
    normalize_versioned_layout,
    normalize_versioned_quick_action_reference,
    normalize_versioned_widget_reference,
)


def test_required_legacy_migrations_are_explicit():
    rules = {rule["legacyModuleCode"]: rule for rule in get_module_migration_rules()}

    assert rules["MODULE_07_DIGITAL_OBJECT"]["canonicalModuleCode"] == "MODULE_07_DIGITAL_HOUSE"
    assert rules["MODULE_14_PRICE_HISTORY"]["canonicalModuleCode"] == "MODULE_11_ANALYTICS"
    assert rules["MODULE_14_PRICE_HISTORY"]["featureCode"] == "PRICE_DYNAMICS"
    assert rules["MODULE_14_CONSTRUCTOR_LITE"]["canonicalModuleCode"] == "MODULE_19_CONSTRUCTOR_LITE"
    assert rules["MODULE_15_CONSTRUCTION_GROUPS"]["canonicalModuleCode"] == "MODULE_01_MATERIAL_HUB"
    assert rules["MODULE_15_CONSTRUCTION_GROUPS"]["featureCode"] == "CONSTRUCTION_APPLICABILITY"
    assert rules["MODULE_16_ADMIN_CABINET"]["targetContextCode"] == DASHBOARD_ADMIN_CONTEXT


def test_normalize_module_reference_preserves_warning_for_unknown_code():
    reference = normalize_module_reference("MODULE_99_UNKNOWN_LEGACY")

    assert reference.targetCode == "MODULE_99_UNKNOWN_LEGACY"
    assert reference.needsReview is True
    assert "preserved for review" in (reference.warning or "")


def test_normalize_module_code_list_deduplicates_canonical_targets():
    assert normalize_module_code_list(
        [
            "MODULE_14_PRICE_HISTORY",
            "MODULE_11_ANALYTICS",
            "MODULE_16_ADMIN_CABINET",
            "MODULE_07_DIGITAL_OBJECT",
        ]
    ) == [
        "MODULE_11_ANALYTICS",
        DASHBOARD_ADMIN_CONTEXT,
        "MODULE_07_DIGITAL_HOUSE",
    ]


def test_normalize_versioned_widget_reference_migrates_price_history_feature():
    widget = normalize_versioned_widget_reference(
        {
            "widgetCode": "old-price-widget",
            "sourceModuleCode": "MODULE_14_PRICE_HISTORY",
            "moduleNumber": 14,
        }
    )

    assert widget["sourceModuleCode"] == "MODULE_11_ANALYTICS"
    assert widget["canonicalModuleCode"] == "MODULE_11_ANALYTICS"
    assert widget["featureCode"] == "PRICE_DYNAMICS"
    assert widget["legacyModuleCode"] == "MODULE_14_PRICE_HISTORY"
    assert "moduleNumber" not in widget


def test_normalize_versioned_quick_action_reference_keeps_admin_context():
    action = normalize_versioned_quick_action_reference(
        {
            "quickActionCode": "DASHBOARD_CONFIGURE",
            "sourceModuleCode": "MODULE_16_ADMIN_CABINET",
        }
    )

    assert action["sourceModuleCode"] == "MODULE_03_USERS_ROLES"
    assert action["canonicalModuleCode"] == "MODULE_03_USERS_ROLES"
    assert action["contextCode"] == DASHBOARD_ADMIN_CONTEXT
    assert action["legacyModuleCode"] == "MODULE_16_ADMIN_CABINET"


def test_normalize_versioned_layout_migrates_favorites_and_widgets_without_payload_loss():
    layout = normalize_versioned_layout(
        {
            "favoriteModules": ["MODULE_14_PRICE_HISTORY", "MODULE_16_ADMIN_CABINET"],
            "widgets": [
                {
                    "widgetCode": "constructor",
                    "sourceModuleCode": "MODULE_14_CONSTRUCTOR_LITE",
                    "size": "medium",
                },
                {
                    "widgetCode": "unknown",
                    "sourceModuleCode": "MODULE_99_UNKNOWN_LEGACY",
                    "size": "small",
                },
            ],
        }
    )

    assert layout["favoriteModules"] == ["MODULE_11_ANALYTICS", DASHBOARD_ADMIN_CONTEXT]
    assert layout["widgets"][0]["sourceModuleCode"] == "MODULE_19_CONSTRUCTOR_LITE"
    assert layout["widgets"][0]["legacyModuleCode"] == "MODULE_14_CONSTRUCTOR_LITE"
    assert layout["widgets"][0]["size"] == "medium"
    assert layout["widgets"][1]["sourceModuleCode"] == "MODULE_99_UNKNOWN_LEGACY"
    assert layout["widgets"][1]["migrationWarning"]


def test_collect_module_migration_warnings_finds_unknown_references_only():
    warnings = collect_module_migration_warnings(
        {
            "moduleCode": "MODULE_14_PRICE_HISTORY",
            "widgets": [{"sourceModuleCode": "MODULE_99_UNKNOWN_LEGACY"}],
        },
        entity_type="dashboard_layout",
    )

    assert warnings == [
        {
            "entityType": "dashboard_layout",
            "path": "widgets[0].sourceModuleCode",
            "sourceValue": "MODULE_99_UNKNOWN_LEGACY",
            "targetValue": "MODULE_99_UNKNOWN_LEGACY",
            "warning": "Unknown module reference 'MODULE_99_UNKNOWN_LEGACY' was preserved for review.",
            "status": "REVIEW",
        }
    ]


def test_versioned_registry_snapshots_cover_required_registries():
    snapshots = get_versioned_registry_snapshots()
    keys = {snapshot["registryKey"] for snapshot in snapshots}

    assert MODULE_REGISTRY_VERSION == "module03-sprint25-v1"
    assert {
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
    }.issubset(keys)
