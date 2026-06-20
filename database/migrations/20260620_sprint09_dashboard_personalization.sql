-- Sprint 09
-- Prepare Atom dashboard personalization, workspaces, favorite modules and RBAC-ready memberships.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS workspaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    slug varchar(255) NOT NULL UNIQUE,
    workspace_type varchar(50) NOT NULL DEFAULT 'ADMIN',
    description text,
    settings jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_workspaces_name ON workspaces(name);
CREATE INDEX IF NOT EXISTS ix_workspaces_workspace_type ON workspaces(workspace_type);
CREATE INDEX IF NOT EXISTS ix_workspaces_status ON workspaces(status);
ALTER TABLE workspaces ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE workspaces ALTER COLUMN workspace_type SET DEFAULT 'ADMIN';
ALTER TABLE workspaces ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE workspaces ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE workspaces ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS workspace_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_key varchar(80) NOT NULL,
    permissions jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_workspace_members_workspace_user ON workspace_members(workspace_id, user_id);
CREATE INDEX IF NOT EXISTS ix_workspace_members_workspace_id ON workspace_members(workspace_id);
CREATE INDEX IF NOT EXISTS ix_workspace_members_user_id ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS ix_workspace_members_role_key ON workspace_members(role_key);
CREATE INDEX IF NOT EXISTS ix_workspace_members_status ON workspace_members(status);
ALTER TABLE workspace_members ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE workspace_members ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE workspace_members ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE workspace_members ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    widget_key varchar(120) NOT NULL UNIQUE,
    title varchar(255) NOT NULL,
    description text,
    module_number integer,
    widget_type varchar(50) NOT NULL,
    default_size varchar(30) NOT NULL DEFAULT 'M',
    config_schema jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_widget_key ON dashboard_widgets(widget_key);
CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_module_number ON dashboard_widgets(module_number);
CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_widget_type ON dashboard_widgets(widget_type);
CREATE INDEX IF NOT EXISTS ix_dashboard_widgets_status ON dashboard_widgets(status);
ALTER TABLE dashboard_widgets ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE dashboard_widgets ALTER COLUMN default_size SET DEFAULT 'M';
ALTER TABLE dashboard_widgets ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE dashboard_widgets ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE dashboard_widgets ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS dashboard_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE SET NULL,
    name varchar(255) NOT NULL,
    is_default boolean NOT NULL DEFAULT false,
    layout jsonb,
    theme_key varchar(80) NOT NULL DEFAULT 'atom-dark',
    density varchar(30) NOT NULL DEFAULT 'normal',
    favorite_modules jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dashboard_profiles_user_id ON dashboard_profiles(user_id);
CREATE INDEX IF NOT EXISTS ix_dashboard_profiles_workspace_id ON dashboard_profiles(workspace_id);
CREATE INDEX IF NOT EXISTS ix_dashboard_profiles_is_default ON dashboard_profiles(is_default);
CREATE INDEX IF NOT EXISTS ix_dashboard_profiles_status ON dashboard_profiles(status);
ALTER TABLE dashboard_profiles ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE dashboard_profiles ALTER COLUMN is_default SET DEFAULT false;
ALTER TABLE dashboard_profiles ALTER COLUMN theme_key SET DEFAULT 'atom-dark';
ALTER TABLE dashboard_profiles ALTER COLUMN density SET DEFAULT 'normal';
ALTER TABLE dashboard_profiles ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE dashboard_profiles ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE dashboard_profiles ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS dashboard_widget_placements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dashboard_profile_id uuid NOT NULL REFERENCES dashboard_profiles(id) ON DELETE CASCADE,
    widget_id uuid NOT NULL REFERENCES dashboard_widgets(id) ON DELETE CASCADE,
    zone varchar(80) NOT NULL DEFAULT 'main',
    sort_order integer NOT NULL DEFAULT 100,
    size varchar(30) NOT NULL DEFAULT 'M',
    config jsonb,
    is_visible boolean NOT NULL DEFAULT true,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dashboard_widget_placements_dashboard_profile_id ON dashboard_widget_placements(dashboard_profile_id);
CREATE INDEX IF NOT EXISTS ix_dashboard_widget_placements_widget_id ON dashboard_widget_placements(widget_id);
CREATE INDEX IF NOT EXISTS ix_dashboard_widget_placements_zone ON dashboard_widget_placements(zone);
CREATE INDEX IF NOT EXISTS ix_dashboard_widget_placements_is_visible ON dashboard_widget_placements(is_visible);
ALTER TABLE dashboard_widget_placements ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE dashboard_widget_placements ALTER COLUMN zone SET DEFAULT 'main';
ALTER TABLE dashboard_widget_placements ALTER COLUMN sort_order SET DEFAULT 100;
ALTER TABLE dashboard_widget_placements ALTER COLUMN size SET DEFAULT 'M';
ALTER TABLE dashboard_widget_placements ALTER COLUMN is_visible SET DEFAULT true;
ALTER TABLE dashboard_widget_placements ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE dashboard_widget_placements ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS favorite_modules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    workspace_id uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    module_number integer NOT NULL,
    sort_order integer NOT NULL DEFAULT 100,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_favorite_modules_user_id ON favorite_modules(user_id);
