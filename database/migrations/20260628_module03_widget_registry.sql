-- Module 03 / Sprint 19: WidgetRegistry
-- Code-first widget metadata registry. It is not Dashboard UI and does not store business payload.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS widget_registry_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    widget_code VARCHAR(160) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    source_module_code VARCHAR(120) NOT NULL,
    canonical_module_code VARCHAR(120),
    feature_code VARCHAR(120),
    legacy_module_code VARCHAR(120),
    widget_type VARCHAR(50) NOT NULL,
    data_source VARCHAR(160),
    required_access_level VARCHAR(40),
    required_scope VARCHAR(40),
    required_action_code VARCHAR(120),
    allowed_roles JSON NOT NULL DEFAULT '[]'::json,
    allowed_cabinet_types JSON NOT NULL DEFAULT '[]'::json,
    default_size VARCHAR(30) NOT NULL DEFAULT 'medium',
    allowed_sizes JSON NOT NULL DEFAULT '["small","medium","large"]'::json,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    is_mock BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 1000,
    settings JSON,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now(),
    CONSTRAINT ck_widget_registry_item_type CHECK (
        widget_type IN ('KPI','CHART','LIST','STATUS','TASK_QUEUE','ALERTS','ACTIONS','ATOM_MAP','SUMMARY')
    ),
    CONSTRAINT ck_widget_registry_item_status CHECK (
        status IN ('ACTIVE','DRAFT','PLANNED','DISABLED','DEPRECATED','ARCHIVED')
    ),
    CONSTRAINT ck_widget_registry_item_default_size CHECK (
        default_size IN ('small','medium','large')
    )
);

ALTER TABLE widget_registry_items
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN allowed_roles SET DEFAULT '[]'::json,
    ALTER COLUMN allowed_cabinet_types SET DEFAULT '[]'::json,
    ALTER COLUMN default_size SET DEFAULT 'medium',
    ALTER COLUMN allowed_sizes SET DEFAULT '["small","medium","large"]'::json,
    ALTER COLUMN status SET DEFAULT 'ACTIVE',
    ALTER COLUMN is_system SET DEFAULT TRUE,
    ALTER COLUMN is_mock SET DEFAULT FALSE,
    ALTER COLUMN sort_order SET DEFAULT 1000,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_widget_registry_items_widget_code
    ON widget_registry_items(widget_code);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_source_module_code
    ON widget_registry_items(source_module_code);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_canonical_module_code
    ON widget_registry_items(canonical_module_code);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_feature_code
    ON widget_registry_items(feature_code);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_legacy_module_code
    ON widget_registry_items(legacy_module_code);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_widget_type
    ON widget_registry_items(widget_type);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_status
    ON widget_registry_items(status);
CREATE INDEX IF NOT EXISTS ix_widget_registry_items_sort_order
    ON widget_registry_items(sort_order);

