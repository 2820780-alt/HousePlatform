-- Debug package / Construction Groups module alias normalization.
-- MODULE_15_CONSTRUCTION_GROUPS is not an active business module.
-- Canonical target: MODULE_01_MATERIAL_HUB / CONSTRUCTION_APPLICABILITY.

BEGIN;

UPDATE platform_module_registry
SET
    canonical_module_code = 'MODULE_01_MATERIAL_HUB',
    status = 'DEPRECATED',
    is_active = false,
    is_public = false,
    is_visible_in_sidebar = false,
    is_visible_on_dashboard = false,
    is_visible_on_atom_map = false,
    is_available_for_widgets = false,
    owner_module_code = 'MODULE_01_MATERIAL_HUB',
    redirect_route = '/api/v1/admin/material-hub/view?feature=construction-applicability',
    feature_codes = '["CONSTRUCTION_APPLICABILITY"]'::jsonb,
    description = 'Legacy feature alias for construction applicability in Material Hub. Kept for old layouts, widgets, permissions and audit history.',
    updated_at = now()
WHERE module_code = 'MODULE_15_CONSTRUCTION_GROUPS';

UPDATE platform_module_registry
SET
    feature_codes = CASE
        WHEN COALESCE(feature_codes, '[]'::jsonb) ? 'CONSTRUCTION_APPLICABILITY'
            THEN COALESCE(feature_codes, '[]'::jsonb)
        ELSE COALESCE(feature_codes, '[]'::jsonb) || '["CONSTRUCTION_APPLICABILITY"]'::jsonb
    END,
    updated_at = now()
WHERE module_code = 'MODULE_01_MATERIAL_HUB';

UPDATE platform_module_registry
SET
    feature_codes = CASE
        WHEN COALESCE(feature_codes, '[]'::jsonb) ? 'TECHNOLOGY_CONSTRUCTION_GROUPS'
            THEN COALESCE(feature_codes, '[]'::jsonb)
        ELSE COALESCE(feature_codes, '[]'::jsonb) || '["TECHNOLOGY_CONSTRUCTION_GROUPS"]'::jsonb
    END,
    updated_at = now()
WHERE module_code = 'MODULE_02_KNOWLEDGE_BASE';

COMMIT;