CREATE INDEX IF NOT EXISTS ix_favorite_modules_workspace_id ON favorite_modules(workspace_id);
CREATE INDEX IF NOT EXISTS ix_favorite_modules_module_number ON favorite_modules(module_number);
CREATE INDEX IF NOT EXISTS ix_favorite_modules_status ON favorite_modules(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_favorite_modules_user_workspace_module
    ON favorite_modules(COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(workspace_id, '00000000-0000-0000-0000-000000000000'::uuid), module_number);
ALTER TABLE favorite_modules ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE favorite_modules ALTER COLUMN sort_order SET DEFAULT 100;
ALTER TABLE favorite_modules ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE favorite_modules ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE favorite_modules ALTER COLUMN updated_at SET DEFAULT now();

INSERT INTO workspaces (name, slug, workspace_type, description, settings)
VALUES (
    'Административное пространство',
    'admin-default',
    'ADMIN',
    'Базовое рабочее пространство администратора платформы АТОМ.',
    '{"theme": "atom-dark", "dashboard": "admin"}'::jsonb
)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO dashboard_widgets (widget_key, title, description, module_number, widget_type, default_size, config_schema)
VALUES
    ('module_atom_map', 'Атомная карта модулей', 'Центральная карта модулей платформы.', 16, 'ATOM_MAP', 'XL', '{"required": true}'::jsonb),
    ('material_kpi', 'Показатели базы материалов', 'Материалы, документы, модерация и источники.', 1, 'KPI', 'M', '{"source": "material_hub"}'::jsonb),
    ('price_dynamics_chart', 'Динамика цен', 'График изменения стоимости по рынку и категориям.', 14, 'CHART', 'L', '{"source": "price_history"}'::jsonb),
    ('source_health', 'Состояние источников', 'Активность и ошибки источников данных.', 1, 'STATUS_LIST', 'M', '{"source": "source_tasks"}'::jsonb),
    ('moderation_queue', 'Очередь модерации', 'Спорные совпадения и материалы на проверке.', 1, 'QUEUE', 'M', '{"source": "quality"}'::jsonb),
    ('quick_actions', 'Быстрые действия', 'Импорт, анализ, создание сметы и тендера.', 16, 'ACTIONS', 'M', '{"editable": true}'::jsonb),
    ('system_events', 'События платформы', 'Уведомления и системные события.', 13, 'EVENTS', 'M', '{"source": "audit"}'::jsonb)
ON CONFLICT (widget_key) DO NOTHING;

INSERT INTO dashboard_profiles (workspace_id, name, is_default, layout, favorite_modules)
SELECT
    w.id,
    'Администратор: обзор платформы',
    true,
    '{"preset": "atom-admin-overview", "zones": ["kpi", "atom", "analytics", "events"]}'::jsonb,
    '[1, 14, 16]'::jsonb
FROM workspaces w
WHERE w.slug = 'admin-default'
  AND NOT EXISTS (
      SELECT 1 FROM dashboard_profiles dp
      WHERE dp.workspace_id = w.id
        AND dp.user_id IS NULL
        AND dp.name = 'Администратор: обзор платформы'
  );

INSERT INTO favorite_modules (workspace_id, module_number, sort_order)
SELECT w.id, module_number, sort_order
FROM workspaces w
CROSS JOIN (VALUES (1, 10), (14, 20), (16, 30)) AS fav(module_number, sort_order)
WHERE w.slug = 'admin-default'
ON CONFLICT DO NOTHING;

INSERT INTO dashboard_widget_placements (dashboard_profile_id, widget_id, zone, sort_order, size, config)
SELECT dp.id, dw.id, placement.zone, placement.sort_order, placement.size, placement.config
FROM dashboard_profiles dp
JOIN workspaces w ON w.id = dp.workspace_id AND w.slug = 'admin-default'
JOIN (VALUES
    ('module_atom_map', 'atom', 10, 'XL', '{"locked": false}'::jsonb),
    ('material_kpi', 'kpi', 20, 'M', '{"visible": true}'::jsonb),
    ('price_dynamics_chart', 'analytics', 30, 'L', '{"period": "month"}'::jsonb),
    ('source_health', 'events', 40, 'M', '{"visible": true}'::jsonb),
    ('quick_actions', 'actions', 50, 'M', '{"visible": true}'::jsonb)
) AS placement(widget_key, zone, sort_order, size, config) ON true
JOIN dashboard_widgets dw ON dw.widget_key = placement.widget_key
WHERE dp.user_id IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM dashboard_widget_placements dwp
      WHERE dwp.dashboard_profile_id = dp.id
        AND dwp.widget_id = dw.id
  );

INSERT INTO audit_events (id, event_type, entity_type, entity_id, user_id, details, ip_address, created_at)
VALUES (
    gen_random_uuid(),
    'sprint09_dashboard_personalization_prepared',
    'AdminCabinet',
    NULL,
    NULL,
    json_build_object('migration', '20260620_sprint09_dashboard_personalization'),
    NULL,
    now()
);

COMMIT;
