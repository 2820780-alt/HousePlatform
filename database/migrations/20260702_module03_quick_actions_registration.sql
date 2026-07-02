-- Sprint 11: Module 03 quick actions registration through PlatformQuickAction.
-- These actions are owned by MODULE_03_USERS_ROLES and rendered by Dashboard /
-- Module Shell surfaces from QuickActionRegistry. They do not create users
-- manually and do not reintroduce a separate Quick Actions menu section.

UPDATE quick_action_registry_items
SET status = 'DISABLED',
    is_available = FALSE,
    settings = (
        COALESCE(settings, '{}'::json)::jsonb
        || '{"disabledReason":"Replaced by Sprint 11 Module 03 platform quick actions."}'::jsonb
    )::json,
    updated_at = now()
WHERE quick_action_code IN (
    'MODULE3_USERS_OPEN',
    'MODULE3_COMPANIES_OPEN',
    'MODULE3_USERS_IMPORT',
    'MODULE3_AUDIT_OPEN',
    'MODULE3_ACCESS_CONFIGURE',
    'MODULE3_ACCESS_BULK_ASSIGN',
    'MODULE3_USERS_EXPORT'
);

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
('MODULE_03_FIND_USER','Найти пользователя','Открыть поиск по пользователям, компаниям и контактам.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','USERS_TABLE',NULL,'FIND_USER','navigate','#users?focus=search',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#users?focus=search','ACTIVE',TRUE,TRUE,TRUE,'BOTH',500,'{"icon":"⌕","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"find-user","permissionCode":"MODULE_03_USERS_READ","visibleForCompanyAdmin":true}'::json),
('MODULE_03_BLOCKED_USERS','Открыть заблокированных','Показать пользователей со статусом блокировки.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','USERS_TABLE',NULL,'OPEN_BLOCKED_USERS','navigate','#users?blocked=true',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#users?blocked=true','ACTIVE',TRUE,TRUE,TRUE,'BOTH',510,'{"icon":"⊘","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"blocked-users","permissionCode":"MODULE_03_USERS_READ","visibleForCompanyAdmin":true}'::json),
('MODULE_03_CHECK_ACCESS','Проверить доступ','Проверить итоговый доступ пользователя к модулям и виджетам.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','ACCESS','ACCESS_MATRIX',NULL,'CHECK_EFFECTIVE_ACCESS','navigate','#access-matrix?mode=check',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_ACCESS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#access-matrix?mode=check','ACTIVE',TRUE,TRUE,TRUE,'BOTH',520,'{"icon":"◇","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"check-access","detailTarget":"#access-matrix-detail","permissionCode":"MODULE_03_ACCESS_READ","visibleForCompanyAdmin":true}'::json),
('MODULE_03_AUDIT_LOG','История изменений','Открыть журнал изменений пользователей, доступов и блокировок.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','AUDIT','AUDIT_LOG',NULL,'OPEN_AUDIT_LOG','navigate','#audit-log',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_AUDIT_VIEW','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#audit-log','ACTIVE',TRUE,TRUE,TRUE,'BOTH',530,'{"icon":"◷","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"audit-log","permissionCode":"MODULE_03_AUDIT_VIEW","visibleForCompanyAdmin":true}'::json),
('MODULE_03_USERS_WITHOUT_COMPANY','Пользователи без компании','Открыть таблицу пользователей без привязки к компании.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','USERS_TABLE',NULL,'OPEN_USERS_WITHOUT_COMPANY','navigate','#users?companyId=null',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'#users?companyId=null','ACTIVE',TRUE,TRUE,TRUE,'BOTH',540,'{"icon":"○","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"users-without-company","permissionCode":"MODULE_03_USERS_READ","visibleForCompanyAdmin":false}'::json),
('MODULE_03_USERS_WITHOUT_TYPE','Пользователи без типа','Открыть таблицу пользователей без назначенного типа.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','USERS_TABLE',NULL,'OPEN_USERS_WITHOUT_TYPE','navigate','#users?userType=null',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'#users?userType=null','ACTIVE',TRUE,TRUE,TRUE,'BOTH',550,'{"icon":"?","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"users-without-type","permissionCode":"MODULE_03_USERS_READ","visibleForCompanyAdmin":false}'::json),
('MODULE_03_SYSTEM_USERS','Системные пользователи','Открыть блок системных пользователей Module №3.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS','SYSTEM_USERS',NULL,'OPEN_SYSTEM_USERS','navigate','#system-users',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#system-users','ACTIVE',TRUE,TRUE,TRUE,'BOTH',560,'{"icon":"♙","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"system-users","permissionCode":"MODULE_03_USERS_READ","visibleForCompanyAdmin":false}'::json),
('MODULE_03_ACCESS_MATRIX','Матрица доступов','Открыть вкладку «Доступы» и матрицу модулей и виджетов.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','ACCESS','ACCESS_MATRIX',NULL,'OPEN_ACCESS_MATRIX','navigate','#access-matrix',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_ACCESS_READ','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#access-matrix','ACTIVE',TRUE,TRUE,TRUE,'BOTH',570,'{"icon":"▦","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"access-matrix","detailTarget":"#access-matrix-detail","permissionCode":"MODULE_03_ACCESS_READ","visibleForCompanyAdmin":true}'::json),
('MODULE_03_EXPORT_USERS','Экспортировать список пользователей','Экспорт будет доступен после подключения сервиса экспорта.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','USERS_EXPORT','USERS_TABLE',NULL,'EXPORT_USERS','navigate','#users?export=1',NULL,'VIEW','VIEW','GLOBAL','MODULE_03_USERS_EXPORT','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'#users?export=1','ACTIVE',TRUE,TRUE,FALSE,'BOTH',580,'{"icon":"⇩","payloadOwner":"MODULE_03_USERS_ROLES","shellActionId":"export-users","permissionCode":"MODULE_03_USERS_EXPORT","disabledReason":"Экспорт будет доступен после подключения сервиса экспорта.","visibleForCompanyAdmin":true}'::json)
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
