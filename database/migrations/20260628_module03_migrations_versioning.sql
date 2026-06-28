-- Module 03 / Sprint 25: Migrations and versioning
-- Tracks registry/layout/widget/permission version state without destructive rewrites.

CREATE TABLE IF NOT EXISTS module_registry_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registry_key VARCHAR(120) NOT NULL,
    registry_version VARCHAR(80) NOT NULL,
    source_module_code VARCHAR(120) NOT NULL,
    description TEXT,
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (registry_key, registry_version)
);

CREATE INDEX IF NOT EXISTS ix_module_registry_versions_registry_key
    ON module_registry_versions (registry_key);

CREATE INDEX IF NOT EXISTS ix_module_registry_versions_registry_version
    ON module_registry_versions (registry_version);

CREATE INDEX IF NOT EXISTS ix_module_registry_versions_source_module_code
    ON module_registry_versions (source_module_code);

CREATE UNIQUE INDEX IF NOT EXISTS uq_module_registry_versions_key_version
    ON module_registry_versions (registry_key, registry_version);

ALTER TABLE module_registry_versions
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS module_migration_warnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    migration_code VARCHAR(120) NOT NULL,
    entity_type VARCHAR(120) NOT NULL,
    entity_id VARCHAR(160),
    source_value VARCHAR(255),
    target_value VARCHAR(255),
    warning TEXT NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'REVIEW',
    payload JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_module_migration_warnings_migration_code
    ON module_migration_warnings (migration_code);

CREATE INDEX IF NOT EXISTS ix_module_migration_warnings_entity_type
    ON module_migration_warnings (entity_type);

CREATE INDEX IF NOT EXISTS ix_module_migration_warnings_source_value
    ON module_migration_warnings (source_value);

CREATE INDEX IF NOT EXISTS ix_module_migration_warnings_status
    ON module_migration_warnings (status);

ALTER TABLE module_migration_warnings
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

INSERT INTO module_registry_versions (
    registry_key,
    registry_version,
    source_module_code,
    description,
    payload,
    updated_at
)
VALUES
(
    'canonical_map',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Canonical module map and required legacy migrations for Sprint 25.',
    '{
      "rules": [
        {"legacyModuleCode":"MODULE_07_DIGITAL_OBJECT","canonicalModuleCode":"MODULE_07_DIGITAL_HOUSE","redirectRoute":"/modules/digital-house","status":"MERGED"},
        {"legacyModuleCode":"MODULE_14_PRICE_HISTORY","canonicalModuleCode":"MODULE_11_ANALYTICS","featureCode":"PRICE_DYNAMICS","redirectRoute":"/modules/analytics?section=price-dynamics","status":"MERGED"},
        {"legacyModuleCode":"MODULE_14_CONSTRUCTOR_LITE","canonicalModuleCode":"MODULE_19_CONSTRUCTOR_LITE","redirectRoute":"/modules/constructor-lite","status":"DEPRECATED"},
        {"legacyModuleCode":"MODULE_15_CONSTRUCTION_GROUPS","canonicalModuleCode":"MODULE_01_MATERIAL_HUB","featureCode":"CONSTRUCTION_APPLICABILITY","redirectRoute":"/api/v1/admin/material-hub/view?feature=construction-applicability","status":"DEPRECATED"},
        {"legacyModuleCode":"MODULE_16_ADMIN_CABINET","canonicalModuleCode":"MODULE_03_USERS_ROLES","targetContextCode":"DASHBOARD_ADMIN_CONTEXT","redirectRoute":"/api/v1/admin/cabinet/view","status":"DEPRECATED_CONTEXT"}
      ],
      "unknownPolicy": "preserve_warning_review",
      "moduleNumberPolicy": "display_legacy_only"
    }'::jsonb,
    now()
),
(
    'legacy_aliases',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Legacy aliases and redirects are preserved for layouts, widgets, permissions, routes and audit history.',
    '{
      "safeMigration": true,
      "physicalDelete": false,
      "reviewUnknownReferences": true
    }'::jsonb,
    now()
),
(
    'module_registry',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for PlatformModuleRegistry and DashboardModuleRegistry compatibility state.',
    '{"owner":"MODULE_03_USERS_ROLES","dashboardIsDisplayLayer":true}'::jsonb,
    now()
),
(
    'role_matrix',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for role matrix based on moduleCode/canonicalModuleCode, not module number.',
    '{"moduleNumberAllowedForLogic":false}'::jsonb,
    now()
),
(
    'permissions',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for permission references and canonical module mappings.',
    '{"normalizeLegacyModuleCode":true}'::jsonb,
    now()
),
(
    'widgets',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for WidgetRegistry compatibility while payload remains module-owned.',
    '{"dashboardWidgetRegistryLayer":"aggregator_mock_compatibility"}'::jsonb,
    now()
),
(
    'dashboard_profiles',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for role dashboard access profiles.',
    '{"filteredByPermissionGuard":true}'::jsonb,
    now()
),
(
    'dashboard_layouts',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for UserDashboardLayout normalization and warnings.',
    '{"legacyLayoutPolicy":"normalize_without_deleting"}'::jsonb,
    now()
),
(
    'quick_actions',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for QuickActionRegistry references by actionCode/moduleCode/featureCode.',
    '{"moduleNumberAllowedForLogic":false}'::jsonb,
    now()
),
(
    'module_lifecycle',
    'module03-sprint25-v1',
    'MODULE_03_USERS_ROLES',
    'Version marker for module lifecycle statuses and visibility rules.',
    '{"statuses":["PLANNED","DRAFT","ACTIVE","DISABLED","DEPRECATED","ARCHIVED","MERGED"]}'::jsonb,
    now()
)
ON CONFLICT (registry_key, registry_version) DO UPDATE
SET
    source_module_code = EXCLUDED.source_module_code,
    description = EXCLUDED.description,
    payload = EXCLUDED.payload,
    updated_at = now();

COMMENT ON TABLE module_registry_versions
IS 'Sprint 25 version markers for Module 03 registries, canonical maps, permissions, widgets, layouts and quick actions.';

COMMENT ON TABLE module_migration_warnings
IS 'Non-destructive review queue for unknown or unsafe legacy references found during module registry/layout/widget migrations.';
