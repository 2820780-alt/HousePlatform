-- Module 03 / Sprint 13. Workspace context fields.
-- Extends existing workspaces/workspace_members without removing legacy names.

BEGIN;

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS owner_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS organization_id varchar(120),
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS ix_workspaces_owner_user_id
    ON workspaces(owner_user_id);
CREATE INDEX IF NOT EXISTS ix_workspaces_organization_id
    ON workspaces(organization_id);
CREATE INDEX IF NOT EXISTS ix_workspaces_is_active
    ON workspaces(is_active);

ALTER TABLE workspaces ALTER COLUMN workspace_type SET DEFAULT 'INTERNAL';
UPDATE workspaces
SET workspace_type = 'INTERNAL',
    updated_at = now()
WHERE workspace_type = 'ADMIN';

UPDATE workspaces
SET is_active = (status = 'ACTIVE')
WHERE is_active IS DISTINCT FROM (status = 'ACTIVE');

ALTER TABLE workspace_members
    ADD COLUMN IF NOT EXISTS role_code varchar(80);

CREATE INDEX IF NOT EXISTS ix_workspace_members_role_code
    ON workspace_members(role_code);

UPDATE workspace_members
SET role_code = role_key,
    updated_at = now()
WHERE role_code IS NULL
  AND role_key IS NOT NULL;

ALTER TABLE workspace_members ALTER COLUMN status SET DEFAULT 'ACTIVE';

COMMIT;
