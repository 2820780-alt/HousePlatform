-- Debug package / Constructor Lite canonical code normalization.
-- MODULE_14_CONSTRUCTOR_LITE is a legacy alias. Canonical target is MODULE_19_CONSTRUCTOR_LITE.

BEGIN;

UPDATE platform_module_registry
SET
    canonical_module_code = 'MODULE_19_CONSTRUCTOR_LITE',
    status = 'DEPRECATED',
    is_active = false,
    is_public = false,
    is_visible_in_sidebar = false,
    is_visible_on_dashboard = false,
    is_visible_on_atom_map = false,
    is_available_for_widgets = false,
    redirect_route = '/modules/constructor-lite',
    description = 'Legacy alias for MODULE_19_CONSTRUCTOR_LITE. Kept for old routes, layouts, widgets, permissions and audit history.',
    updated_at = now()
WHERE module_code = 'MODULE_14_CONSTRUCTOR_LITE';

INSERT INTO platform_module_registry (
    module_code,
    canonical_module_code,
    title,
    short_title,
    description,
    version,
    legacy_number,
    display_number,
    visual_number,
    display_order,
    status,
    route,
    redirect_route,
    icon,
    color,
    is_system,
    is_active,
    is_public,
    is_visible_in_sidebar,
    is_visible_on_dashboard,
    is_visible_on_atom_map,
    is_available_for_widgets,
    legacy_codes,
    feature_codes
)
VALUES (
    'MODULE_19_CONSTRUCTOR_LITE',
    'MODULE_19_CONSTRUCTOR_LITE',
    'Constructor Lite',
    'Constructor',
    'Future lightweight constructor for object plan, scenarios and solution selection.',
    'planned',
    19,
    19,
    19,
    1900,
    'PLANNED',
    '/modules/constructor-lite',
    NULL,
    'blocks',
    '#8b5cf6',
    true,
    false,
    false,
    false,
    false,
    false,
    false,
    '["MODULE_14_CONSTRUCTOR_LITE"]'::jsonb,
    '["CONSTRUCTOR_SCENARIOS", "HOUSE_OPTIONS", "SOLUTION_COMPARE"]'::jsonb
)
ON CONFLICT (module_code) DO UPDATE
SET
    canonical_module_code = EXCLUDED.canonical_module_code,
    legacy_codes = EXCLUDED.legacy_codes,
    feature_codes = EXCLUDED.feature_codes,
    status = CASE
        WHEN platform_module_registry.status = 'ACTIVE' THEN platform_module_registry.status
        ELSE EXCLUDED.status
    END,
    route = EXCLUDED.route,
    updated_at = now();

COMMIT;
