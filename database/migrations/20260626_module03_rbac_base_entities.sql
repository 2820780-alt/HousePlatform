-- Module 03 / Sprint 7. RBAC base entities upgrade
-- Extends permissions with moduleCode/actionCode/accessLevel/accessScope and adds workspace_roles.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE permissions ADD COLUMN IF NOT EXISTS module_code varchar(120);
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS action_code varchar(80);
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS access_level varchar(30) NOT NULL DEFAULT 'VIEW';
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS access_scope varchar(30) NOT NULL DEFAULT 'GLOBAL';
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS conditions jsonb;
ALTER TABLE permissions ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS ix_permissions_module_code ON permissions(module_code);
CREATE INDEX IF NOT EXISTS ix_permissions_action_code ON permissions(action_code);
CREATE INDEX IF NOT EXISTS ix_permissions_access_level ON permissions(access_level);
CREATE INDEX IF NOT EXISTS ix_permissions_access_scope ON permissions(access_scope);
CREATE INDEX IF NOT EXISTS ix_permissions_is_active ON permissions(is_active);
CREATE INDEX IF NOT EXISTS ix_permissions_conditions ON permissions USING gin (conditions);

ALTER TABLE permissions ALTER COLUMN access_level SET DEFAULT 'VIEW';
ALTER TABLE permissions ALTER COLUMN access_scope SET DEFAULT 'GLOBAL';
ALTER TABLE permissions ALTER COLUMN is_active SET DEFAULT true;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_permissions_module_code_registry'
    ) THEN
        ALTER TABLE permissions
            ADD CONSTRAINT fk_permissions_module_code_registry
            FOREIGN KEY (module_code)
            REFERENCES platform_module_registry(module_code)
            NOT VALID;
    END IF;
END $$;

UPDATE permissions AS p
SET module_code = pmr.module_code
FROM platform_module_registry AS pmr
WHERE p.module_code IS NULL
  AND p.module_number IS NOT NULL
  AND (
      pmr.legacy_number = p.module_number
      OR pmr.display_number = p.module_number
      OR pmr.visual_number = p.module_number
  )
  AND pmr.status <> 'PLANNED';

UPDATE permissions
SET action_code = CASE
        WHEN permission_key LIKE 'VIEW_%' THEN 'VIEW'
        WHEN permission_key LIKE 'CREATE_%' THEN 'CREATE'
        WHEN permission_key LIKE 'EDIT_%' THEN 'EDIT'
        WHEN permission_key LIKE 'APPROVE_%' THEN 'APPROVE'
        WHEN permission_key LIKE 'MANAGE_%' THEN 'ADMIN'
        WHEN permission_key LIKE 'DELETE_%' THEN 'ADMIN'
        ELSE access_level
    END
WHERE action_code IS NULL;

UPDATE permissions
SET access_level = CASE
        WHEN action_code IN ('NO_ACCESS', 'VIEW', 'CREATE', 'EDIT', 'APPROVE', 'ADMIN') THEN action_code
        ELSE access_level
    END
WHERE access_level IS NULL OR access_level = 'VIEW';

UPDATE permissions
SET access_scope = 'GLOBAL'
WHERE access_scope IS NULL;

UPDATE permissions
SET is_active = (status = 'ACTIVE')
WHERE is_active IS NULL;

CREATE TABLE IF NOT EXISTS workspace_roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ux_workspace_roles_workspace_role UNIQUE (workspace_id, role_id)
);

CREATE INDEX IF NOT EXISTS ix_workspace_roles_workspace_id ON workspace_roles(workspace_id);
CREATE INDEX IF NOT EXISTS ix_workspace_roles_role_id ON workspace_roles(role_id);
CREATE INDEX IF NOT EXISTS ix_workspace_roles_status ON workspace_roles(status);

ALTER TABLE workspace_roles ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE workspace_roles ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE workspace_roles ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE workspace_roles ALTER COLUMN updated_at SET DEFAULT now();

INSERT INTO workspace_roles (workspace_id, role_id, status)
SELECT DISTINCT ura.workspace_id, ura.role_id, 'ACTIVE'
FROM user_role_assignments AS ura
WHERE ura.workspace_id IS NOT NULL
  AND ura.status = 'ACTIVE'
ON CONFLICT (workspace_id, role_id) DO NOTHING;

COMMIT;
