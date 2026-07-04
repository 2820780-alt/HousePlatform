-- Sprint 10: universal platform quick action surfaces.
-- Extends QuickActionRegistry without turning Dashboard or Module 03 shell
-- into owners of business operations.

ALTER TABLE quick_action_registry_items
    ADD COLUMN IF NOT EXISTS section_code VARCHAR(120),
    ADD COLUMN IF NOT EXISTS action_code VARCHAR(160),
    ADD COLUMN IF NOT EXISTS action_type VARCHAR(40) NOT NULL DEFAULT 'navigate',
    ADD COLUMN IF NOT EXISTS target_route VARCHAR(255),
    ADD COLUMN IF NOT EXISTS modal_code VARCHAR(120),
    ADD COLUMN IF NOT EXISTS required_permission VARCHAR(160),
    ADD COLUMN IF NOT EXISTS is_enabled_by_default BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS max_surface VARCHAR(40) NOT NULL DEFAULT 'BOTH';

UPDATE quick_action_registry_items
SET action_code = COALESCE(action_code, quick_action_code),
    target_route = COALESCE(target_route, route),
    is_available = status = 'ACTIVE'
WHERE action_code IS NULL
   OR target_route IS NULL;


ALTER TABLE quick_action_registry_items
    ALTER COLUMN action_code SET NOT NULL;

ALTER TABLE quick_action_registry_items
    DROP CONSTRAINT IF EXISTS ck_quick_action_registry_action_type,
    DROP CONSTRAINT IF EXISTS ck_quick_action_registry_max_surface;

ALTER TABLE quick_action_registry_items
    ADD CONSTRAINT ck_quick_action_registry_action_type CHECK (
        action_type IN ('navigate', 'modal', 'callback')
    ),
    ADD CONSTRAINT ck_quick_action_registry_max_surface CHECK (
        max_surface IN ('MODULE_BAR', 'MODULE_CARD', 'BOTH')
    );

CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_section
    ON quick_action_registry_items(section_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_action_code
    ON quick_action_registry_items(action_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_action_type
    ON quick_action_registry_items(action_type);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_modal
    ON quick_action_registry_items(modal_code);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_required_permission
    ON quick_action_registry_items(required_permission);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_default_enabled
    ON quick_action_registry_items(is_enabled_by_default);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_available
    ON quick_action_registry_items(is_available);
CREATE INDEX IF NOT EXISTS ix_quick_action_registry_items_surface
    ON quick_action_registry_items(max_surface);

COMMENT ON COLUMN quick_action_registry_items.source_module_code IS
    'Owning module code. Quick actions must use moduleCode-based ownership.';
COMMENT ON COLUMN quick_action_registry_items.max_surface IS
    'Allowed rendering surface: MODULE_BAR, MODULE_CARD, or BOTH.';
COMMENT ON COLUMN quick_action_registry_items.action_code IS
    'Owning-module action code. Business execution remains inside the source module.';
