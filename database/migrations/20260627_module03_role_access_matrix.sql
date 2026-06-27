-- Module 03 / Sprint 9. Starter role access matrix.
-- New access rows are code-first. module_number remains only for legacy/display data.

BEGIN;

ALTER TABLE module_access ALTER COLUMN module_number DROP NOT NULL;
ALTER TABLE module_access ADD COLUMN IF NOT EXISTS access_scope varchar(30) NOT NULL DEFAULT 'GLOBAL';
ALTER TABLE function_access ADD COLUMN IF NOT EXISTS access_scope varchar(30) NOT NULL DEFAULT 'GLOBAL';

CREATE INDEX IF NOT EXISTS ix_module_access_access_scope
    ON module_access(access_scope);
CREATE INDEX IF NOT EXISTS ix_function_access_access_scope
    ON function_access(access_scope);

DROP INDEX IF EXISTS ux_module_access_scope;
CREATE UNIQUE INDEX IF NOT EXISTS ux_module_access_scope_legacy_number
    ON module_access(
        COALESCE(role_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        module_number
    )
    WHERE module_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_module_access_scope_module_code
    ON module_access(
        COALESCE(role_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(canonical_module_code, module_code),
        access_scope
    )
    WHERE module_number IS NULL
      AND COALESCE(canonical_module_code, module_code) IS NOT NULL
      AND status = 'ACTIVE';

CREATE UNIQUE INDEX IF NOT EXISTS ux_function_access_scope_feature_code
    ON function_access(
        COALESCE(role_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(canonical_module_code, module_code),
        feature_code,
        function_key,
        access_scope
    )
    WHERE COALESCE(canonical_module_code, module_code) IS NOT NULL
      AND feature_code IS NOT NULL
      AND status = 'ACTIVE';

WITH starter_matrix(role_key, module_code, access_level, access_scope) AS (
    VALUES
        ('SUPER_ADMIN', 'MODULE_01_MATERIAL_HUB', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_02_KNOWLEDGE_BASE', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_03_USERS_ROLES', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_04_WORKS_COSTS', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_05_ESTIMATES', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_06_ESTIMATE_AUDIT', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_08_PROCUREMENT', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_09_TENDERS', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_10_MARKETPLACE', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_11_ANALYTICS', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_12_AI_ASSISTANT', 'ADMIN', 'GLOBAL'),
        ('SUPER_ADMIN', 'MODULE_13_AUDIT', 'ADMIN', 'GLOBAL'),
        ('PLATFORM_ADMIN', 'MODULE_01_MATERIAL_HUB', 'ADMIN', 'GLOBAL'),
        ('PLATFORM_ADMIN', 'MODULE_02_KNOWLEDGE_BASE', 'ADMIN', 'GLOBAL'),
        ('PLATFORM_ADMIN', 'MODULE_03_USERS_ROLES', 'EDIT', 'GLOBAL'),
        ('PLATFORM_ADMIN', 'MODULE_11_ANALYTICS', 'ADMIN', 'GLOBAL'),
        ('MODERATOR', 'MODULE_01_MATERIAL_HUB', 'APPROVE', 'GLOBAL'),
        ('MODERATOR', 'MODULE_02_KNOWLEDGE_BASE', 'APPROVE', 'GLOBAL'),
        ('MODERATOR', 'MODULE_03_USERS_ROLES', 'NO_ACCESS', 'NONE'),
        ('KNOWLEDGE_MANAGER', 'MODULE_02_KNOWLEDGE_BASE', 'ADMIN', 'GLOBAL'),
        ('KNOWLEDGE_MANAGER', 'MODULE_01_MATERIAL_HUB', 'VIEW', 'GLOBAL'),
        ('KNOWLEDGE_MANAGER', 'MODULE_11_ANALYTICS', 'VIEW', 'GLOBAL'),
        ('ESTIMATOR', 'MODULE_05_ESTIMATES', 'ADMIN', 'OWN'),
        ('ESTIMATOR', 'MODULE_06_ESTIMATE_AUDIT', 'APPROVE', 'OWN'),
        ('ESTIMATOR', 'MODULE_01_MATERIAL_HUB', 'VIEW', 'LIMITED'),
        ('ESTIMATOR', 'MODULE_02_KNOWLEDGE_BASE', 'VIEW', 'LIMITED'),
        ('ESTIMATOR', 'MODULE_11_ANALYTICS', 'VIEW', 'OWN'),
        ('ENGINEER_DESIGNER', 'MODULE_02_KNOWLEDGE_BASE', 'EDIT', 'GLOBAL'),
        ('ENGINEER_DESIGNER', 'MODULE_04_WORKS_COSTS', 'VIEW', 'GLOBAL'),
        ('ENGINEER_DESIGNER', 'MODULE_11_ANALYTICS', 'VIEW', 'OWN'),
        ('SUPPLIER', 'MODULE_01_MATERIAL_HUB', 'VIEW', 'LIMITED'),
        ('SUPPLIER', 'MODULE_11_ANALYTICS', 'VIEW', 'OWN'),
        ('CONTRACTOR', 'MODULE_04_WORKS_COSTS', 'ADMIN', 'OWN'),
        ('CONTRACTOR', 'MODULE_11_ANALYTICS', 'VIEW', 'OWN'),
        ('CUSTOMER', 'MODULE_05_ESTIMATES', 'VIEW', 'OWN'),
        ('CUSTOMER', 'MODULE_08_PROCUREMENT', 'VIEW', 'OWN'),
        ('CUSTOMER', 'MODULE_02_KNOWLEDGE_BASE', 'VIEW', 'LIMITED'),
        ('ANALYST', 'MODULE_11_ANALYTICS', 'ADMIN', 'GLOBAL'),
        ('ANALYST', 'MODULE_01_MATERIAL_HUB', 'VIEW', 'GLOBAL'),
        ('ANALYST', 'MODULE_02_KNOWLEDGE_BASE', 'VIEW', 'GLOBAL'),
        ('VIEWER', 'MODULE_01_MATERIAL_HUB', 'VIEW', 'LIMITED'),
        ('VIEWER', 'MODULE_02_KNOWLEDGE_BASE', 'VIEW', 'LIMITED'),
        ('VIEWER', 'MODULE_11_ANALYTICS', 'VIEW', 'LIMITED')
)
INSERT INTO module_access (
    role_id,
    module_number,
    module_code,
    canonical_module_code,
    access_level,
    access_scope,
    status
)
SELECT
    roles.id,
    NULL,
    starter_matrix.module_code,
    COALESCE(platform_module_registry.canonical_module_code, starter_matrix.module_code),
    starter_matrix.access_level,
    starter_matrix.access_scope,
    'ACTIVE'
FROM starter_matrix
JOIN roles ON roles.role_key = starter_matrix.role_key
LEFT JOIN platform_module_registry
    ON platform_module_registry.module_code = starter_matrix.module_code
ON CONFLICT DO NOTHING;

WITH feature_matrix(role_key, module_code, feature_code, access_level, access_scope) AS (
    VALUES
        ('SUPER_ADMIN', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'ADMIN', 'GLOBAL'),
        ('PLATFORM_ADMIN', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'ADMIN', 'GLOBAL'),
        ('MODERATOR', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'VIEW', 'GLOBAL'),
        ('ESTIMATOR', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'VIEW', 'OWN'),
        ('SUPPLIER', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'VIEW', 'OWN'),
        ('CONTRACTOR', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'VIEW', 'OWN'),
        ('ANALYST', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'ADMIN', 'GLOBAL'),
        ('VIEWER', 'MODULE_11_ANALYTICS', 'PRICE_DYNAMICS', 'VIEW', 'LIMITED')
)
INSERT INTO function_access (
    role_id,
    module_number,
    module_code,
    canonical_module_code,
    feature_code,
    function_key,
    access_level,
    access_scope,
    status
)
SELECT
    roles.id,
    NULL,
    feature_matrix.module_code,
    COALESCE(platform_module_registry.canonical_module_code, feature_matrix.module_code),
    feature_matrix.feature_code,
    feature_matrix.feature_code,
    feature_matrix.access_level,
    feature_matrix.access_scope,
    'ACTIVE'
FROM feature_matrix
JOIN roles ON roles.role_key = feature_matrix.role_key
LEFT JOIN platform_module_registry
    ON platform_module_registry.module_code = feature_matrix.module_code
ON CONFLICT DO NOTHING;

UPDATE module_access
SET
    module_code = 'MODULE_11_ANALYTICS',
    canonical_module_code = 'MODULE_11_ANALYTICS',
    access_scope = CASE WHEN access_scope IS NULL THEN 'GLOBAL' ELSE access_scope END,
    updated_at = now()
WHERE module_code = 'MODULE_14_PRICE_HISTORY'
   OR canonical_module_code = 'MODULE_14_PRICE_HISTORY';

UPDATE function_access
SET
    module_code = 'MODULE_11_ANALYTICS',
    canonical_module_code = 'MODULE_11_ANALYTICS',
    feature_code = COALESCE(feature_code, 'PRICE_DYNAMICS'),
    function_key = CASE WHEN function_key = 'MODULE_14_PRICE_HISTORY' THEN 'PRICE_DYNAMICS' ELSE function_key END,
    access_scope = CASE WHEN access_scope IS NULL THEN 'GLOBAL' ELSE access_scope END,
    updated_at = now()
WHERE module_code = 'MODULE_14_PRICE_HISTORY'
   OR canonical_module_code = 'MODULE_14_PRICE_HISTORY'
   OR function_key = 'MODULE_14_PRICE_HISTORY';

UPDATE module_access AS access
SET
    status = 'LEGACY',
    updated_at = now()
FROM roles
WHERE roles.id = access.role_id
  AND roles.role_key IN (
      'SUPER_ADMIN',
      'PLATFORM_ADMIN',
      'MODERATOR',
      'KNOWLEDGE_MANAGER',
      'ESTIMATOR',
      'ENGINEER_DESIGNER',
      'SUPPLIER',
      'CONTRACTOR',
      'CUSTOMER',
      'ANALYST',
      'VIEWER'
  )
  AND access.module_number IS NOT NULL;

UPDATE module_access
SET
    status = 'LEGACY',
    updated_at = now()
WHERE status = 'ACTIVE'
  AND (
      module_number = 14
      OR module_code = 'MODULE_14_PRICE_HISTORY'
      OR canonical_module_code = 'MODULE_14_PRICE_HISTORY'
  );

COMMIT;
