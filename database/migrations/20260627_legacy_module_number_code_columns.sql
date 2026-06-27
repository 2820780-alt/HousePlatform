-- Debug package / module_number compatibility layer.
-- Keep module_number as legacy/display data, but add code-first columns for new logic.

BEGIN;

ALTER TABLE dashboard_widgets ADD COLUMN IF NOT EXISTS source_module_code varchar(120);
ALTER TABLE dashboard_widgets ADD COLUMN IF NOT EXISTS canonical_module_code varchar(120);
ALTER TABLE dashboard_widgets ADD COLUMN IF NOT EXISTS feature_code varchar(120);

CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_source_module_code
    ON dashboard_widgets(source_module_code);
CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_canonical_module_code
    ON dashboard_widgets(canonical_module_code);
CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_feature_code
    ON dashboard_widgets(feature_code);

ALTER TABLE favorite_modules ADD COLUMN IF NOT EXISTS module_code varchar(120);
ALTER TABLE favorite_modules ADD COLUMN IF NOT EXISTS canonical_module_code varchar(120);

CREATE INDEX IF NOT EXISTS ix_favorite_modules_module_code
    ON favorite_modules(module_code);
CREATE INDEX IF NOT EXISTS ix_favorite_modules_canonical_module_code
    ON favorite_modules(canonical_module_code);

ALTER TABLE module_access ADD COLUMN IF NOT EXISTS module_code varchar(120);
ALTER TABLE module_access ADD COLUMN IF NOT EXISTS canonical_module_code varchar(120);

CREATE INDEX IF NOT EXISTS ix_module_access_module_code
    ON module_access(module_code);
CREATE INDEX IF NOT EXISTS ix_module_access_canonical_module_code
    ON module_access(canonical_module_code);

ALTER TABLE function_access ADD COLUMN IF NOT EXISTS module_code varchar(120);
ALTER TABLE function_access ADD COLUMN IF NOT EXISTS canonical_module_code varchar(120);
ALTER TABLE function_access ADD COLUMN IF NOT EXISTS feature_code varchar(120);

CREATE INDEX IF NOT EXISTS ix_function_access_module_code
    ON function_access(module_code);
CREATE INDEX IF NOT EXISTS ix_function_access_canonical_module_code
    ON function_access(canonical_module_code);
CREATE INDEX IF NOT EXISTS ix_function_access_feature_code
    ON function_access(feature_code);

WITH legacy_module_number_map(legacy_number, module_code, canonical_module_code) AS (
    VALUES
        (1, 'MODULE_01_MATERIAL_HUB', 'MODULE_01_MATERIAL_HUB'),
        (2, 'MODULE_02_KNOWLEDGE_BASE', 'MODULE_02_KNOWLEDGE_BASE'),
        (3, 'MODULE_03_USERS_ROLES', 'MODULE_03_USERS_ROLES'),
        (4, 'MODULE_04_WORKS_COSTS', 'MODULE_04_WORKS_COSTS'),
        (5, 'MODULE_05_ESTIMATES', 'MODULE_05_ESTIMATES'),
        (6, 'MODULE_06_ESTIMATE_AUDIT', 'MODULE_06_ESTIMATE_AUDIT'),
        (7, 'MODULE_07_DIGITAL_OBJECT', 'MODULE_07_DIGITAL_HOUSE'),
        (8, 'MODULE_08_PROCUREMENT', 'MODULE_08_PROCUREMENT'),
        (9, 'MODULE_09_TENDERS', 'MODULE_09_TENDERS'),
        (10, 'MODULE_10_MARKETPLACE', 'MODULE_10_MARKETPLACE'),
        (11, 'MODULE_11_ANALYTICS', 'MODULE_11_ANALYTICS'),
        (12, 'MODULE_12_AI_ASSISTANT', 'MODULE_12_AI_ASSISTANT'),
        (13, 'MODULE_13_AUDIT', 'MODULE_13_AUDIT'),
        (14, 'MODULE_14_PRICE_HISTORY', 'MODULE_11_ANALYTICS'),
        (15, 'MODULE_15_CONSTRUCTION_GROUPS', 'MODULE_01_MATERIAL_HUB'),
        (16, 'MODULE_16_ADMIN_CABINET', 'MODULE_03_USERS_ROLES')
)
UPDATE dashboard_widgets AS widget
SET
    source_module_code = COALESCE(widget.source_module_code, legacy.module_code),
    canonical_module_code = COALESCE(widget.canonical_module_code, legacy.canonical_module_code)
FROM legacy_module_number_map AS legacy
WHERE widget.module_number = legacy.legacy_number;

