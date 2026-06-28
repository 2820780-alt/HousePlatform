-- Module 03 / Sprint 18: Role Dashboard Access Profiles
-- This table stores access/preset profiles for the existing Dashboard shell.
-- It does not create separate dashboards and does not store business widget payload.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS role_dashboard_access_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_code VARCHAR(80) NOT NULL UNIQUE,
    source_module_code VARCHAR(120) NOT NULL DEFAULT 'MODULE_03_USERS_ROLES',
    allowed_module_codes JSON NOT NULL DEFAULT '[]'::json,
    allowed_feature_codes JSON NOT NULL DEFAULT '[]'::json,
    default_widget_codes JSON NOT NULL DEFAULT '[]'::json,
    default_quick_action_codes JSON NOT NULL DEFAULT '[]'::json,
    hidden_widget_codes JSON NOT NULL DEFAULT '[]'::json,
    default_layout_code VARCHAR(120),
    description TEXT,
    settings JSON,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

ALTER TABLE role_dashboard_access_profiles
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN source_module_code SET DEFAULT 'MODULE_03_USERS_ROLES',
    ALTER COLUMN allowed_module_codes SET DEFAULT '[]'::json,
    ALTER COLUMN allowed_feature_codes SET DEFAULT '[]'::json,
    ALTER COLUMN default_widget_codes SET DEFAULT '[]'::json,
    ALTER COLUMN default_quick_action_codes SET DEFAULT '[]'::json,
    ALTER COLUMN hidden_widget_codes SET DEFAULT '[]'::json,
    ALTER COLUMN is_system SET DEFAULT TRUE,
    ALTER COLUMN is_active SET DEFAULT TRUE,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_role_dashboard_access_profiles_role_code
    ON role_dashboard_access_profiles(role_code);

CREATE INDEX IF NOT EXISTS ix_role_dashboard_access_profiles_default_layout_code
    ON role_dashboard_access_profiles(default_layout_code);

CREATE INDEX IF NOT EXISTS ix_role_dashboard_access_profiles_is_system
    ON role_dashboard_access_profiles(is_system);

CREATE INDEX IF NOT EXISTS ix_role_dashboard_access_profiles_is_active
    ON role_dashboard_access_profiles(is_active);