INSERT INTO widget_registry_items (
    widget_code,
    title,
    description,
    source_module_code,
    canonical_module_code,
    feature_code,
    legacy_module_code,
    widget_type,
    data_source,
    required_access_level,
    required_scope,
    required_action_code,
    allowed_roles,
    allowed_cabinet_types,
    default_size,
    allowed_sizes,
    status,
    is_system,
    is_mock,
    sort_order,
    settings
) VALUES
('materials-kpi','Материалы','Количество материалов и новые позиции.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB',NULL,NULL,'KPI','materialHubSummary','VIEW','LIMITED',NULL,'[]'::json,'[]'::json,'small','["small","medium","large"]'::json,'ACTIVE',TRUE,TRUE,10,'{"payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('classification-queue','Требует классификации','Очередь материалов, которым нужна ручная проверка.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB',NULL,NULL,'TASK_QUEUE',NULL,'VIEW','LIMITED',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'ACTIVE',TRUE,FALSE,20,'{"payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('price-dynamics','Динамика цен','Изменение цен и индекс стоимости.','MODULE_11_ANALYTICS','MODULE_11_ANALYTICS','PRICE_DYNAMICS','MODULE_14_PRICE_HISTORY','CHART','priceDynamicsSummary','VIEW','LIMITED',NULL,'[]'::json,'[]'::json,'large','["small","medium","large"]'::json,'ACTIVE',TRUE,TRUE,30,'{"payloadOwner":"MODULE_11_ANALYTICS","legacyFeature":"PRICE_DYNAMICS","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('source-health','Источники данных','Состояние активных источников сбора.','MODULE_01_MATERIAL_HUB','MODULE_01_MATERIAL_HUB',NULL,NULL,'STATUS',NULL,'VIEW','LIMITED',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'ACTIVE',TRUE,FALSE,40,'{"payloadOwner":"MODULE_01_MATERIAL_HUB","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('system-alerts','Уведомления','Ошибки, предупреждения и события платформы.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES',NULL,NULL,'ALERTS','systemEvents','VIEW','LIMITED',NULL,'["SUPER_ADMIN","PLATFORM_ADMIN"]'::json,'["ADMIN"]'::json,'medium','["small","medium","large"]'::json,'ACTIVE',TRUE,TRUE,50,'{"contextCode":"DASHBOARD_ADMIN_CONTEXT","payloadOwner":"DASHBOARD_ADMIN_CONTEXT","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('quick-actions','Действия карточек АТОМа','Legacy-запись: быстрые действия теперь выбираются на карточках модулей.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES',NULL,NULL,'ACTIONS',NULL,'VIEW','LIMITED','DASHBOARD_CONFIGURE','["SUPER_ADMIN","PLATFORM_ADMIN"]'::json,'["ADMIN"]'::json,'medium','["small","medium","large"]'::json,'DISABLED',TRUE,FALSE,60,'{"contextCode":"DASHBOARD_ADMIN_CONTEXT","payloadOwner":"DASHBOARD_ADMIN_CONTEXT","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('atom-map','Атомная карта','Избранные модули вокруг центра управления.','MODULE_03_USERS_ROLES','MODULE_03_USERS_ROLES',NULL,NULL,'ATOM_MAP',NULL,'VIEW','LIMITED',NULL,'[]'::json,'[]'::json,'large','["medium","large"]'::json,'ACTIVE',TRUE,FALSE,70,'{"contextCode":"DASHBOARD_ADMIN_CONTEXT","payloadOwner":"DASHBOARD_ADMIN_CONTEXT","registryLayer":"MODULE_03_WIDGET_REGISTRY"}'::json),
('digital-house-status','Образ дома','Состояние цифрового объекта строительства.','MODULE_07_DIGITAL_HOUSE','MODULE_07_DIGITAL_HOUSE','HOUSE_PROFILE',NULL,'STATUS',NULL,'VIEW','OWN',NULL,'[]'::json,'["CUSTOMER"]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,80,'{"payloadOwner":"MODULE_07_DIGITAL_HOUSE","requiredModuleStatus":"ACTIVE"}'::json),
('estimate-summary','Сводка сметы','Итоговая стоимость, изменения и отклонения.','MODULE_05_ESTIMATE_ENGINE','MODULE_05_ESTIMATE_ENGINE',NULL,NULL,'KPI',NULL,'VIEW','OWN',NULL,'[]'::json,'["CUSTOMER","ESTIMATOR"]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,90,'{"payloadOwner":"MODULE_05_ESTIMATE_ENGINE","requiredModuleStatus":"ACTIVE"}'::json),
('estimate-audit-risk','Риски сметы','Проверка ошибок, дублей и подозрительных строк.','MODULE_06_ESTIMATE_AUDIT','MODULE_06_ESTIMATE_AUDIT',NULL,NULL,'ALERTS',NULL,'VIEW','OWN',NULL,'[]'::json,'["ESTIMATOR"]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,100,'{"payloadOwner":"MODULE_06_ESTIMATE_AUDIT","requiredModuleStatus":"ACTIVE"}'::json),
('procurement-requests','Закупки','Заявки, поставки и комплектация.','MODULE_09_PROCUREMENT','MODULE_09_PROCUREMENT',NULL,NULL,'LIST',NULL,'VIEW','OWN',NULL,'[]'::json,'["CUSTOMER","SUPPLIER"]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,110,'{"payloadOwner":"MODULE_09_PROCUREMENT","requiredModuleStatus":"ACTIVE"}'::json),
('marketplace-cart','Маркетплейс','Корзина, подборки и предложения.','MODULE_10_MARKETPLACE','MODULE_10_MARKETPLACE',NULL,NULL,'LIST',NULL,'VIEW','OWN',NULL,'[]'::json,'["CUSTOMER","SUPPLIER"]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,120,'{"payloadOwner":"MODULE_10_MARKETPLACE","requiredModuleStatus":"ACTIVE"}'::json),
('partner-tender-invites','Приглашения партнеров','Тендеры и входящие приглашения.','MODULE_08_PARTNER_PORTAL','MODULE_08_PARTNER_PORTAL',NULL,NULL,'TASK_QUEUE',NULL,'VIEW','OWN',NULL,'[]'::json,'["SUPPLIER"]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,130,'{"payloadOwner":"MODULE_08_PARTNER_PORTAL","requiredModuleStatus":"ACTIVE"}'::json),
('project-collaboration-activity','Комната проекта','Активность участников и проектные события.','MODULE_13_PROJECT_COLLABORATION','MODULE_13_PROJECT_COLLABORATION',NULL,NULL,'LIST',NULL,'VIEW','OWN',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,140,'{"payloadOwner":"MODULE_13_PROJECT_COLLABORATION","requiredModuleStatus":"ACTIVE"}'::json),
('constructor-changes','Конструктор Lite','Последние изменения модели и комплектаций.','MODULE_19_CONSTRUCTOR_LITE','MODULE_19_CONSTRUCTOR_LITE',NULL,'MODULE_14_CONSTRUCTOR_LITE','LIST',NULL,'VIEW','OWN',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,150,'{"payloadOwner":"MODULE_19_CONSTRUCTOR_LITE","requiredModuleStatus":"ACTIVE"}'::json),
('contracts-pending','Договоры','Договоры на согласовании и подписании.','MODULE_15_CONTRACTS','MODULE_15_CONTRACTS',NULL,NULL,'TASK_QUEUE',NULL,'VIEW','OWN',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,160,'{"payloadOwner":"MODULE_15_CONTRACTS","requiredModuleStatus":"ACTIVE"}'::json),
('ai-recommendations','AI-рекомендации','Рекомендации и подсказки AI-помощника.','MODULE_12_AI_ASSISTANT','MODULE_12_AI_ASSISTANT',NULL,NULL,'LIST',NULL,'VIEW','LIMITED',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,170,'{"payloadOwner":"MODULE_12_AI_ASSISTANT","requiredModuleStatus":"ACTIVE"}'::json),
('logistics-delivery','Логистика','Доставки, зоны и статусы отгрузок.','MODULE_16_LOGISTICS_DELIVERY','MODULE_16_LOGISTICS_DELIVERY',NULL,NULL,'STATUS',NULL,'VIEW','OWN',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,180,'{"payloadOwner":"MODULE_16_LOGISTICS_DELIVERY","requiredModuleStatus":"ACTIVE"}'::json),
('finance-budget','Финансы','Бюджет, платежи и кассовый план.','MODULE_17_FINANCE_PAYMENTS','MODULE_17_FINANCE_PAYMENTS',NULL,NULL,'KPI',NULL,'VIEW','OWN',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,190,'{"payloadOwner":"MODULE_17_FINANCE_PAYMENTS","requiredModuleStatus":"ACTIVE"}'::json),
('quality-control-issues','Контроль качества','Замечания, проверки и статусы качества.','MODULE_18_QUALITY_CONTROL','MODULE_18_QUALITY_CONTROL',NULL,NULL,'ALERTS',NULL,'VIEW','OWN',NULL,'[]'::json,'[]'::json,'medium','["small","medium","large"]'::json,'PLANNED',TRUE,FALSE,200,'{"payloadOwner":"MODULE_18_QUALITY_CONTROL","requiredModuleStatus":"ACTIVE"}'::json)
ON CONFLICT (widget_code) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    source_module_code = EXCLUDED.source_module_code,
    canonical_module_code = EXCLUDED.canonical_module_code,
    feature_code = EXCLUDED.feature_code,
    legacy_module_code = EXCLUDED.legacy_module_code,
    widget_type = EXCLUDED.widget_type,
    data_source = EXCLUDED.data_source,
    required_access_level = EXCLUDED.required_access_level,
    required_scope = EXCLUDED.required_scope,
    required_action_code = EXCLUDED.required_action_code,
    allowed_roles = EXCLUDED.allowed_roles,
    allowed_cabinet_types = EXCLUDED.allowed_cabinet_types,
    default_size = EXCLUDED.default_size,
    allowed_sizes = EXCLUDED.allowed_sizes,
    status = EXCLUDED.status,
    is_system = EXCLUDED.is_system,
    is_mock = EXCLUDED.is_mock,
    sort_order = EXCLUDED.sort_order,
    settings = EXCLUDED.settings,
    updated_at = now();
