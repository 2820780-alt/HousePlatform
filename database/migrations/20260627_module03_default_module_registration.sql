-- Module 03 / Sprint 10. Default registration metadata for future modules.
-- This keeps PlatformModuleRegistry code-first and does not create business logic.

BEGIN;

ALTER TABLE platform_module_registry
    ADD COLUMN IF NOT EXISTS default_permissions jsonb,
    ADD COLUMN IF NOT EXISTS available_actions jsonb,
    ADD COLUMN IF NOT EXISTS dashboard_widgets jsonb,
    ADD COLUMN IF NOT EXISTS owner_scope_rules jsonb;

CREATE INDEX IF NOT EXISTS ix_platform_module_registry_available_actions
    ON platform_module_registry USING gin (available_actions);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_dashboard_widgets
    ON platform_module_registry USING gin (dashboard_widgets);

UPDATE platform_module_registry
SET
    default_permissions = '[
        {"role": "SUPER_ADMIN", "accessLevel": "ADMIN", "scope": "GLOBAL"},
        {"role": "PLATFORM_ADMIN", "accessLevel": "VIEW", "scope": "GLOBAL"},
        {"role": "MODERATOR", "accessLevel": "APPROVE", "scope": "GLOBAL"},
        {"role": "CONTRACTOR", "accessLevel": "VIEW", "scope": "OWN"},
        {"role": "CUSTOMER", "accessLevel": "VIEW", "scope": "OWN"}
    ]'::jsonb,
    available_actions = '["VIEW", "CREATE_ISSUE", "APPROVE_CHECK", "EXPORT_REPORT"]'::jsonb,
    dashboard_widgets = '["QUALITY_CONTROL_ISSUES"]'::jsonb,
    owner_scope_rules = '{
        "ownerField": "workspaceId",
        "regionField": "service_region_id",
        "notes": "Module-owned payloads will define concrete object/project visibility."
    }'::jsonb,
    feature_codes = CASE
        WHEN COALESCE(feature_codes, '[]'::jsonb) ? 'QUALITY_ISSUES'
            THEN COALESCE(feature_codes, '[]'::jsonb)
        ELSE COALESCE(feature_codes, '[]'::jsonb) || '["QUALITY_ISSUES", "CHECKLISTS", "ACCEPTANCE_REPORTS"]'::jsonb
    END,
    updated_at = now()
WHERE module_code = 'MODULE_18_QUALITY_CONTROL';

UPDATE platform_module_registry
SET
    canonical_module_code = 'MODULE_18_QUALITY_CONTROL',
    status = 'DEPRECATED',
    is_active = false,
    is_public = false,
    is_visible_in_sidebar = false,
    is_visible_on_dashboard = false,
    is_visible_on_atom_map = false,
    is_available_for_widgets = false,
    redirect_route = '/modules/quality-control',
    description = 'Legacy conflicting quality-control code. MODULE_16 is reserved for logistics delivery; use MODULE_18_QUALITY_CONTROL.',
    updated_at = now()
WHERE module_code = 'MODULE_16_QUALITY_CONTROL';

COMMIT;
