-- Module 01 / Material Hub v2.0
-- Adds a safe v2 data layer around existing Material, CatalogProduct and MaterialDocument.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS construction_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL UNIQUE,
    slug varchar(255) NOT NULL UNIQUE,
    description text,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_construction_groups_name ON construction_groups(name);
CREATE INDEX IF NOT EXISTS ix_construction_groups_status ON construction_groups(status);
ALTER TABLE construction_groups ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE construction_groups ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE construction_groups ALTER COLUMN sort_order SET DEFAULT 0;
ALTER TABLE construction_groups ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE construction_groups ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS material_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    construction_group_id uuid REFERENCES construction_groups(id) ON DELETE SET NULL,
    category_id uuid NOT NULL REFERENCES material_categories(id) ON DELETE RESTRICT,
    subcategory_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    name varchar(255) NOT NULL,
    slug varchar(255) NOT NULL UNIQUE,
    description text,
    key_characteristics jsonb,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_material_types_construction_group_id ON material_types(construction_group_id);
CREATE INDEX IF NOT EXISTS ix_material_types_category_id ON material_types(category_id);
CREATE INDEX IF NOT EXISTS ix_material_types_subcategory_id ON material_types(subcategory_id);
CREATE INDEX IF NOT EXISTS ix_material_types_name ON material_types(name);
CREATE INDEX IF NOT EXISTS ix_material_types_status ON material_types(status);
ALTER TABLE material_types ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE material_types ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE material_types ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE material_types ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE materials ADD COLUMN IF NOT EXISTS material_type_id uuid REFERENCES material_types(id) ON DELETE SET NULL;
ALTER TABLE materials ADD COLUMN IF NOT EXISTS article varchar(255);
CREATE INDEX IF NOT EXISTS ix_materials_material_type_id ON materials(material_type_id);
CREATE INDEX IF NOT EXISTS ix_materials_article ON materials(article);

CREATE TABLE IF NOT EXISTS classification_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(255) NOT NULL,
    rule_code varchar(120) UNIQUE,
    construction_group_id uuid REFERENCES construction_groups(id) ON DELETE SET NULL,
    category_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    subcategory_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    material_type_id uuid REFERENCES material_types(id) ON DELETE SET NULL,
    priority integer NOT NULL DEFAULT 100,
    match_keywords jsonb,
    required_keywords jsonb,
    excluded_keywords jsonb,
    source_category_patterns jsonb,
    brand_patterns jsonb,
    manufacturer_patterns jsonb,
    characteristic_conditions jsonb,
    confidence numeric(5, 4),
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_from_material_id uuid REFERENCES materials(id) ON DELETE SET NULL,
    note text,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_classification_rules_rule_code ON classification_rules(rule_code);
