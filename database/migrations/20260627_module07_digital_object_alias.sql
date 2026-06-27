-- Debug package / Module 07 legacy alias normalization.
-- MODULE_07_DIGITAL_OBJECT is a legacy code. Canonical target is MODULE_07_DIGITAL_HOUSE.

BEGIN;

UPDATE platform_module_registry
SET
    canonical_module_code = 'MODULE_07_DIGITAL_HOUSE',
    status = 'MERGED',
    is_active = false,
    is_public = false,
    is_visible_in_sidebar = false,
    is_visible_on_dashboard = false,
    is_visible_on_atom_map = false,
    is_available_for_widgets = false,
    merged_into_module_code = 'MODULE_07_DIGITAL_HOUSE',
    redirect_route = '/modules/digital-house',
    description = 'Legacy alias for MODULE_07_DIGITAL_HOUSE. Kept for old routes, layouts, widgets, permissions and audit history.',
    updated_at = now()
WHERE module_code = 'MODULE_07_DIGITAL_OBJECT';

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
    'MODULE_07_DIGITAL_HOUSE',
    'MODULE_07_DIGITAL_HOUSE',
    'Образ объекта',
    'Объект',
    'Digital object of construction: profile, estimates, procurement, storage, expenses and history.',
    'planned',
    7,
    7,
    7,
    700,
    'PLANNED',
    '/modules/digital-house',
    NULL,
    'home',
    '#60a5fa',
    true,
    false,
    false,
    false,
    false,
    false,
    false,
    '["MODULE_07_DIGITAL_OBJECT", "MODULE_07_DIGITAL_OBJECT_V2"]'::jsonb,
    '["HOUSE_PROFILE", "HOUSE_ESTIMATES", "HOUSE_PURCHASES", "HOUSE_STORAGE", "HOUSE_EXPENSES", "HOUSE_HISTORY"]'::jsonb
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
