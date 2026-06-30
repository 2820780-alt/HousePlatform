-- Sprint 11: extend user quick action states for safe stale-action handling.
-- LOADING and ERROR are UI/service states; they do not execute module business logic.

ALTER TABLE user_module_quick_actions
    DROP CONSTRAINT IF EXISTS ck_user_module_quick_action_status;

ALTER TABLE user_module_quick_actions
    ADD CONSTRAINT ck_user_module_quick_action_status CHECK (
        status IN (
            'ACTIVE',
            'DISABLED',
            'BROKEN_CONFIG',
            'MODULE_DISABLED',
            'NO_LONGER_AVAILABLE',
            'LOADING',
            'ERROR'
        )
    );

COMMENT ON COLUMN user_module_quick_actions.status IS
    'User quick action state. LOADING/ERROR are non-executable safety states for stale or changing module actions.';
