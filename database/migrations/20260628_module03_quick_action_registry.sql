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

INSERT INTO quick_action_registry_items (
    quick_action_code,
    title,
    description,
    source_module_code,
    canonical_module_code,
    feature_code,
    widget_code,
    required_action_code,
    required_access_level,
    required_scope,
    allowed_roles,
    allowed_cabinet_types,
    route,
    status,
    is_system,
    sort_order,
    settings
) VALUES
('MATERIAL_CREATE','Добавить материал','Переход к созданию или карточке материала. Бизнес-создание проверяет Module 1.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','MATERIAL_CREATE',NULL,'CREATE','CREATE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","KNOWLEDGE_MANAGER"]'::json,'["ADMIN","KNOWLEDGE_MANAGER"]'::json,'/api/v1/admin/material-hub/view/materials','ACTIVE',TRUE,10,'{"icon":"+","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('SUPPLIER_PRICE_UPLOAD','Загрузить прайс','Безопасный переход к экрану загрузки прайса. Сам upload должен проверять CREATE/UPLOAD внутри Module 1.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','UPLOAD_SUPPLIER_FILE',NULL,'VIEW','VIEW','LIMITED','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","SUPPLIER"]'::json,'["ADMIN","SUPPLIER"]'::json,'/api/v1/admin/material-hub/view','ACTIVE',TRUE,20,'{"icon":"⇧","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('SOURCE_TASK_CREATE','Запустить анализ источника','Переход к задачам анализа источников. Запуск задачи проверяется в Module 1.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','SOURCE_TASK_CREATE',NULL,'CREATE','CREATE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'/api/v1/admin/material-hub/view','ACTIVE',TRUE,30,'{"icon":"▶","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('MATERIAL_MODERATION_OPEN','Открыть модерацию','Переход к очереди модерации материалов.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','MODERATION',NULL,'APPROVE','APPROVE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'/api/v1/admin/material-hub/view/moderation','ACTIVE',TRUE,40,'{"icon":"!","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('SOURCE_ERRORS_OPEN','Проверить ошибки сбора','Переход к ошибкам и задачам сбора источников.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','SOURCE_TASK_ERRORS',NULL,'VIEW','VIEW','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR","ANALYST"]'::json,'["ADMIN","MODERATOR","ANALYST"]'::json,'/api/v1/admin/material-hub/view/tasks','ACTIVE',TRUE,50,'{"icon":"×","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('SOURCE_CREATE','Добавить источник','Переход к источникам. Создание источника остается операцией Module 1.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','SOURCE_CREATE',NULL,'CREATE','CREATE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN"]'::json,'["ADMIN"]'::json,'/api/v1/admin/material-hub/view/sources','ACTIVE',TRUE,60,'{"icon":"+","mock":true,"payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('DOCUMENT_LIST_OPEN','Открыть документы','Переход к документам Material Hub.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','DOCUMENTS',NULL,'VIEW','VIEW','LIMITED','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","KNOWLEDGE_MANAGER","ENGINEER_DESIGNER","ANALYST"]'::json,'["ADMIN","KNOWLEDGE_MANAGER","ENGINEER_DESIGNER","ANALYST"]'::json,'/api/v1/admin/material-hub/view/documents','ACTIVE',TRUE,70,'{"icon":"□","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('MATERIAL_APPROVE','Подтвердить материал','Модераторский переход к подтверждению материалов.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','MODERATION',NULL,'APPROVE','APPROVE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'/api/v1/admin/material-hub/view/moderation','ACTIVE',TRUE,80,'{"icon":"✓","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('MATERIAL_CLASSIFICATION_FIX','Исправить классификацию','Переход к ручной классификации материалов.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','CLASSIFICATION',NULL,'APPROVE','APPROVE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'/api/v1/admin/material-hub/view/moderation','ACTIVE',TRUE,90,'{"icon":"↻","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('MATERIAL_RECHECK_SEND','Отправить на повторную проверку','Переход к повторной проверке материалов.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','MODERATION',NULL,'APPROVE','APPROVE','GLOBAL','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR"]'::json,'["ADMIN","MODERATOR"]'::json,'/api/v1/admin/material-hub/view/moderation','ACTIVE',TRUE,100,'{"icon":"↺","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('SUPPLIER_PRICE_UPDATE','Обновить цену','Будущая операция поставщика. Пока только planned metadata.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB','SUPPLIER_PRICE_UPDATE',NULL,'VIEW','VIEW','LIMITED','["SUPPLIER"]'::json,'["SUPPLIER"]'::json,'/api/v1/admin/material-hub/view','PLANNED',TRUE,110,'{"icon":"↗","payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('SUPPLIER_OFFER_CREATE','Предложить товар','Будущая операция витрины/поставщика. Не активна в MVP.','MODULE_10_MARKETPLACE','MODULE_10_MARKETPLACE','SUPPLIER_OFFER',NULL,'CREATE','CREATE','OWN','["SUPPLIER"]'::json,'["SUPPLIER"]'::json,'/modules/marketplace','PLANNED',TRUE,120,'{"icon":"+","payloadOwner":"MODULE_10_MARKETPLACE","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('CUSTOMER_OBJECT_CREATE','Создать объект','Будущая операция Module 7. Не активна до готовности Digital House.','MODULE_07_DIGITAL_HOUSE','MODULE_07_DIGITAL_HOUSE','HOUSE_PROFILE',NULL,'CREATE','CREATE','OWN','["CUSTOMER"]'::json,'["CUSTOMER"]'::json,'/modules/digital-house','PLANNED',TRUE,130,'{"icon":"+","payloadOwner":"MODULE_07_DIGITAL_HOUSE","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('CUSTOMER_ESTIMATE_REQUEST','Получить смету','Будущая операция Module 5. Не активна до готовности Estimate Engine.','MODULE_05_ESTIMATE_ENGINE','MODULE_05_ESTIMATE_ENGINE','ESTIMATE_REQUEST',NULL,'CREATE','CREATE','OWN','["CUSTOMER"]'::json,'["CUSTOMER"]'::json,'/modules/estimates','PLANNED',TRUE,140,'{"icon":"₽","payloadOwner":"MODULE_05_ESTIMATE_ENGINE","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('CUSTOMER_PROCUREMENT_REQUEST','Отправить заявку','Будущая операция Module 9. Не активна до готовности Procurement.','MODULE_09_PROCUREMENT','MODULE_09_PROCUREMENT','PROCUREMENT_REQUEST',NULL,'CREATE','CREATE','OWN','["CUSTOMER"]'::json,'["CUSTOMER"]'::json,'/modules/procurement','PLANNED',TRUE,150,'{"icon":"→","payloadOwner":"MODULE_09_PROCUREMENT","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json),
('DASHBOARD_CONFIGURE','Настроить Dashboard','Переход к настройке существующего Dashboard.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES','DASHBOARD_PERSONALIZE',NULL,'VIEW','VIEW','LIMITED','["SUPER_ADMIN","PLATFORM_ADMIN","ADMIN","MODERATOR","KNOWLEDGE_MANAGER","ESTIMATOR","ENGINEER_DESIGNER","SUPPLIER","CONTRACTOR","CUSTOMER","ANALYST"]'::json,'["ADMIN","MODERATOR","KNOWLEDGE_MANAGER","ESTIMATOR","ENGINEER_DESIGNER","SUPPLIER","CONTRACTOR","CUSTOMER","ANALYST"]'::json,'#dashboard-config','ACTIVE',TRUE,900,'{"icon":"⚙","contextCode":"DASHBOARD_ADMIN_CONTEXT","payloadOwner":"DASHBOARD_ADMIN_CONTEXT","registryLayer":"MODULE_03_QUICK_ACTION_REGISTRY"}'::json)
ON CONFLICT (quick_action_code) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    source_module_code = EXCLUDED.source_module_code,
    canonical_module_code = EXCLUDED.canonical_module_code,
    feature_code = EXCLUDED.feature_code,
    widget_code = EXCLUDED.widget_code,
    required_action_code = EXCLUDED.required_action_code,
    required_access_level = EXCLUDED.required_access_level,
    required_scope = EXCLUDED.required_scope,
    allowed_roles = EXCLUDED.allowed_roles,
    allowed_cabinet_types = EXCLUDED.allowed_cabinet_types,
    route = EXCLUDED.route,
    status = EXCLUDED.status,
    is_system = EXCLUDED.is_system,
    sort_order = EXCLUDED.sort_order,
    settings = EXCLUDED.settings,
    updated_at = now();

UPDATE role_dashboard_access_profiles
SET default_quick_action_codes = '["MATERIAL_MODERATION_OPEN","MATERIAL_APPROVE","MATERIAL_CLASSIFICATION_FIX","MATERIAL_RECHECK_SEND","SOURCE_ERRORS_OPEN","DASHBOARD_CONFIGURE"]'::json,
    updated_at = now()
WHERE role_code = 'MODERATOR';
