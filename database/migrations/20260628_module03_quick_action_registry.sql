-- Module 03 / Sprint 22: QuickActionRegistry
-- Metadata and permission registry for Dashboard quick actions.
-- Owning modules still execute business operations and must call requirePermission().

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS quick_action_registry_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quick_action_code VARCHAR(160) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    source_module_code VARCHAR(120) NOT NULL,
    canonical_module_code VARCHAR(120),
    feature_code VARCHAR(120),
    widget_code VARCHAR(160),
    required_action_code VARCHAR(120) NOT NULL,
    required_access_level VARCHAR(40) NOT NULL,
    required_scope VARCHAR(40) NOT NULL,
    allowed_roles JSON NOT NULL DEFAULT '[]'::json,
    allowed_cabinet_types JSON NOT NULL DEFAULT '[]'::json,
    route VARCHAR(255),
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 1000,
    settings JSON,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT ck_quick_action_registry_item_status CHECK (
        status IN ('ACTIVE','DRAFT','PLANNED','DISABLED')
    ),
    CONSTRAINT ck_quick_action_registry_access_level CHECK (
        required_access_level IN ('NO_ACCESS','VIEW','CREATE','EDIT','APPROVE','ADMIN')
    ),
    CONSTRAINT ck_quick_action_registry_scope CHECK (
        required_scope IN ('NONE','GLOBAL','OWN','RELEVANT','LIMITED')
    )
);

ALTER TABLE quick_action_registry_items
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN allowed_roles SET DEFAULT '[]'::json,
    ALTER COLUMN allowed_cabinet_types SET DEFAULT '[]'::json,
    ALTER COLUMN status SET DEFAULT 'ACTIVE',
    ALTER COLUMN is_system SET DEFAULT TRUE,
    ALTER COLUMN sort_order SET DEFAULT 1000,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_code
    ON quick_action_registry_items(quick_action_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_source_module
    ON quick_action_registry_items(source_module_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_canonical_module
    ON quick_action_registry_items(canonical_module_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_feature
    ON quick_action_registry_items(feature_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_widget
    ON quick_action_registry_items(widget_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_required_action
    ON quick_action_registry_items(required_action_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_status
    ON quick_action_registry_items(status);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_sort_order
    ON quick_action_registry_items(sort_order);

-- Fixed quick action seeds were removed: user shortcuts are saved in user_module_quick_actions.
