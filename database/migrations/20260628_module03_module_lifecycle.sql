-- Module 03 / Sprint 24: Module Lifecycle
-- Safe lifecycle statuses for PlatformModuleRegistry. This does not physically delete modules.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_platform_module_registry_lifecycle_status'
    ) THEN
        ALTER TABLE platform_module_registry
            ADD CONSTRAINT ck_platform_module_registry_lifecycle_status
            CHECK (status IN ('PLANNED','DRAFT','ACTIVE','DISABLED','DEPRECATED','ARCHIVED','MERGED'));
    END IF;
END $$;

UPDATE platform_module_registry
SET
    is_active = CASE WHEN status = 'ACTIVE' THEN is_active ELSE FALSE END,
    is_visible_in_sidebar = CASE WHEN status = 'ACTIVE' THEN is_visible_in_sidebar ELSE FALSE END,
    is_visible_on_dashboard = CASE WHEN status = 'ACTIVE' THEN is_visible_on_dashboard ELSE FALSE END,
    is_visible_on_atom_map = CASE WHEN status = 'ACTIVE' THEN is_visible_on_atom_map ELSE FALSE END,
    is_available_for_widgets = CASE WHEN status = 'ACTIVE' THEN is_available_for_widgets ELSE FALSE END,
    updated_at = now()
WHERE status IN ('PLANNED','DRAFT','DISABLED','DEPRECATED','ARCHIVED','MERGED');

UPDATE platform_module_registry
SET
    is_active = TRUE,
    is_public = TRUE,
    is_visible_in_sidebar = COALESCE(is_visible_in_sidebar, TRUE),
    is_visible_on_dashboard = COALESCE(is_visible_on_dashboard, TRUE),
    is_visible_on_atom_map = COALESCE(is_visible_on_atom_map, TRUE),
    is_available_for_widgets = COALESCE(is_available_for_widgets, TRUE),
    updated_at = now()
WHERE status = 'ACTIVE' AND is_active IS NOT TRUE;

COMMENT ON CONSTRAINT ck_platform_module_registry_lifecycle_status
ON platform_module_registry
IS 'Module lifecycle statuses: PLANNED, DRAFT, ACTIVE, DISABLED, DEPRECATED, ARCHIVED, MERGED. Non-active statuses are hidden from user-facing module visibility.';