INSERT INTO role_dashboard_access_profiles (
    role_code,
    source_module_code,
    allowed_module_codes,
    allowed_feature_codes,
    default_widget_codes,
    default_quick_action_codes,
    hidden_widget_codes,
    default_layout_code,
    description,
    settings,
    is_system,
    is_active
) VALUES
(
    'SUPER_ADMIN',
    'MODULE_03_USERS_ROLES',
    '["MODULE_01_MATERIAL_HUB","MODULE_02_KNOWLEDGE_BASE","MODULE_03_USERS_ROLES","MODULE_04_WORKS_COSTS","MODULE_05_ESTIMATES","MODULE_06_ESTIMATE_AUDIT","MODULE_08_PROCUREMENT","MODULE_09_TENDERS","MODULE_10_MARKETPLACE","MODULE_11_ANALYTICS","MODULE_12_AI_ASSISTANT","MODULE_13_AUDIT"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW","PRICE_DYNAMICS","DASHBOARD_ROLE_PREVIEW","DASHBOARD_REGISTRY_ADMIN"]'::json,
    '["materials-kpi","classification-queue","price-dynamics","source-health","system-alerts","atom-map"]'::json,
    '["MATERIAL_CREATE","SUPPLIER_PRICE_UPLOAD","SOURCE_TASK_CREATE","MATERIAL_MODERATION_OPEN","SOURCE_ERRORS_OPEN","SOURCE_CREATE","DOCUMENT_LIST_OPEN","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'ADMIN_DASHBOARD_DEFAULT',
    'Owner-level profile for viewing and configuring the existing Dashboard shell.',
    '{"workspaceType":"ADMINISTRATION","activeCabinetType":"ADMIN","favoriteModuleCodes":["MODULE_01_MATERIAL_HUB","MODULE_11_ANALYTICS","MODULE_03_USERS_ROLES"]}'::json,
    TRUE,
    TRUE
),
(
    'PLATFORM_ADMIN',
    'MODULE_03_USERS_ROLES',
    '["MODULE_01_MATERIAL_HUB","MODULE_02_KNOWLEDGE_BASE","MODULE_03_USERS_ROLES","MODULE_11_ANALYTICS"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW","PRICE_DYNAMICS","DASHBOARD_ROLE_PREVIEW","DASHBOARD_REGISTRY_ADMIN"]'::json,
    '["materials-kpi","classification-queue","price-dynamics","source-health","system-alerts","atom-map"]'::json,
    '["MATERIAL_CREATE","SUPPLIER_PRICE_UPLOAD","SOURCE_TASK_CREATE","MATERIAL_MODERATION_OPEN","SOURCE_ERRORS_OPEN","SOURCE_CREATE","DOCUMENT_LIST_OPEN","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'ADMIN_DASHBOARD_DEFAULT',
    'Platform administration profile without Super Admin ownership-level operations.',
    '{"workspaceType":"ADMINISTRATION","activeCabinetType":"ADMIN","favoriteModuleCodes":["MODULE_01_MATERIAL_HUB","MODULE_11_ANALYTICS","MODULE_03_USERS_ROLES"]}'::json,
    TRUE,
    TRUE
),
(
    'MODERATOR',
    'MODULE_03_USERS_ROLES',
    '["MODULE_01_MATERIAL_HUB","MODULE_02_KNOWLEDGE_BASE"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW","PRICE_DYNAMICS"]'::json,
    '["classification-queue","materials-kpi","source-health"]'::json,
    '["MATERIAL_MODERATION_OPEN","SOURCE_ERRORS_OPEN","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'MODERATION_DASHBOARD_DEFAULT',
    'Moderator view profile for the existing Dashboard shell.',
    '{"workspaceType":"MODERATION","activeCabinetType":"MODERATOR","favoriteModuleCodes":["MODULE_01_MATERIAL_HUB","MODULE_02_KNOWLEDGE_BASE"]}'::json,
    TRUE,
    TRUE
),
(
    'KNOWLEDGE_MANAGER',
    'MODULE_03_USERS_ROLES',
    '["MODULE_02_KNOWLEDGE_BASE","MODULE_01_MATERIAL_HUB","MODULE_11_ANALYTICS"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW"]'::json,
    '["materials-kpi","classification-queue"]'::json,
    '["MATERIAL_CREATE","DOCUMENT_LIST_OPEN","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'KNOWLEDGE_DASHBOARD_DEFAULT',
    'Knowledge manager view profile for the existing Dashboard shell.',
    '{"workspaceType":"KNOWLEDGE","activeCabinetType":"KNOWLEDGE_MANAGER","favoriteModuleCodes":["MODULE_02_KNOWLEDGE_BASE","MODULE_01_MATERIAL_HUB","MODULE_11_ANALYTICS"]}'::json,
    TRUE,
    TRUE
),
(
    'ESTIMATOR',
    'MODULE_03_USERS_ROLES',
    '["MODULE_05_ESTIMATES","MODULE_06_ESTIMATE_AUDIT","MODULE_01_MATERIAL_HUB","MODULE_02_KNOWLEDGE_BASE","MODULE_11_ANALYTICS"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW","PRICE_DYNAMICS"]'::json,
    '["price-dynamics","materials-kpi"]'::json,
    '["DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'ESTIMATOR_DASHBOARD_DEFAULT',
    'Estimator view profile for the existing Dashboard shell.',
    '{"workspaceType":"ESTIMATES","activeCabinetType":"ESTIMATOR","favoriteModuleCodes":["MODULE_05_ESTIMATES","MODULE_06_ESTIMATE_AUDIT","MODULE_01_MATERIAL_HUB"]}'::json,
    TRUE,
    TRUE
),
(
    'ENGINEER_DESIGNER',
    'MODULE_03_USERS_ROLES',
    '["MODULE_02_KNOWLEDGE_BASE","MODULE_04_WORKS_COSTS","MODULE_11_ANALYTICS"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW"]'::json,
    '["materials-kpi"]'::json,
    '["DOCUMENT_LIST_OPEN","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'ENGINEER_DASHBOARD_DEFAULT',
    'Engineer/designer view profile for the existing Dashboard shell.',
    '{"workspaceType":"ENGINEERING","activeCabinetType":"ENGINEER_DESIGNER","favoriteModuleCodes":["MODULE_02_KNOWLEDGE_BASE","MODULE_04_WORKS_COSTS","MODULE_11_ANALYTICS"]}'::json,
    TRUE,
    TRUE
),
(
    'SUPPLIER',
    'MODULE_03_USERS_ROLES',
    '["MODULE_01_MATERIAL_HUB","MODULE_08_PROCUREMENT","MODULE_09_TENDERS","MODULE_10_MARKETPLACE"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW"]'::json,
    '["materials-kpi"]'::json,
    '["SUPPLIER_PRICE_UPLOAD","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'SUPPLIER_DASHBOARD_DEFAULT',
    'Supplier view profile for the existing Dashboard shell.',
    '{"workspaceType":"SUPPLIER","activeCabinetType":"SUPPLIER","favoriteModuleCodes":["MODULE_01_MATERIAL_HUB","MODULE_08_PROCUREMENT","MODULE_09_TENDERS"]}'::json,
    TRUE,
    TRUE
),
(
    'CONTRACTOR',
    'MODULE_03_USERS_ROLES',
    '["MODULE_04_WORKS_COSTS","MODULE_11_ANALYTICS"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW","PRICE_DYNAMICS"]'::json,
    '["price-dynamics"]'::json,
    '["DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'CONTRACTOR_DASHBOARD_DEFAULT',
    'Contractor view profile for the existing Dashboard shell.',
    '{"workspaceType":"CONTRACTOR","activeCabinetType":"CONTRACTOR","favoriteModuleCodes":["MODULE_04_WORKS_COSTS","MODULE_11_ANALYTICS"]}'::json,
    TRUE,
    TRUE
),
(
    'CUSTOMER',
    'MODULE_03_USERS_ROLES',
    '["MODULE_05_ESTIMATES","MODULE_07_DIGITAL_HOUSE","MODULE_08_PROCUREMENT","MODULE_10_MARKETPLACE"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW"]'::json,
    '[]'::json,
    '["DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'CUSTOMER_DASHBOARD_DEFAULT',
    'Customer view profile for the existing Dashboard shell.',
    '{"workspaceType":"CUSTOMER","activeCabinetType":"CUSTOMER","favoriteModuleCodes":["MODULE_07_DIGITAL_HOUSE","MODULE_05_ESTIMATES","MODULE_08_PROCUREMENT"]}'::json,
    TRUE,
    TRUE
),
(
    'ANALYST',
    'MODULE_03_USERS_ROLES',
    '["MODULE_01_MATERIAL_HUB","MODULE_11_ANALYTICS","MODULE_13_AUDIT"]'::json,
    '["DASHBOARD_VIEW","DASHBOARD_PERSONALIZE","ATOM_MAP_VIEW","PRICE_DYNAMICS"]'::json,
    '["price-dynamics","materials-kpi","source-health"]'::json,
    '["SOURCE_ERRORS_OPEN","DOCUMENT_LIST_OPEN","DASHBOARD_CONFIGURE"]'::json,
    '[]'::json,
    'ANALYST_DASHBOARD_DEFAULT',
    'Analyst view profile for the existing Dashboard shell.',
    '{"workspaceType":"ANALYTICS","activeCabinetType":"ANALYST","favoriteModuleCodes":["MODULE_11_ANALYTICS","MODULE_01_MATERIAL_HUB","MODULE_13_AUDIT"]}'::json,
    TRUE,
    TRUE
),
(
    'VIEWER',
    'MODULE_03_USERS_ROLES',
    '["MODULE_01_MATERIAL_HUB","MODULE_02_KNOWLEDGE_BASE","MODULE_11_ANALYTICS"]'::json,
    '["DASHBOARD_VIEW","ATOM_MAP_VIEW","PRICE_DYNAMICS"]'::json,
    '["materials-kpi","price-dynamics"]'::json,
    '[]'::json,
    '[]'::json,
    'VIEWER_DASHBOARD_DEFAULT',
    'Read-only view profile for the existing Dashboard shell.',
    '{"workspaceType":"VIEW_ONLY","activeCabinetType":"VIEWER","favoriteModuleCodes":["MODULE_01_MATERIAL_HUB","MODULE_11_ANALYTICS"]}'::json,
    TRUE,
    TRUE
)
ON CONFLICT (role_code) DO UPDATE SET
    source_module_code = EXCLUDED.source_module_code,
    allowed_module_codes = EXCLUDED.allowed_module_codes,
    allowed_feature_codes = EXCLUDED.allowed_feature_codes,
    default_widget_codes = EXCLUDED.default_widget_codes,
    default_quick_action_codes = EXCLUDED.default_quick_action_codes,
    hidden_widget_codes = EXCLUDED.hidden_widget_codes,
    default_layout_code = EXCLUDED.default_layout_code,
    description = EXCLUDED.description,
    settings = EXCLUDED.settings,
    is_system = EXCLUDED.is_system,
    is_active = EXCLUDED.is_active,
    updated_at = now();
