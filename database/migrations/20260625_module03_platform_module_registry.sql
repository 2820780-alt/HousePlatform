-- Module 03 / Sprint 1. PlatformModuleRegistry
-- Adds an expandable module registry without replacing legacy module_number references yet.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS platform_module_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_code varchar(120) NOT NULL UNIQUE,
    canonical_module_code varchar(120),
    title varchar(255) NOT NULL,
    short_title varchar(120),
    description text,
    version varchar(50),
    legacy_number integer,
    display_number integer,
    visual_number integer,
    display_order integer NOT NULL DEFAULT 100,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    route varchar(255),
    redirect_route varchar(255),
    icon varchar(80),
    color varchar(50),
    is_system boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT false,
    is_public boolean NOT NULL DEFAULT false,
    is_visible_in_sidebar boolean NOT NULL DEFAULT false,
    is_visible_on_dashboard boolean NOT NULL DEFAULT false,
    is_visible_on_atom_map boolean NOT NULL DEFAULT false,
    is_available_for_widgets boolean NOT NULL DEFAULT false,
    parent_module_code varchar(120),
    owner_module_code varchar(120),
    merged_into_module_code varchar(120),
    legacy_codes jsonb,
    feature_codes jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_platform_module_registry_module_code
    ON platform_module_registry(module_code);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_canonical_module_code
    ON platform_module_registry(canonical_module_code);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_legacy_number
    ON platform_module_registry(legacy_number);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_display_number
    ON platform_module_registry(display_number);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_visual_number
    ON platform_module_registry(visual_number);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_display_order
    ON platform_module_registry(display_order);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_status
    ON platform_module_registry(status);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_is_system
    ON platform_module_registry(is_system);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_is_active
    ON platform_module_registry(is_active);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_is_public
    ON platform_module_registry(is_public);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_parent_module_code
    ON platform_module_registry(parent_module_code);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_owner_module_code
    ON platform_module_registry(owner_module_code);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_merged_into_module_code
    ON platform_module_registry(merged_into_module_code);

ALTER TABLE platform_module_registry
    ALTER COLUMN legacy_codes TYPE jsonb USING legacy_codes::jsonb;
ALTER TABLE platform_module_registry
    ALTER COLUMN feature_codes TYPE jsonb USING feature_codes::jsonb;

CREATE INDEX IF NOT EXISTS ix_platform_module_registry_legacy_codes
    ON platform_module_registry USING gin (legacy_codes);
CREATE INDEX IF NOT EXISTS ix_platform_module_registry_feature_codes
    ON platform_module_registry USING gin (feature_codes);

ALTER TABLE platform_module_registry ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE platform_module_registry ALTER COLUMN display_order SET DEFAULT 100;
ALTER TABLE platform_module_registry ALTER COLUMN status SET DEFAULT 'DRAFT';
ALTER TABLE platform_module_registry ALTER COLUMN is_system SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN is_active SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN is_public SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN is_visible_in_sidebar SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN is_visible_on_dashboard SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN is_visible_on_atom_map SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN is_available_for_widgets SET DEFAULT false;
ALTER TABLE platform_module_registry ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE platform_module_registry ALTER COLUMN updated_at SET DEFAULT now();

COMMIT;
