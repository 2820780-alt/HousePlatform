-- User-owned module quick actions.
-- A quick action is a personal shortcut to an owning-module action.
-- It is not WidgetRegistry, RBAC, Dashboard business logic, or Module 08 source of truth.

CREATE TABLE IF NOT EXISTS user_module_quick_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    workspace_id UUID NULL REFERENCES workspaces(id),
    active_region_code VARCHAR(80),

    source_module_code VARCHAR(120) NOT NULL,
    feature_code VARCHAR(120),
    action_key VARCHAR(160) NOT NULL,

    title VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(80),

    route VARCHAR(500),
    deep_link VARCHAR(500),

    saved_config_ref VARCHAR(255),
    config_snapshot JSON,

    sort_order INTEGER NOT NULL DEFAULT 1000,
    is_visible_in_module_bar BOOLEAN NOT NULL DEFAULT TRUE,

    is_pinned_to_atom_card BOOLEAN NOT NULL DEFAULT FALSE,
    atom_card_order INTEGER,
    atom_card_accent VARCHAR(20),

    status VARCHAR(40) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),

    CONSTRAINT ck_user_module_quick_action_status CHECK (
        status IN ('ACTIVE', 'DISABLED', 'BROKEN_CONFIG', 'MODULE_DISABLED', 'NO_LONGER_AVAILABLE')
    ),
    CONSTRAINT ck_user_module_quick_action_atom_accent CHECK (
        atom_card_accent IS NULL
        OR atom_card_accent IN ('blue', 'cyan', 'green', 'orange', 'red', 'purple')
    )
);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_user_module
    ON user_module_quick_actions(user_id, source_module_code);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_workspace
    ON user_module_quick_actions(workspace_id);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_region
    ON user_module_quick_actions(active_region_code);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_action_key
    ON user_module_quick_actions(action_key);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_saved_config
    ON user_module_quick_actions(saved_config_ref);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_module_bar
    ON user_module_quick_actions(user_id, source_module_code, is_visible_in_module_bar, sort_order);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_atom_card
    ON user_module_quick_actions(user_id, source_module_code, is_pinned_to_atom_card, atom_card_order);

CREATE INDEX IF NOT EXISTS ix_user_module_quick_actions_status
    ON user_module_quick_actions(status);

COMMENT ON TABLE user_module_quick_actions IS
    'Personal user shortcuts to actions owned and executed by source modules. Stores config refs/snapshots, not business result payload.';

COMMENT ON COLUMN user_module_quick_actions.source_module_code IS
    'Owning module code. Required. Module owner validates and executes the action.';

COMMENT ON COLUMN user_module_quick_actions.action_key IS
    'Owning-module action key. Required. Not a global RBAC permission by itself.';

COMMENT ON COLUMN user_module_quick_actions.saved_config_ref IS
    'Optional reference to owning-module saved configuration. Does not store action result.';

COMMENT ON COLUMN user_module_quick_actions.config_snapshot IS
    'Optional safe configuration snapshot. Must not contain raw/business result payload or чужие данные.';

