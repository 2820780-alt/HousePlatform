-- Module 03 / Sprint 2.1. Seed planned future modules.
-- Existing module_code rows are not downgraded or renamed in this migration.

BEGIN;

INSERT INTO platform_module_registry (
    module_code,
    canonical_module_code,
    title,
    short_title,
    version,
    legacy_number,
    display_number,
    visual_number,
    display_order,
    status,
    route,
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
VALUES
    ('MODULE_05_ESTIMATE_ENGINE', 'MODULE_05_ESTIMATE_ENGINE', 'Estimate Engine', 'Estimate Engine', 'planned', 5, 5, 5, 510, 'PLANNED', '/modules/estimate-engine', 'calculator', '#0ea5e9', true, false, false, false, false, false, false, '["MODULE_05_ESTIMATES"]'::jsonb, NULL),
    ('MODULE_07_DIGITAL_HOUSE', 'MODULE_07_DIGITAL_HOUSE', 'Digital House', 'Digital House', 'planned', 7, 7, 7, 710, 'PLANNED', '/modules/digital-house', 'home', '#14b8a6', true, false, false, false, false, false, false, '["MODULE_07_DIGITAL_OBJECT"]'::jsonb, NULL),
    ('MODULE_08_PARTNER_PORTAL', 'MODULE_08_PARTNER_PORTAL', 'Partner Portal', 'Partners', 'planned', 8, 8, 8, 810, 'PLANNED', '/modules/partner-portal', 'users', '#38bdf8', true, false, false, false, false, false, false, NULL, NULL),
    ('MODULE_09_PROCUREMENT', 'MODULE_09_PROCUREMENT', 'Procurement', 'Procurement', 'planned', 9, 9, 9, 910, 'PLANNED', '/modules/procurement', 'shopping-cart', '#06b6d4', true, false, false, false, false, false, false, '["MODULE_08_PROCUREMENT"]'::jsonb, NULL),
    ('MODULE_13_PROJECT_COLLABORATION', 'MODULE_13_PROJECT_COLLABORATION', 'Project Collaboration', 'Collaboration', 'planned', 13, 13, 13, 1310, 'PLANNED', '/modules/project-collaboration', 'messages-square', '#64748b', true, false, false, false, false, false, false, NULL, NULL),
    ('MODULE_14_CONSTRUCTOR_LITE', 'MODULE_14_CONSTRUCTOR_LITE', 'Constructor Lite', 'Constructor', 'planned', 14, 14, 14, 1410, 'PLANNED', '/modules/constructor-lite', 'drafting-compass', '#8b5cf6', true, false, false, false, false, false, false, NULL, NULL),
    ('MODULE_15_CONTRACTS', 'MODULE_15_CONTRACTS', 'Contracts', 'Contracts', 'planned', 15, 15, 15, 1510, 'PLANNED', '/modules/contracts', 'file-signature', '#10b981', true, false, false, false, false, false, false, NULL, NULL),
    ('MODULE_16_LOGISTICS_DELIVERY', 'MODULE_16_LOGISTICS_DELIVERY', 'Logistics Delivery', 'Logistics', 'planned', 16, 16, 16, 1610, 'PLANNED', '/modules/logistics-delivery', 'truck', '#f97316', true, false, false, false, false, false, false, NULL, NULL),
    ('MODULE_17_FINANCE_PAYMENTS', 'MODULE_17_FINANCE_PAYMENTS', 'Finance Payments', 'Finance', 'planned', 17, 17, 17, 1710, 'PLANNED', '/modules/finance-payments', 'wallet-cards', '#22c55e', true, false, false, false, false, false, false, NULL, NULL),
    ('MODULE_18_QUALITY_CONTROL', 'MODULE_18_QUALITY_CONTROL', 'Quality Control', 'Quality', 'planned', 18, 18, 18, 1810, 'PLANNED', '/modules/quality-control', 'badge-check', '#ef4444', true, false, false, false, false, false, false, NULL, NULL)
ON CONFLICT (module_code) DO NOTHING;

COMMIT;
