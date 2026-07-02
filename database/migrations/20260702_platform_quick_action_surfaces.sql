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

UPDATE quick_action_registry_items
SET max_surface = 'MODULE_CARD',
    action_code = COALESCE(action_code, 'OPEN_DASHBOARD_CONFIGURE'),
    target_route = COALESCE(target_route, route),
    updated_at = now()
WHERE quick_action_code = 'DASHBOARD_CONFIGURE';

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

INSERT INTO quick_action_registry_items (
    quick_action_code,
    title,
    description,
    source_module_code,
    canonical_module_code,
    feature_code,
    section_code,
    widget_code,
    action_code,
    action_type,
    target_route,
    modal_code,
    required_action_code,
    required_access_level,
    required_scope,
    required_permission,
    allowed_roles,
    allowed_cabinet_types,
    route,
    status,
    is_system,
    is_enabled_by_default,
    is_available,
    max_surface,
    sort_order,
    settings
) VALUES
('MODULE3_USERS_OPEN','Добавить пользователя','Переход к пользователям. Ручное создание заменяется стандартной регистрацией.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','USERS',NULL,'OPEN_USERS','navigate','#users',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_MANAGE','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#users','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',500,'{"icon":"+","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"add-user","permissionCode":"MODULE_03_USERS_MANAGE","visibleForCompanyAdmin":true}'::json),
('MODULE3_COMPANIES_OPEN','Добавить компанию','Переход к компаниям и карточкам организаций.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','COMPANIES','USERS',NULL,'OPEN_COMPANIES','navigate','#companies',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_COMPANIES_MANAGE','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'#companies','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',510,'{"icon":"+","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"add-company","permissionCode":"MODULE_03_COMPANIES_MANAGE","visibleForCompanyAdmin":false}'::json),
('MODULE3_USERS_IMPORT','Импорт пользователей','Переход к журналу и существующим операциям импорта.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS_IMPORT','USERS',NULL,'OPEN_USER_IMPORT','navigate','#audit-log',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_IMPORT','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'#audit-log','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',520,'{"icon":"⇧","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"import-users","permissionCode":"MODULE_03_USERS_IMPORT","visibleForCompanyAdmin":false}'::json),
('MODULE3_AUDIT_OPEN','Открыть историю','Открыть историю изменений доступа.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','AUDIT_LOG','AUDIT',NULL,'OPEN_AUDIT_LOG','navigate','#audit-log',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_AUDIT_VIEW','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#audit-log','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',530,'{"icon":"◷","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"open-history","permissionCode":"MODULE_03_AUDIT_VIEW","visibleForCompanyAdmin":true}'::json),
('MODULE3_ACCESS_CONFIGURE','Настроить доступы','Переход к матрице доступа.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','ACCESS_MATRIX','ACCESS',NULL,'OPEN_ACCESS_MATRIX','navigate','#access-matrix',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_ACCESS_MANAGE','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#access-matrix','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',540,'{"icon":"◇","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"configure-access","detailTarget":"#access-matrix-detail","permissionCode":"MODULE_03_ACCESS_MANAGE","visibleForCompanyAdmin":true}'::json),
('MODULE3_ACCESS_BULK_ASSIGN','Массовое назначение доступа','Групповой переход к настройке доступов.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','ACCESS_MATRIX','ACCESS',NULL,'OPEN_BULK_ACCESS_ASSIGNMENT','navigate','#access-matrix',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_ACCESS_BULK_ASSIGN','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'#access-matrix','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',550,'{"icon":"▦","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"bulk-access-assignment","detailTarget":"#access-matrix-detail","permissionCode":"MODULE_03_ACCESS_BULK_ASSIGN","visibleForCompanyAdmin":false}'::json),
('MODULE3_USERS_EXPORT','Экспорт списка','Переход к списку пользователей для выгрузки/проверки.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','USERS',NULL,'OPEN_USERS_EXPORT','navigate','#users',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_EXPORT','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#users','ACTIVE',TRUE,TRUE,TRUE,'MODULE_BAR',560,'{"icon":"⇩","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"export-users","permissionCode":"MODULE_03_USERS_EXPORT","visibleForCompanyAdmin":true}'::json)
ON CONFLICT (quick_action_code) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    source_module_code = EXCLUDED.source_module_code,
    canonical_module_code = EXCLUDED.canonical_module_code,
    feature_code = EXCLUDED.feature_code,
    section_code = EXCLUDED.section_code,
    widget_code = EXCLUDED.widget_code,
    action_code = EXCLUDED.action_code,
    action_type = EXCLUDED.action_type,
    target_route = EXCLUDED.target_route,
    modal_code = EXCLUDED.modal_code,
    required_action_code = EXCLUDED.required_action_code,
    required_access_level = EXCLUDED.required_access_level,
    required_scope = EXCLUDED.required_scope,
    required_permission = EXCLUDED.required_permission,
    allowed_roles = EXCLUDED.allowed_roles,
    allowed_cabinet_types = EXCLUDED.allowed_cabinet_types,
    route = EXCLUDED.route,
    status = EXCLUDED.status,
    is_system = EXCLUDED.is_system,
    is_enabled_by_default = EXCLUDED.is_enabled_by_default,
    is_available = EXCLUDED.is_available,
    max_surface = EXCLUDED.max_surface,
    sort_order = EXCLUDED.sort_order,
    settings = EXCLUDED.settings,
    updated_at = now();

COMMENT ON COLUMN quick_action_registry_items.source_module_code IS
    'Owning module code. Quick actions must use moduleCode-based ownership.';
COMMENT ON COLUMN quick_action_registry_items.max_surface IS
    'Allowed rendering surface: MODULE_BAR, MODULE_CARD, or BOTH.';
COMMENT ON COLUMN quick_action_registry_items.action_code IS
    'Owning-module action code. Business execution remains inside the source module.';
