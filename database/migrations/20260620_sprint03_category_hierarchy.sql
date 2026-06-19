-- Sprint 03 / Module 01
-- Normalize current Material Hub category hierarchy without deleting linked data.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE material_categories
    ADD COLUMN IF NOT EXISTS status varchar(30) NOT NULL DEFAULT 'ACTIVE';

CREATE INDEX IF NOT EXISTS ix_material_categories_status
    ON material_categories(status);

DO $$
DECLARE
    v_roof uuid;
    v_roof_water_old uuid;
    v_electric uuid;
    v_electric_light_old uuid;
    v_electro_goods_old uuid;
    v_sheet uuid;
    v_dry_building uuid;
    v_dry_mix uuid;
    v_wall uuid;
    v_heat uuid;
    v_facade uuid;
    v_building_old uuid;
    v_profiles uuid;
    v_gas_blocks uuid;
    v_gas_block_duplicate uuid;
    v_tray_blocks uuid;
    v_osb uuid;
    v_xps uuid;
    v_acoustic uuid;
    v_flexible_shingles uuid;
    v_gkl uuid;
    v_gvl uuid;
    v_gypsum_sheets uuid;
    v_decor_facade uuid;
    v_vodostok uuid;
    v_leaf_materials uuid;
    v_plywood uuid;
    v_hdf uuid;
    v_profiles_gkl uuid;
