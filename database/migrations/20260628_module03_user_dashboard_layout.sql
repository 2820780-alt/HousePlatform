-- Module 03 / Sprint 21: UserDashboardLayout
-- Personal layout for the existing Dashboard. No business payload and no moduleNumber logic.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_dashboard_layouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    workspace_id UUID REFERENCES workspaces(id),
    active_region_code VARCHAR(80),
    active_cabinet_id VARCHAR(120),
    cabinet_type VARCHAR(80),
    favorite_modules JSON NOT NULL DEFAULT '[]'::json,
    widgets JSON NOT NULL DEFAULT '[]'::json,
    layout_settings JSON,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);

ALTER TABLE user_dashboard_layouts
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN favorite_modules SET DEFAULT '[]'::json,
    ALTER COLUMN widgets SET DEFAULT '[]'::json,
    ALTER COLUMN is_default SET DEFAULT FALSE,
    ALTER COLUMN status SET DEFAULT 'ACTIVE',
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_user_id
    ON user_dashboard_layouts(user_id);
CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_workspace_id
    ON user_dashboard_layouts(workspace_id);
CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_active_region_code
    ON user_dashboard_layouts(active_region_code);
CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_active_cabinet_id
    ON user_dashboard_layouts(active_cabinet_id);
CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_cabinet_type
    ON user_dashboard_layouts(cabinet_type);
CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_is_default
    ON user_dashboard_layouts(is_default);
CREATE INDEX IF NOT EXISTS ix_user_dashboard_layouts_status
    ON user_dashboard_layouts(status);

CREATE UNIQUE INDEX IF NOT EXISTS ux_user_dashboard_layouts_default_context
    ON user_dashboard_layouts(
        user_id,
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(active_region_code, ''),
        COALESCE(active_cabinet_id, '')
    )
    WHERE is_default = TRUE AND status = 'ACTIVE';