WITH legacy_module_number_map(legacy_number, module_code, canonical_module_code) AS (
    VALUES
        (1, 'MODULE_01_MATERIAL_HUB', 'MODULE_01_MATERIAL_HUB'),
        (2, 'MODULE_02_KNOWLEDGE_BASE', 'MODULE_02_KNOWLEDGE_BASE'),
        (3, 'MODULE_03_USERS_ROLES', 'MODULE_03_USERS_ROLES'),
        (4, 'MODULE_04_WORKS_COSTS', 'MODULE_04_WORKS_COSTS'),
        (5, 'MODULE_05_ESTIMATES', 'MODULE_05_ESTIMATES'),
        (6, 'MODULE_06_ESTIMATE_AUDIT', 'MODULE_06_ESTIMATE_AUDIT'),
        (7, 'MODULE_07_DIGITAL_OBJECT', 'MODULE_07_DIGITAL_HOUSE'),
        (8, 'MODULE_08_PROCUREMENT', 'MODULE_08_PROCUREMENT'),
        (9, 'MODULE_09_TENDERS', 'MODULE_09_TENDERS'),
        (10, 'MODULE_10_MARKETPLACE', 'MODULE_10_MARKETPLACE'),
        (11, 'MODULE_11_ANALYTICS', 'MODULE_11_ANALYTICS'),
        (12, 'MODULE_12_AI_ASSISTANT', 'MODULE_12_AI_ASSISTANT'),
        (13, 'MODULE_13_AUDIT', 'MODULE_13_AUDIT'),
        (14, 'MODULE_14_PRICE_HISTORY', 'MODULE_11_ANALYTICS'),
        (15, 'MODULE_15_CONSTRUCTION_GROUPS', 'MODULE_01_MATERIAL_HUB'),
        (16, 'MODULE_16_ADMIN_CABINET', 'MODULE_03_USERS_ROLES')
)
UPDATE favorite_modules AS favorite
SET
    module_code = COALESCE(favorite.module_code, legacy.module_code),
    canonical_module_code = COALESCE(favorite.canonical_module_code, legacy.canonical_module_code)
FROM legacy_module_number_map AS legacy
WHERE favorite.module_number = legacy.legacy_number;

WITH legacy_module_number_map(legacy_number, module_code, canonical_module_code) AS (
    VALUES
        (1, 'MODULE_01_MATERIAL_HUB', 'MODULE_01_MATERIAL_HUB'),
        (2, 'MODULE_02_KNOWLEDGE_BASE', 'MODULE_02_KNOWLEDGE_BASE'),
        (3, 'MODULE_03_USERS_ROLES', 'MODULE_03_USERS_ROLES'),
        (4, 'MODULE_04_WORKS_COSTS', 'MODULE_04_WORKS_COSTS'),
        (5, 'MODULE_05_ESTIMATES', 'MODULE_05_ESTIMATES'),
        (6, 'MODULE_06_ESTIMATE_AUDIT', 'MODULE_06_ESTIMATE_AUDIT'),
        (7, 'MODULE_07_DIGITAL_OBJECT', 'MODULE_07_DIGITAL_HOUSE'),
        (8, 'MODULE_08_PROCUREMENT', 'MODULE_08_PROCUREMENT'),
        (9, 'MODULE_09_TENDERS', 'MODULE_09_TENDERS'),
        (10, 'MODULE_10_MARKETPLACE', 'MODULE_10_MARKETPLACE'),
        (11, 'MODULE_11_ANALYTICS', 'MODULE_11_ANALYTICS'),
        (12, 'MODULE_12_AI_ASSISTANT', 'MODULE_12_AI_ASSISTANT'),
        (13, 'MODULE_13_AUDIT', 'MODULE_13_AUDIT'),
        (14, 'MODULE_14_PRICE_HISTORY', 'MODULE_11_ANALYTICS'),
        (15, 'MODULE_15_CONSTRUCTION_GROUPS', 'MODULE_01_MATERIAL_HUB'),
        (16, 'MODULE_16_ADMIN_CABINET', 'MODULE_03_USERS_ROLES')
)
UPDATE module_access AS access
SET
    module_code = COALESCE(access.module_code, legacy.module_code),
    canonical_module_code = COALESCE(access.canonical_module_code, legacy.canonical_module_code)
FROM legacy_module_number_map AS legacy
WHERE access.module_number = legacy.legacy_number;

WITH legacy_module_number_map(legacy_number, module_code, canonical_module_code) AS (
    VALUES
        (1, 'MODULE_01_MATERIAL_HUB', 'MODULE_01_MATERIAL_HUB'),
        (2, 'MODULE_02_KNOWLEDGE_BASE', 'MODULE_02_KNOWLEDGE_BASE'),
        (3, 'MODULE_03_USERS_ROLES', 'MODULE_03_USERS_ROLES'),
        (4, 'MODULE_04_WORKS_COSTS', 'MODULE_04_WORKS_COSTS'),
        (5, 'MODULE_05_ESTIMATES', 'MODULE_05_ESTIMATES'),
        (6, 'MODULE_06_ESTIMATE_AUDIT', 'MODULE_06_ESTIMATE_AUDIT'),
        (7, 'MODULE_07_DIGITAL_OBJECT', 'MODULE_07_DIGITAL_HOUSE'),
        (8, 'MODULE_08_PROCUREMENT', 'MODULE_08_PROCUREMENT'),
        (9, 'MODULE_09_TENDERS', 'MODULE_09_TENDERS'),
        (10, 'MODULE_10_MARKETPLACE', 'MODULE_10_MARKETPLACE'),
        (11, 'MODULE_11_ANALYTICS', 'MODULE_11_ANALYTICS'),
        (12, 'MODULE_12_AI_ASSISTANT', 'MODULE_12_AI_ASSISTANT'),
        (13, 'MODULE_13_AUDIT', 'MODULE_13_AUDIT'),
        (14, 'MODULE_14_PRICE_HISTORY', 'MODULE_11_ANALYTICS'),
        (15, 'MODULE_15_CONSTRUCTION_GROUPS', 'MODULE_01_MATERIAL_HUB'),
        (16, 'MODULE_16_ADMIN_CABINET', 'MODULE_03_USERS_ROLES')
)
UPDATE function_access AS access
SET
    module_code = COALESCE(access.module_code, legacy.module_code),
    canonical_module_code = COALESCE(access.canonical_module_code, legacy.canonical_module_code)
FROM legacy_module_number_map AS legacy
WHERE access.module_number = legacy.legacy_number;

COMMIT;
