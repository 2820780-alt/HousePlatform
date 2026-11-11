BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE material_categories IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE units IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE material_attributes IN SHARE ROW EXCLUSIVE MODE;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'material_attributes' AND column_name = 'value_type'
          AND (data_type <> 'character varying' OR character_maximum_length <> 20 OR is_nullable <> 'NO'
               OR column_default IS DISTINCT FROM '''text''::character varying')
    ) THEN
        RAISE EXCEPTION 'M1 material attribute value_type has an incompatible existing definition';
    END IF;
END $$;

ALTER TABLE material_attributes ADD COLUMN IF NOT EXISTS value_type varchar(20) NOT NULL DEFAULT 'text';

CREATE TEMP TABLE m1_ui_category_seed (
    name text NOT NULL,
    slug text NOT NULL,
    sort_order integer NOT NULL
) ON COMMIT DROP;

INSERT INTO m1_ui_category_seed (name, slug, sort_order) VALUES
    ('Сыпучие материалы', 'm1-ui-bulk-materials', 1),
    ('Бетон, цемент и растворы', 'm1-ui-concrete-cement-mortar', 2),
    ('Стеновые и сборные изделия', 'm1-ui-wall-precast-products', 3),
    ('Арматура и металлопрокат', 'm1-ui-rebar-metal', 4),
    ('Пиломатериалы и листы', 'm1-ui-timber-sheets', 5),
    ('Изоляционные материалы', 'm1-ui-insulation', 6),
    ('Кровельные материалы', 'm1-ui-roofing', 7),
    ('Облицовочные материалы', 'm1-ui-cladding', 8),
    ('Строительные смеси и химия', 'm1-ui-mixes-chemicals', 9),
    ('Напольные покрытия', 'm1-ui-flooring', 10),
    ('Материалы для стен и потолков', 'm1-ui-walls-ceilings', 11),
    ('Окна и двери', 'm1-ui-windows-doors', 12),
    ('Трубы и водоотведение', 'm1-ui-pipes-drainage', 13),
    ('Крепёж и монтажные изделия', 'm1-ui-fasteners', 14);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM m1_ui_category_seed s
        JOIN material_categories c ON c.slug = s.slug
        WHERE c.parent_id IS NOT NULL OR c.name <> s.name OR c.status <> 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'M1 UI category slug conflicts with an existing category';
    END IF;
    IF EXISTS (
        SELECT 1 FROM m1_ui_category_seed s
        JOIN material_categories c ON c.parent_id IS NULL AND lower(c.name) = lower(s.name)
        GROUP BY s.name HAVING count(*) > 1 OR bool_or(c.status <> 'ACTIVE' OR c.name <> s.name)
    ) THEN
        RAISE EXCEPTION 'M1 UI category name is duplicated or inactive';
    END IF;
    IF EXISTS (SELECT 1 FROM units WHERE abbreviation IN ('kg', 't') AND unit_type <> 'WEIGHT') THEN
        RAISE EXCEPTION 'M1 UI mass unit conflicts with an existing unit';
    END IF;
END $$;

INSERT INTO material_categories (id, parent_id, name, slug, status, level, sort_order, created_at, updated_at)
SELECT gen_random_uuid(), NULL, s.name, s.slug, 'ACTIVE', 0, s.sort_order, now(), now()
FROM m1_ui_category_seed s
WHERE NOT EXISTS (
    SELECT 1 FROM material_categories c WHERE c.parent_id IS NULL AND lower(c.name) = lower(s.name)
);

INSERT INTO units (id, name, abbreviation, unit_type, is_base, created_at)
SELECT gen_random_uuid(), u.name, u.abbreviation, 'WEIGHT', u.is_base, now()
FROM (VALUES ('Килограмм', 'kg', true), ('Тонна', 't', false)) AS u(name, abbreviation, is_base)
WHERE NOT EXISTS (SELECT 1 FROM units existing WHERE existing.abbreviation = u.abbreviation);

COMMIT;
