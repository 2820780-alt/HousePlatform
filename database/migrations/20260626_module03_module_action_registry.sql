-- Module 03 / Sprint 6. ModuleActionRegistry
-- Allows each module to declare actions without changing RBAC core code.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS module_action_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_code varchar(120) NOT NULL,
    action_code varchar(80) NOT NULL,
    title varchar(255) NOT NULL,
    description text,
    is_system boolean NOT NULL DEFAULT true,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ux_module_action_registry_module_action UNIQUE (module_code, action_code)
);

CREATE INDEX IF NOT EXISTS ix_module_action_registry_module_code
    ON module_action_registry(module_code);
CREATE INDEX IF NOT EXISTS ix_module_action_registry_action_code
    ON module_action_registry(action_code);
CREATE INDEX IF NOT EXISTS ix_module_action_registry_is_system
    ON module_action_registry(is_system);
CREATE INDEX IF NOT EXISTS ix_module_action_registry_is_active
    ON module_action_registry(is_active);

ALTER TABLE module_action_registry ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE module_action_registry ALTER COLUMN is_system SET DEFAULT true;
ALTER TABLE module_action_registry ALTER COLUMN is_active SET DEFAULT true;
ALTER TABLE module_action_registry ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE module_action_registry ALTER COLUMN updated_at SET DEFAULT now();

INSERT INTO module_action_registry (
    module_code,
    action_code,
    title,
    description,
    is_system,
    is_active
)
SELECT
    modules.module_code,
    actions.action_code,
    actions.title,
    actions.description,
    true,
    true
FROM platform_module_registry AS modules
CROSS JOIN (
    VALUES
        ('VIEW', 'View', 'Read module data.'),
        ('CREATE', 'Create', 'Create module records.'),
        ('EDIT', 'Edit', 'Update module records.'),
        ('APPROVE', 'Approve', 'Approve or moderate module records.'),
        ('ADMIN', 'Admin', 'Manage module settings and access.')
) AS actions(action_code, title, description)
WHERE modules.is_system = true
  AND modules.status = 'ACTIVE'
ON CONFLICT (module_code, action_code) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    is_system = EXCLUDED.is_system,
    is_active = EXCLUDED.is_active,
    updated_at = now();

COMMIT;
