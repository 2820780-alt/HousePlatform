-- Module 03 / Users, Roles, Workspaces v1.0
-- Adds configurable roles, permissions, module/function access, sessions, preferences and audit log.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name varchar(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at timestamp without time zone;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_at timestamp without time zone;
ALTER TABLE users ADD COLUMN IF NOT EXISTS settings jsonb;
CREATE INDEX IF NOT EXISTS ix_users_last_login_at ON users(last_login_at);
CREATE INDEX IF NOT EXISTS ix_users_last_activity_at ON users(last_activity_at);

CREATE TABLE IF NOT EXISTS roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_key varchar(80) NOT NULL UNIQUE,
    name varchar(255) NOT NULL,
    description text,
    is_system boolean NOT NULL DEFAULT false,
    settings jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_roles_role_key ON roles(role_key);
CREATE INDEX IF NOT EXISTS ix_roles_is_system ON roles(is_system);
CREATE INDEX IF NOT EXISTS ix_roles_status ON roles(status);
ALTER TABLE roles ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE roles ALTER COLUMN is_system SET DEFAULT false;
ALTER TABLE roles ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE roles ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE roles ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_key varchar(120) NOT NULL UNIQUE,
    name varchar(255) NOT NULL,
    description text,
    module_number integer,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_permissions_permission_key ON permissions(permission_key);
CREATE INDEX IF NOT EXISTS ix_permissions_module_number ON permissions(module_number);
CREATE INDEX IF NOT EXISTS ix_permissions_status ON permissions(status);
ALTER TABLE permissions ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE permissions ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE permissions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE permissions ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS role_permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    effect varchar(20) NOT NULL DEFAULT 'ALLOW',
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_role_permissions_role_permission ON role_permissions(role_id, permission_id);
CREATE INDEX IF NOT EXISTS ix_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS ix_role_permissions_permission_id ON role_permissions(permission_id);
CREATE INDEX IF NOT EXISTS ix_role_permissions_effect ON role_permissions(effect);
CREATE INDEX IF NOT EXISTS ix_role_permissions_status ON role_permissions(status);
ALTER TABLE role_permissions ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE role_permissions ALTER COLUMN effect SET DEFAULT 'ALLOW';
ALTER TABLE role_permissions ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE role_permissions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE role_permissions ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS user_role_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_role_assignments_user_id ON user_role_assignments(user_id);
CREATE INDEX IF NOT EXISTS ix_user_role_assignments_role_id ON user_role_assignments(role_id);
CREATE INDEX IF NOT EXISTS ix_user_role_assignments_workspace_id ON user_role_assignments(workspace_id);
CREATE INDEX IF NOT EXISTS ix_user_role_assignments_status ON user_role_assignments(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_role_assignments_user_role_workspace
    ON user_role_assignments(user_id, role_id, COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid));
ALTER TABLE user_role_assignments ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE user_role_assignments ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE user_role_assignments ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE user_role_assignments ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS module_access (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id uuid REFERENCES roles(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    module_number integer NOT NULL,
    access_level varchar(30) NOT NULL DEFAULT 'NO_ACCESS',
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_module_access_role_id ON module_access(role_id);
CREATE INDEX IF NOT EXISTS ix_module_access_user_id ON module_access(user_id);
CREATE INDEX IF NOT EXISTS ix_module_access_workspace_id ON module_access(workspace_id);
CREATE INDEX IF NOT EXISTS ix_module_access_module_number ON module_access(module_number);
CREATE INDEX IF NOT EXISTS ix_module_access_access_level ON module_access(access_level);
CREATE INDEX IF NOT EXISTS ix_module_access_status ON module_access(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_module_access_scope
    ON module_access(
        COALESCE(role_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        module_number
    );
ALTER TABLE module_access ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE module_access ALTER COLUMN access_level SET DEFAULT 'NO_ACCESS';
ALTER TABLE module_access ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE module_access ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE module_access ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS function_access (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id uuid REFERENCES roles(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    module_number integer,
    function_key varchar(120) NOT NULL,
    access_level varchar(30) NOT NULL DEFAULT 'NO_ACCESS',
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_function_access_role_id ON function_access(role_id);
CREATE INDEX IF NOT EXISTS ix_function_access_user_id ON function_access(user_id);
CREATE INDEX IF NOT EXISTS ix_function_access_workspace_id ON function_access(workspace_id);
CREATE INDEX IF NOT EXISTS ix_function_access_module_number ON function_access(module_number);
CREATE INDEX IF NOT EXISTS ix_function_access_function_key ON function_access(function_key);
CREATE INDEX IF NOT EXISTS ix_function_access_access_level ON function_access(access_level);
CREATE INDEX IF NOT EXISTS ix_function_access_status ON function_access(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_function_access_scope
    ON function_access(
        COALESCE(role_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(module_number, 0),
        function_key
    );
ALTER TABLE function_access ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE function_access ALTER COLUMN access_level SET DEFAULT 'NO_ACCESS';
ALTER TABLE function_access ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE function_access ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE function_access ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS user_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token_hash varchar(255),
    ip_address varchar(50),
    user_agent varchar(500),
    metadata_json jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    started_at timestamp without time zone NOT NULL DEFAULT now(),
    last_seen_at timestamp without time zone,
    ended_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_user_sessions_session_token_hash ON user_sessions(session_token_hash);
CREATE INDEX IF NOT EXISTS ix_user_sessions_ip_address ON user_sessions(ip_address);
CREATE INDEX IF NOT EXISTS ix_user_sessions_status ON user_sessions(status);
CREATE INDEX IF NOT EXISTS ix_user_sessions_started_at ON user_sessions(started_at);
CREATE INDEX IF NOT EXISTS ix_user_sessions_last_seen_at ON user_sessions(last_seen_at);
CREATE INDEX IF NOT EXISTS ix_user_sessions_ended_at ON user_sessions(ended_at);
ALTER TABLE user_sessions ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE user_sessions ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE user_sessions ALTER COLUMN started_at SET DEFAULT now();
ALTER TABLE user_sessions ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE user_sessions ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS user_preferences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    preference_key varchar(120) NOT NULL,
    value jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS ix_user_preferences_workspace_id ON user_preferences(workspace_id);
CREATE INDEX IF NOT EXISTS ix_user_preferences_preference_key ON user_preferences(preference_key);
CREATE INDEX IF NOT EXISTS ix_user_preferences_status ON user_preferences(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_preferences_user_workspace_key
    ON user_preferences(user_id, COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid), preference_key);
ALTER TABLE user_preferences ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE user_preferences ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE user_preferences ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE user_preferences ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS role_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key varchar(120) NOT NULL UNIQUE,
    name varchar(255) NOT NULL,
    description text,
    role_keys jsonb,
    permission_keys jsonb,
    module_access jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_role_templates_template_key ON role_templates(template_key);
CREATE INDEX IF NOT EXISTS ix_role_templates_status ON role_templates(status);
ALTER TABLE role_templates ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE role_templates ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE role_templates ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE role_templates ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE SET NULL,
    action_type varchar(80) NOT NULL,
    entity_type varchar(100),
    entity_id uuid,
    result varchar(30) NOT NULL DEFAULT 'SUCCESS',
    ip_address varchar(50),
    user_agent varchar(500),
    details jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_workspace_id ON audit_logs(workspace_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs(action_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_id ON audit_logs(entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_result ON audit_logs(result);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at);
ALTER TABLE audit_logs ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE audit_logs ALTER COLUMN result SET DEFAULT 'SUCCESS';
ALTER TABLE audit_logs ALTER COLUMN created_at SET DEFAULT now();

INSERT INTO roles (role_key, name, description, is_system)
VALUES
    ('ADMIN', 'Администратор', 'Полный доступ к управлению платформой.', true),
    ('MANAGER', 'Менеджер', 'Операционное управление данными и процессами.', true),
    ('ESTIMATOR', 'Сметчик', 'Работа со сметами, материалами и ценами.', true),
    ('ENGINEER', 'Инженер', 'Работа с технологиями, проектированием и проверками.', true),
    ('SUPPLIER', 'Поставщик', 'Работа с предложениями, прайсами и остатками.', true),
    ('CONTRACTOR', 'Подрядчик', 'Работа с проектами, работами и тендерами.', true),
    ('CUSTOMER', 'Заказчик', 'Просмотр своего проекта, смет и статусов.', true),
    ('ANALYST', 'Аналитик', 'Просмотр аналитики и динамики рынка.', true),
    ('MODERATOR', 'Модератор', 'Проверка данных, дублей, классификации и документов.', true),
    ('VIEWER', 'Наблюдатель', 'Ограниченный просмотр разрешенных разделов.', true)
ON CONFLICT (role_key) DO NOTHING;

INSERT INTO permissions (permission_key, name, description, module_number)
VALUES
    ('VIEW_MATERIALS', 'Просмотр материалов', 'Разрешает смотреть базу материалов.', 1),
    ('EDIT_MATERIALS', 'Редактирование материалов', 'Разрешает изменять материалы.', 1),
    ('DELETE_MATERIALS', 'Удаление материалов', 'Разрешает удалять или архивировать материалы.', 1),
    ('VIEW_DOCUMENTS', 'Просмотр документов', 'Разрешает смотреть документы и ресурсы знаний.', 1),
    ('EDIT_DOCUMENTS', 'Редактирование документов', 'Разрешает изменять документы и привязки.', 1),
    ('VIEW_PRICES', 'Просмотр цен', 'Разрешает смотреть цены и историю цен.', 14),
    ('EDIT_PRICES', 'Редактирование цен', 'Разрешает изменять цены через допустимые процессы.', 1),
    ('VIEW_USERS', 'Просмотр пользователей', 'Разрешает смотреть пользователей.', 3),
    ('MANAGE_USERS', 'Управление пользователями', 'Разрешает создавать, блокировать и изменять пользователей.', 3),
    ('VIEW_AUDIT', 'Просмотр аудита', 'Разрешает смотреть журнал действий.', 13),
    ('VIEW_KNOWLEDGE', 'Просмотр базы знаний', 'Разрешает смотреть знания и кандидаты.', 2),
    ('EDIT_KNOWLEDGE', 'Редактирование базы знаний', 'Разрешает проверять и изменять знания.', 2)
ON CONFLICT (permission_key) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id, effect)
SELECT r.id, p.id, 'ALLOW'
FROM roles r
CROSS JOIN permissions p
WHERE r.role_key = 'ADMIN'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id, effect)
SELECT r.id, p.id, 'ALLOW'
FROM roles r
JOIN permissions p ON p.permission_key IN (
    'VIEW_MATERIALS',
    'EDIT_MATERIALS',
    'VIEW_DOCUMENTS',
    'VIEW_PRICES',
    'VIEW_KNOWLEDGE'
)
WHERE r.role_key = 'MODERATOR'
ON CONFLICT DO NOTHING;

INSERT INTO module_access (role_id, module_number, access_level)
SELECT r.id, module_number, 'ADMIN'
FROM roles r
CROSS JOIN generate_series(1, 16) AS module_number
WHERE r.role_key = 'ADMIN'
ON CONFLICT DO NOTHING;

INSERT INTO module_access (role_id, module_number, access_level)
SELECT r.id, module_number, access_level
FROM roles r
JOIN (VALUES
    (1, 'EDIT'),
    (2, 'VIEW'),
    (13, 'VIEW'),
    (14, 'VIEW'),
    (16, 'VIEW')
) AS access(module_number, access_level) ON true
WHERE r.role_key = 'MODERATOR'
ON CONFLICT DO NOTHING;

INSERT INTO role_templates (template_key, name, description, role_keys, permission_keys, module_access)
VALUES (
    'atom_default_admin',
    'Базовый администратор АТОМ',
    'Шаблон полного административного доступа для начальной настройки платформы.',
    '["ADMIN"]'::jsonb,
    (SELECT jsonb_agg(permission_key ORDER BY permission_key) FROM permissions),
    '{"1":"ADMIN","2":"ADMIN","3":"ADMIN","4":"ADMIN","5":"ADMIN","6":"ADMIN","7":"ADMIN","8":"ADMIN","9":"ADMIN","10":"ADMIN","11":"ADMIN","12":"ADMIN","13":"ADMIN","14":"ADMIN","15":"ADMIN","16":"ADMIN"}'::jsonb
)
ON CONFLICT (template_key) DO NOTHING;

INSERT INTO audit_logs (action_type, entity_type, details)
VALUES (
    'MODULE03_PREPARED',
    'Module03',
    jsonb_build_object('migration', '20260620_module03_users_roles_workspaces')
);

COMMIT;