CREATE INDEX IF NOT EXISTS ix_classification_rules_construction_group_id ON classification_rules(construction_group_id);
CREATE INDEX IF NOT EXISTS ix_classification_rules_category_id ON classification_rules(category_id);
CREATE INDEX IF NOT EXISTS ix_classification_rules_subcategory_id ON classification_rules(subcategory_id);
CREATE INDEX IF NOT EXISTS ix_classification_rules_material_type_id ON classification_rules(material_type_id);
CREATE INDEX IF NOT EXISTS ix_classification_rules_priority ON classification_rules(priority);
CREATE INDEX IF NOT EXISTS ix_classification_rules_status ON classification_rules(status);
ALTER TABLE classification_rules ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE classification_rules ALTER COLUMN priority SET DEFAULT 100;
ALTER TABLE classification_rules ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE classification_rules ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE classification_rules ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS knowledge_resources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid REFERENCES sources(id) ON DELETE SET NULL,
    legacy_document_id uuid REFERENCES material_documents(id) ON DELETE SET NULL,
    resource_type varchar(50) NOT NULL,
    title varchar(500) NOT NULL,
    resource_url varchar(1000),
    source_url varchar(1000),
    metadata_json jsonb,
    extracted_data jsonb,
    extracted_text text,
    issue_date date,
    expiry_date date,
    status varchar(30) NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_knowledge_resources_source_id ON knowledge_resources(source_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resources_legacy_document_id ON knowledge_resources(legacy_document_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resources_resource_type ON knowledge_resources(resource_type);
CREATE INDEX IF NOT EXISTS ix_knowledge_resources_status ON knowledge_resources(status);
CREATE INDEX IF NOT EXISTS ix_knowledge_resources_expiry_date ON knowledge_resources(expiry_date);
ALTER TABLE knowledge_resources ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE knowledge_resources ALTER COLUMN status SET DEFAULT 'NEEDS_REVIEW';
ALTER TABLE knowledge_resources ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE knowledge_resources ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS knowledge_resource_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL REFERENCES knowledge_resources(id) ON DELETE CASCADE,
    material_id uuid REFERENCES materials(id) ON DELETE SET NULL,
    construction_group_id uuid REFERENCES construction_groups(id) ON DELETE SET NULL,
    category_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    subcategory_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    material_type_id uuid REFERENCES material_types(id) ON DELETE SET NULL,
    manufacturer_id uuid REFERENCES manufacturers(id) ON DELETE SET NULL,
    link_type varchar(50) NOT NULL DEFAULT 'APPLIES_TO',
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_resource_id ON knowledge_resource_links(resource_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_material_id ON knowledge_resource_links(material_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_construction_group_id ON knowledge_resource_links(construction_group_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_category_id ON knowledge_resource_links(category_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_subcategory_id ON knowledge_resource_links(subcategory_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_material_type_id ON knowledge_resource_links(material_type_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_manufacturer_id ON knowledge_resource_links(manufacturer_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_link_type ON knowledge_resource_links(link_type);
CREATE INDEX IF NOT EXISTS ix_knowledge_resource_links_status ON knowledge_resource_links(status);
ALTER TABLE knowledge_resource_links ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE knowledge_resource_links ALTER COLUMN link_type SET DEFAULT 'APPLIES_TO';
ALTER TABLE knowledge_resource_links ALTER COLUMN status SET DEFAULT 'ACTIVE';
ALTER TABLE knowledge_resource_links ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE knowledge_resource_links ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS material_analogs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id uuid NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    analog_material_id uuid NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    relation_type varchar(30) NOT NULL DEFAULT 'ANALOG',
    match_score numeric(5, 4),
    reason text,
    status varchar(30) NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT material_analogs_not_self CHECK (material_id <> analog_material_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_material_analogs_pair_type
    ON material_analogs(material_id, analog_material_id, relation_type);
CREATE INDEX IF NOT EXISTS ix_material_analogs_material_id ON material_analogs(material_id);
CREATE INDEX IF NOT EXISTS ix_material_analogs_analog_material_id ON material_analogs(analog_material_id);
CREATE INDEX IF NOT EXISTS ix_material_analogs_relation_type ON material_analogs(relation_type);
CREATE INDEX IF NOT EXISTS ix_material_analogs_status ON material_analogs(status);
ALTER TABLE material_analogs ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE material_analogs ALTER COLUMN relation_type SET DEFAULT 'ANALOG';
ALTER TABLE material_analogs ALTER COLUMN status SET DEFAULT 'NEEDS_REVIEW';
ALTER TABLE material_analogs ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE material_analogs ALTER COLUMN updated_at SET DEFAULT now();

CREATE TABLE IF NOT EXISTS material_quality_issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id uuid NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    issue_type varchar(50) NOT NULL,
    severity varchar(30) NOT NULL DEFAULT 'MEDIUM',
    reason text,
    details jsonb,
    status varchar(30) NOT NULL DEFAULT 'OPEN',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_material_quality_issues_material_id ON material_quality_issues(material_id);
CREATE INDEX IF NOT EXISTS ix_material_quality_issues_issue_type ON material_quality_issues(issue_type);
CREATE INDEX IF NOT EXISTS ix_material_quality_issues_severity ON material_quality_issues(severity);
CREATE INDEX IF NOT EXISTS ix_material_quality_issues_status ON material_quality_issues(status);
ALTER TABLE material_quality_issues ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE material_quality_issues ALTER COLUMN severity SET DEFAULT 'MEDIUM';
ALTER TABLE material_quality_issues ALTER COLUMN status SET DEFAULT 'OPEN';
ALTER TABLE material_quality_issues ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE material_quality_issues ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE knowledge_candidates
    ADD COLUMN IF NOT EXISTS knowledge_resource_id uuid REFERENCES knowledge_resources(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_knowledge_resource_id ON knowledge_candidates(knowledge_resource_id);

ALTER TABLE unit_conversion_rules
    ADD COLUMN IF NOT EXISTS material_type_id uuid REFERENCES material_types(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_material_type_id ON unit_conversion_rules(material_type_id);

INSERT INTO construction_groups (name, slug, description, sort_order)
VALUES
    ('Фундамент', 'fundament', 'Материалы и решения для основания здания.', 10),
    ('Стены', 'steny', 'Стеновые материалы, кладочные смеси и связанные элементы.', 20),
    ('Перегородки', 'peregorodki', 'Материалы для внутренних перегородок.', 30),
    ('Перекрытия', 'perekrytiya', 'Материалы для перекрытий и настилов.', 40),
    ('Кровля', 'krovlya', 'Кровельные покрытия, водосток и комплектующие.', 50),
    ('Фасад', 'fasad', 'Фасадные материалы, панели, сайдинг и доборные элементы.', 60),
    ('Гидроизоляция', 'gidroizolyaciya', 'Гидроизоляционные материалы и системы.', 70),
    ('Теплоизоляция', 'teploizolyaciya', 'Теплоизоляционные материалы.', 80),
    ('Звукоизоляция', 'zvukoizolyaciya', 'Акустические и звукоизоляционные материалы.', 90),
    ('Окна', 'okna', 'Оконные системы и комплектующие.', 100),
    ('Двери', 'dveri', 'Дверные системы и комплектующие.', 110),
    ('Электрика', 'elektrika', 'Кабель, освещение, щитовое оборудование и электромонтаж.', 120),
    ('Вентиляция', 'ventilyaciya', 'Вентиляционные материалы и оборудование.', 130),
    ('Отопление', 'otoplenie', 'Материалы и оборудование для отопления.', 140),
    ('Водоснабжение', 'vodosnabzhenie', 'Материалы для водоснабжения.', 150),
    ('Канализация', 'kanalizaciya', 'Материалы для канализации.', 160),
    ('Внутренняя отделка', 'vnutrennyaya-otdelka', 'Материалы для внутренней отделки.', 170),
    ('Наружная отделка', 'naruzhnaya-otdelka', 'Материалы для наружной отделки.', 180),
    ('Благоустройство', 'blagoustroystvo', 'Материалы для участка и благоустройства.', 190),
    ('Крепеж', 'krepezh', 'Крепежные изделия и расходные элементы.', 200),
    ('Инструмент', 'instrument', 'Инструменты и расходный инструмент.', 210)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO knowledge_resources (
    source_id,
    legacy_document_id,
    resource_type,
    title,
    resource_url,
    source_url,
    metadata_json,
    issue_date,
    expiry_date,
    status,
    created_at,
    updated_at
)
SELECT
    md.source_id,
    md.id,
    md.document_type::text,
    md.title,
    md.file_url,
    md.source_url,
    jsonb_build_object('migrated_from', 'MaterialDocument'),
    md.issue_date,
    md.expiry_date,
    md.status::text,
    md.created_at,
    now()
FROM material_documents md
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_resources kr WHERE kr.legacy_document_id = md.id
);

INSERT INTO knowledge_resource_links (
    resource_id,
    material_id,
    category_id,
    subcategory_id,
    manufacturer_id,
    link_type,
    status,
    created_at,
    updated_at
)
SELECT
    kr.id,
    md.material_id,
    m.category_id,
    m.subcategory_id,
    md.manufacturer_id,
    'APPLIES_TO',
    'ACTIVE',
    now(),
    now()
FROM knowledge_resources kr
JOIN material_documents md ON md.id = kr.legacy_document_id
LEFT JOIN materials m ON m.id = md.material_id
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_resource_links krl WHERE krl.resource_id = kr.id
);

INSERT INTO material_quality_issues (material_id, issue_type, severity, reason, details)
SELECT
    m.id,
    'CLASSIFICATION_REQUIRED',
    'HIGH',
    'Материал без категории требует классификации.',
    jsonb_build_object('source', 'module01_v2_migration')
FROM materials m
WHERE m.category_id IS NULL
  AND m.status NOT IN ('ARCHIVED', 'REJECTED')
  AND NOT EXISTS (
      SELECT 1 FROM material_quality_issues qi
      WHERE qi.material_id = m.id
        AND qi.issue_type = 'CLASSIFICATION_REQUIRED'
        AND qi.status = 'OPEN'
  );

INSERT INTO classification_rules (
    name,
    rule_code,
    construction_group_id,
    category_id,
    subcategory_id,
    priority,
    match_keywords,
    confidence,
    status,
    note
)
SELECT
    'Газобетонные блоки',
    'wall_aerated_concrete_blocks',
    cg.id,
    parent.id,
    child.id,
    20,
    '["газобетон", "газобетонный блок", "bonolit", "ytong", "вкблок"]'::jsonb,
    0.9000,
    'ACTIVE',
    'Seed rule for Material Hub v2.0'
FROM construction_groups cg
JOIN material_categories parent ON parent.name = 'Стеновые материалы' AND parent.parent_id IS NULL
JOIN material_categories child ON child.parent_id = parent.id AND child.name = 'Газобетонные блоки'
WHERE cg.slug = 'steny'
ON CONFLICT (rule_code) DO NOTHING;

INSERT INTO classification_rules (
    name,
    rule_code,
    construction_group_id,
    category_id,
    subcategory_id,
    priority,
    match_keywords,
    confidence,
    status,
    note
)
SELECT
    'OSB',
    'sheet_osb',
    cg.id,
    parent.id,
    child.id,
    30,
    '["osb", "осп", "осб", "плита osb"]'::jsonb,
    0.8800,
    'ACTIVE',
    'Seed rule for Material Hub v2.0'
FROM construction_groups cg
JOIN material_categories parent ON parent.name = 'Листовые и плитные материалы' AND parent.parent_id IS NULL
JOIN material_categories child ON child.parent_id = parent.id AND child.name = 'OSB'
WHERE cg.slug = 'perekrytiya'
ON CONFLICT (rule_code) DO NOTHING;

INSERT INTO audit_events (id, event_type, entity_type, entity_id, user_id, details, ip_address, created_at)
VALUES (
    gen_random_uuid(),
    'module01_material_hub_v2_prepared',
    'MaterialHub',
    NULL,
    NULL,
    json_build_object('migration', '20260620_module01_material_hub_v2'),
    NULL,
    now()
);

COMMIT;