BEGIN
    -- Top-level canonical categories.
    INSERT INTO material_categories (id, parent_id, name, slug, description, status, level, sort_order, created_at, updated_at)
    SELECT gen_random_uuid(), NULL, 'Кровля', 'krovlya', NULL, 'ACTIVE', 0, 0, now(), now()
    WHERE NOT EXISTS (SELECT 1 FROM material_categories WHERE parent_id IS NULL AND name = 'Кровля');

    INSERT INTO material_categories (id, parent_id, name, slug, description, status, level, sort_order, created_at, updated_at)
    SELECT gen_random_uuid(), NULL, 'Электрика', 'elektrika', NULL, 'ACTIVE', 0, 0, now(), now()
    WHERE NOT EXISTS (SELECT 1 FROM material_categories WHERE parent_id IS NULL AND name = 'Электрика');

    INSERT INTO material_categories (id, parent_id, name, slug, description, status, level, sort_order, created_at, updated_at)
    SELECT gen_random_uuid(), NULL, 'Профили и комплектующие', 'profili-i-komplektuyuschie', NULL, 'ACTIVE', 0, 0, now(), now()
    WHERE NOT EXISTS (SELECT 1 FROM material_categories WHERE parent_id IS NULL AND name = 'Профили и комплектующие');

    UPDATE material_categories
    SET name = 'Тепло/Звукоизоляция',
        slug = 'teplo-zvukoizolyaciya',
        updated_at = now()
    WHERE parent_id IS NULL AND name = 'Теплоизоляция';

    UPDATE material_categories
    SET name = 'Фасад',
        slug = 'fasad',
        updated_at = now()
    WHERE parent_id IS NULL AND name = 'Фасады';

    SELECT id INTO v_roof FROM material_categories WHERE parent_id IS NULL AND name = 'Кровля' LIMIT 1;
    SELECT id INTO v_electric FROM material_categories WHERE parent_id IS NULL AND name = 'Электрика' LIMIT 1;
    SELECT id INTO v_sheet FROM material_categories WHERE parent_id IS NULL AND name = 'Листовые и плитные материалы' LIMIT 1;
    SELECT id INTO v_dry_mix FROM material_categories WHERE parent_id IS NULL AND name = 'Сухие смеси' LIMIT 1;
    SELECT id INTO v_wall FROM material_categories WHERE parent_id IS NULL AND name = 'Стеновые материалы' LIMIT 1;
    SELECT id INTO v_heat FROM material_categories WHERE parent_id IS NULL AND name = 'Тепло/Звукоизоляция' LIMIT 1;
    SELECT id INTO v_facade FROM material_categories WHERE parent_id IS NULL AND name = 'Фасад' LIMIT 1;
    SELECT id INTO v_profiles FROM material_categories WHERE parent_id IS NULL AND name = 'Профили и комплектующие' LIMIT 1;
    SELECT id INTO v_roof_water_old FROM material_categories WHERE parent_id IS NULL AND name = 'Кровля и водосток' LIMIT 1;
    SELECT id INTO v_electric_light_old FROM material_categories WHERE parent_id IS NULL AND name = 'Электрика и освещение' LIMIT 1;
    SELECT id INTO v_electro_goods_old FROM material_categories WHERE parent_id IS NULL AND name = 'Электротовары' LIMIT 1;
    SELECT id INTO v_dry_building FROM material_categories WHERE parent_id IS NULL AND name = 'Материалы для сухого строительства' LIMIT 1;
    SELECT id INTO v_building_old FROM material_categories WHERE parent_id IS NULL AND name = 'Строительные материалы' LIMIT 1;

    -- Safe merges of broad top-level containers.
    IF v_roof_water_old IS NOT NULL THEN
        UPDATE material_categories SET parent_id = v_roof, level = 1, updated_at = now() WHERE parent_id = v_roof_water_old;
        UPDATE materials SET category_id = v_roof WHERE category_id = v_roof_water_old;
        UPDATE materials SET subcategory_id = v_roof WHERE subcategory_id = v_roof_water_old;
        UPDATE material_categories SET status = 'ARCHIVED', description = concat_ws(E'\n', description, 'Merged into Кровля by Sprint 03 migration'), updated_at = now() WHERE id = v_roof_water_old;
    END IF;

    IF v_electric_light_old IS NOT NULL THEN
        UPDATE material_categories SET parent_id = v_electric, level = 1, updated_at = now() WHERE parent_id = v_electric_light_old;
        UPDATE materials SET category_id = v_electric WHERE category_id = v_electric_light_old;
        UPDATE material_categories SET status = 'ARCHIVED', description = concat_ws(E'\n', description, 'Merged into Электрика by Sprint 03 migration'), updated_at = now() WHERE id = v_electric_light_old;
    END IF;

    IF v_electro_goods_old IS NOT NULL THEN
        UPDATE material_categories SET parent_id = v_electric, level = 1, updated_at = now() WHERE parent_id = v_electro_goods_old;
        UPDATE materials SET category_id = v_electric WHERE category_id = v_electro_goods_old;
        UPDATE material_categories SET status = 'ARCHIVED', description = concat_ws(E'\n', description, 'Merged into Электрика by Sprint 03 migration'), updated_at = now() WHERE id = v_electro_goods_old;
    END IF;

    -- Required subcategories.
    INSERT INTO material_categories (id, parent_id, name, slug, description, status, level, sort_order, created_at, updated_at)
    SELECT gen_random_uuid(), v_wall, 'Лотковые блоки', 'lotkovye-bloki', 'Лотковые газобетонные блоки для армопояса', 'ACTIVE', 1, 0, now(), now()
    WHERE v_wall IS NOT NULL AND NOT EXISTS (SELECT 1 FROM material_categories WHERE parent_id = v_wall AND name = 'Лотковые блоки');

    INSERT INTO material_categories (id, parent_id, name, slug, description, status, level, sort_order, created_at, updated_at)
    SELECT gen_random_uuid(), v_roof, 'Водосток', 'vodostok', NULL, 'ACTIVE', 1, 0, now(), now()
    WHERE v_roof IS NOT NULL AND NOT EXISTS (SELECT 1 FROM material_categories WHERE parent_id = v_roof AND name = 'Водосток');

    SELECT id INTO v_tray_blocks FROM material_categories WHERE parent_id = v_wall AND name = 'Лотковые блоки' LIMIT 1;
    SELECT id INTO v_vodostok FROM material_categories WHERE parent_id = v_roof AND name = 'Водосток' LIMIT 1;
    SELECT id INTO v_osb FROM material_categories WHERE name = 'OSB' LIMIT 1;
    SELECT id INTO v_plywood FROM material_categories WHERE name = 'Фанера' LIMIT 1;
    SELECT id INTO v_hdf FROM material_categories WHERE name = 'ХДФ' LIMIT 1;
    SELECT id INTO v_xps FROM material_categories WHERE name = 'XPS' LIMIT 1;
    SELECT id INTO v_acoustic FROM material_categories WHERE name = 'Акустические плиты' LIMIT 1;
    SELECT id INTO v_gas_blocks FROM material_categories WHERE parent_id = v_wall AND name = 'Газобетонные блоки' LIMIT 1;
    SELECT id INTO v_gas_block_duplicate FROM material_categories WHERE parent_id = v_wall AND name = 'Газобетонный блок' LIMIT 1;
    SELECT id INTO v_flexible_shingles FROM material_categories WHERE name = 'Гибкая черепица' LIMIT 1;
    SELECT id INTO v_gkl FROM material_categories WHERE parent_id = v_sheet AND name = 'ГКЛ' LIMIT 1;
    SELECT id INTO v_gvl FROM material_categories WHERE parent_id = v_sheet AND name = 'ГВЛ' LIMIT 1;
    SELECT id INTO v_gypsum_sheets FROM material_categories WHERE name = 'Гипсовые листы' LIMIT 1;
    SELECT id INTO v_decor_facade FROM material_categories WHERE name IN ('Декоративные фасадные панели', 'Декоративные фасадные системы') LIMIT 1;
    SELECT id INTO v_leaf_materials FROM material_categories WHERE name = 'Листовые материалы' LIMIT 1;
    SELECT id INTO v_profiles_gkl FROM material_categories WHERE name = 'Профили для гипсокартона' LIMIT 1;

    -- Move/rename subcategories.
    UPDATE material_categories SET parent_id = v_sheet, level = 1, updated_at = now() WHERE id = v_osb;
    UPDATE material_categories SET parent_id = v_sheet, level = 1, updated_at = now() WHERE id IN (v_plywood, v_hdf);
    UPDATE material_categories SET parent_id = v_heat, level = 1, updated_at = now() WHERE id IN (v_xps, v_acoustic);
    UPDATE material_categories SET parent_id = v_roof, level = 1, updated_at = now() WHERE id = v_flexible_shingles;
    UPDATE material_categories SET parent_id = v_sheet, level = 1, updated_at = now() WHERE id = v_gypsum_sheets;
    UPDATE material_categories SET parent_id = v_sheet, level = 1, name = 'ГВЛ', slug = 'gvl', updated_at = now() WHERE name = 'Гипсоволокнистые листы';
    UPDATE material_categories SET parent_id = v_sheet, level = 1, name = 'ГКЛ', slug = 'gkl', updated_at = now() WHERE name = 'Гипсовые листовые материалы';
    UPDATE material_categories SET parent_id = v_facade, level = 1, name = 'Декоративные фасадные панели', slug = 'dekorativnye-fasadnye-paneli', updated_at = now() WHERE id = v_decor_facade;
    UPDATE material_categories SET parent_id = v_profiles, level = 1, updated_at = now() WHERE id = v_profiles_gkl;

    IF v_gas_block_duplicate IS NOT NULL AND v_gas_blocks IS NOT NULL THEN
        UPDATE materials SET subcategory_id = v_gas_blocks WHERE subcategory_id = v_gas_block_duplicate;
        UPDATE materials SET category_id = v_wall, subcategory_id = v_gas_blocks WHERE category_id = v_gas_block_duplicate;
        UPDATE material_categories SET status = 'ARCHIVED', description = concat_ws(E'\n', description, 'Merged into Газобетонные блоки by Sprint 03 migration'), updated_at = now() WHERE id = v_gas_block_duplicate;
    END IF;

    -- Category-specific material moves.
    UPDATE materials SET category_id = v_wall, subcategory_id = v_tray_blocks, canonical_name = regexp_replace(canonical_name, '^Газобетонный блок', 'Лотковый блок')
    WHERE canonical_name ILIKE '%500*400*250%' AND v_tray_blocks IS NOT NULL;

    UPDATE materials SET category_id = v_sheet, subcategory_id = v_osb WHERE subcategory_id = v_osb OR category_id = v_osb;
    UPDATE materials SET category_id = v_heat, subcategory_id = v_xps WHERE subcategory_id = v_xps OR category_id = v_xps;
    UPDATE materials SET category_id = v_heat, subcategory_id = v_acoustic WHERE subcategory_id = v_acoustic OR category_id = v_acoustic;
    UPDATE materials SET category_id = v_roof, subcategory_id = v_flexible_shingles WHERE subcategory_id = v_flexible_shingles OR category_id = v_flexible_shingles;
    UPDATE materials SET category_id = v_facade, subcategory_id = v_decor_facade WHERE subcategory_id = v_decor_facade OR category_id = v_decor_facade;
    UPDATE materials SET category_id = v_sheet, subcategory_id = v_leaf_materials WHERE category_id = v_leaf_materials AND v_leaf_materials IS NOT NULL;
    UPDATE materials SET category_id = v_sheet, subcategory_id = v_plywood WHERE canonical_name ILIKE '%фанер%' AND v_plywood IS NOT NULL;
    UPDATE materials SET category_id = v_sheet, subcategory_id = v_hdf WHERE canonical_name ILIKE '%хдф%' AND v_hdf IS NOT NULL;

    -- Split broad dry-building bucket by material name where we can do it safely.
    IF v_dry_building IS NOT NULL THEN
        UPDATE materials SET category_id = v_profiles, subcategory_id = v_profiles_gkl
        WHERE category_id = v_dry_building AND canonical_name ILIKE '%профил%' AND v_profiles_gkl IS NOT NULL;

        UPDATE materials SET category_id = v_heat, subcategory_id = v_acoustic
        WHERE category_id = v_dry_building AND canonical_name ILIKE '%акуст%' AND v_acoustic IS NOT NULL;

        UPDATE materials SET category_id = v_sheet, subcategory_id = COALESCE(v_gypsum_sheets, v_gkl)
        WHERE category_id = v_dry_building AND (canonical_name ILIKE '%лист%' OR canonical_name ILIKE '%гкл%' OR canonical_name ILIKE '%кнауф%');

        UPDATE materials SET category_id = NULL, subcategory_id = NULL, status = 'NEEDS_REVIEW'
        WHERE category_id = v_dry_building;

        UPDATE material_categories SET status = 'ARCHIVED', description = concat_ws(E'\n', description, 'Split into sheet materials, profiles, dry mixes and review queue by Sprint 03 migration'), updated_at = now()
        WHERE id = v_dry_building;
    END IF;

    IF v_building_old IS NOT NULL THEN
        UPDATE material_categories SET parent_id = v_sheet, level = 1, updated_at = now() WHERE parent_id = v_building_old AND name = 'Листовые материалы';
        UPDATE material_categories SET status = 'ARCHIVED', description = concat_ws(E'\n', description, 'Split by Sprint 03 migration'), updated_at = now() WHERE id = v_building_old;
    END IF;

    INSERT INTO audit_events (id, event_type, entity_type, entity_id, user_id, details, ip_address, created_at)
    VALUES (
        gen_random_uuid(),
        'category_hierarchy_migrated',
        'MaterialCategory',
        NULL,
        NULL,
        json_build_object('migration', '20260620_sprint03_category_hierarchy'),
        NULL,
        now()
    );
END $$;

COMMIT;
