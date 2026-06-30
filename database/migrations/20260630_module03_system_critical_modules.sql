-- Module 03 / Sprint I: System-critical module protection.
-- Adds an explicit flag separate from is_system so critical platform foundations
-- cannot be disabled accidentally by ordinary administrators.

BEGIN;

ALTER TABLE platform_module_registry
    ADD COLUMN IF NOT EXISTS is_system_critical boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_platform_module_registry_is_system_critical
    ON platform_module_registry(is_system_critical);

UPDATE platform_module_registry
SET is_system_critical = true
WHERE module_code IN (
    'MODULE_03_USERS_ROLES',
    'MODULE_13_AUDIT'
);

COMMENT ON COLUMN platform_module_registry.is_system_critical
IS 'System-critical modules require SUPER_ADMIN and explicit confirmation for dangerous lifecycle changes.';

COMMIT;
