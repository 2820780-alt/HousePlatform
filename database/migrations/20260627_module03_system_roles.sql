-- Module 03 / Sprint 8. System roles.
-- Creates canonical platform roles and protects their role_key from mutation.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO roles (role_key, name, description, is_system, settings, status)
VALUES
    (
        'SUPER_ADMIN',
        'Super Admin',
        'Full platform owner role with all administrative capabilities.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'PLATFORM_ADMIN',
        'Platform Admin',
        'Platform administration without ownership-level safeguards.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8","legacyCodes":["ADMIN"]}'::json,
        'ACTIVE'
    ),
    (
        'MODERATOR',
        'Moderator',
        'Data moderation, classification review and quality control workflows.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'KNOWLEDGE_MANAGER',
        'Knowledge Manager',
        'Technology, knowledge base and reference-data curation.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8","relatedModuleCode":"MODULE_02_KNOWLEDGE_BASE"}'::json,
        'ACTIVE'
    ),
    (
        'ESTIMATOR',
        'Estimator',
        'Estimate preparation, review and estimate-related workflows.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'ENGINEER_DESIGNER',
        'Engineer Designer',
        'Engineering, design and technical validation workflows.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8","legacyCodes":["ENGINEER"]}'::json,
        'ACTIVE'
    ),
    (
        'SUPPLIER',
        'Supplier',
        'Supplier cabinet, offers, prices and source data workflows.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'CONTRACTOR',
        'Contractor',
        'Contractor cabinet, works and project execution workflows.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'CUSTOMER',
        'Customer',
        'Customer cabinet, project object and procurement visibility.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'ANALYST',
        'Analyst',
        'Analytics and reporting workflows.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    ),
    (
        'VIEWER',
        'Viewer',
        'Read-only access to explicitly allowed platform areas.',
        true,
        '{"isSystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false,"canExtendPermissions":true,"roleVersion":"module03-sprint8"}'::json,
        'ACTIVE'
    )
ON CONFLICT (role_key) DO UPDATE
SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    is_system = true,
    settings = (COALESCE(roles.settings::jsonb, '{}'::jsonb) || EXCLUDED.settings::jsonb)::json,
    status = 'ACTIVE',
    updated_at = now();

UPDATE roles
SET
    is_system = true,
    settings = (COALESCE(settings::jsonb, '{}'::jsonb) || '{"isLegacySystemRole":true,"canDelete":false,"canRenameCode":false,"canDisable":false}'::jsonb)::json,
    status = 'ACTIVE',
    updated_at = now()
WHERE role_key IN ('ADMIN', 'MANAGER', 'ENGINEER', 'DEV_ADMIN');

CREATE OR REPLACE FUNCTION prevent_system_role_mutation()
RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.role_key IN (
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
        ) THEN
            RAISE EXCEPTION 'System role % cannot be deleted', OLD.role_key;
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.role_key IN (
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
    ) THEN
        IF NEW.role_key <> OLD.role_key THEN
            RAISE EXCEPTION 'System role code % cannot be renamed', OLD.role_key;
        END IF;
        IF NEW.is_system IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'System role % cannot be converted to non-system role', OLD.role_key;
        END IF;
        IF NEW.status <> 'ACTIVE' THEN
            RAISE EXCEPTION 'System role % cannot be disabled or archived', OLD.role_key;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_system_role_mutation ON roles;
CREATE TRIGGER trg_prevent_system_role_mutation
BEFORE UPDATE OR DELETE ON roles
FOR EACH ROW
EXECUTE FUNCTION prevent_system_role_mutation();

COMMIT;
