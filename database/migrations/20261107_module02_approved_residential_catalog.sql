-- Approved M2 navigation taxonomy only. No Technology or engineering content.
BEGIN;

CREATE TEMP TABLE m2_approved_catalog_seed (
    code varchar(120) PRIMARY KEY,
    parent_code varchar(120),
    name varchar(255) NOT NULL,
    description text,
    sort_order integer NOT NULL
) ON COMMIT DROP;

INSERT INTO m2_approved_catalog_seed (code, parent_code, name, description, sort_order) VALUES
    ('PREPARATION', NULL, 'Подготовка и демонтаж', NULL, 10),
    ('FOUNDATIONS', NULL, 'Фундаменты и подземная часть', 'Фундаментные системы и конструкции подземной части жилого дома.', 20),
    ('WALLS', NULL, 'Стены и несущий каркас', NULL, 30),
    ('PARTITIONS', NULL, 'Перегородки', NULL, 40),
    ('FLOORS_AND_STAIRS', NULL, 'Перекрытия, полы по грунту и лестницы', NULL, 50),
    ('ROOF', NULL, 'Крыша, кровля и водосток', NULL, 60),
    ('FACADE_AND_OPENINGS', NULL, 'Фасад, окна и наружные двери', NULL, 70),
    ('SITE_WORKS', NULL, 'Работы вокруг дома', NULL, 80),
    ('INTERIOR_ROUGH', NULL, 'Черновая внутренняя отделка', NULL, 90),
    ('INTERIOR_FINISH', NULL, 'Чистовая отделка', NULL, 100),
    ('WATER_AND_SEWER', NULL, 'Водоснабжение и канализация', NULL, 110),
    ('HEATING_AND_DHW', NULL, 'Отопление и горячая вода', NULL, 120),
    ('VENTILATION_AND_AC', NULL, 'Вентиляция и кондиционирование', NULL, 130),
    ('ELECTRICAL_AND_AUTOMATION', NULL, 'Электрика, слаботочка и умный дом', NULL, 140),
    ('GAS_AND_COMBUSTION', NULL, 'Газ, дымоходы, печи и камины', NULL, 150),
    ('FINAL_INSTALLATION', NULL, 'Финальное оснащение', NULL, 160),
    ('STRIP_FOUNDATIONS', 'FOUNDATIONS', 'Ленточные фундаменты', NULL, 10),
    ('SLAB_FOUNDATIONS', 'FOUNDATIONS', 'Плитные фундаменты', NULL, 20),
    ('PILE_FOUNDATIONS', 'FOUNDATIONS', 'Свайные основания', NULL, 30),
    ('PILE_GRILLAGE_FOUNDATIONS', 'FOUNDATIONS', 'Свайно-ростверковые системы', NULL, 40),
    ('COLUMN_FOUNDATIONS', 'FOUNDATIONS', 'Столбчатые фундаменты', NULL, 50),
    ('BASEMENT_AND_SUBSTRUCTURE', 'FOUNDATIONS', 'Подвал, цоколь и подземные конструкции', NULL, 60);

INSERT INTO module2_technology_categories (
    code, parent_id, name, description, sort_order, scope_code, status, content_status
)
SELECT code, NULL, name, description, sort_order, 'RESIDENTIAL', 'ACTIVE',
       CASE WHEN code = 'FOUNDATIONS' THEN 'IN_PROGRESS' ELSE 'EMPTY' END
FROM m2_approved_catalog_seed
WHERE parent_code IS NULL
ON CONFLICT (code) DO NOTHING;

INSERT INTO module2_technology_categories (
    code, parent_id, name, description, sort_order, scope_code, status, content_status
)
SELECT seed.code, parent.id, seed.name, seed.description, seed.sort_order,
       'RESIDENTIAL', 'ACTIVE', 'EMPTY'
FROM m2_approved_catalog_seed AS seed
JOIN module2_technology_categories AS parent ON parent.code = seed.parent_code
WHERE seed.parent_code IS NOT NULL
ON CONFLICT (code) DO NOTHING;

DO $approved_catalog$
BEGIN
    IF (
        SELECT count(*) FROM m2_approved_catalog_seed AS seed
        JOIN module2_technology_categories AS category ON category.code = seed.code
        LEFT JOIN module2_technology_categories AS parent ON parent.code = seed.parent_code
        WHERE category.name = seed.name
          AND category.sort_order = seed.sort_order
          AND category.scope_code = 'RESIDENTIAL'
          AND category.parent_id IS NOT DISTINCT FROM parent.id
    ) <> (SELECT count(*) FROM m2_approved_catalog_seed) THEN
        RAISE EXCEPTION 'Approved M2 taxonomy conflicts with existing category rows';
    END IF;
END
$approved_catalog$;

COMMIT;
