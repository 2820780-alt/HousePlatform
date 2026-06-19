-- Sprint 03 / Module 01
-- Prepare Knowledge Base candidates and material-bound unit conversion rules.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS knowledge_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid REFERENCES sources(id) ON DELETE SET NULL,
    material_id uuid REFERENCES materials(id) ON DELETE SET NULL,
    category_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    document_id uuid REFERENCES material_documents(id) ON DELETE SET NULL,
    candidate_type varchar(50) NOT NULL,
    title varchar(500) NOT NULL,
    extracted_text text,
    structured_data jsonb,
    source_url varchar(1000),
    confidence numeric(5, 4),
    status varchar(30) NOT NULL DEFAULT 'AUTO_EXTRACTED',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_source_id ON knowledge_candidates(source_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_material_id ON knowledge_candidates(material_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_category_id ON knowledge_candidates(category_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_document_id ON knowledge_candidates(document_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_candidate_type ON knowledge_candidates(candidate_type);
CREATE INDEX IF NOT EXISTS ix_knowledge_candidates_status ON knowledge_candidates(status);

CREATE TABLE IF NOT EXISTS unit_conversion_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id uuid REFERENCES materials(id) ON DELETE SET NULL,
    category_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    subcategory_id uuid REFERENCES material_categories(id) ON DELETE SET NULL,
    from_unit varchar(50) NOT NULL,
    to_unit varchar(50) NOT NULL,
    formula_type varchar(50) NOT NULL,
    formula jsonb,
    required_specifications jsonb,
    coefficient numeric(18, 8),
    source text,
    confidence numeric(5, 4),
    status varchar(30) NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_material_id ON unit_conversion_rules(material_id);
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_category_id ON unit_conversion_rules(category_id);
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_subcategory_id ON unit_conversion_rules(subcategory_id);
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_from_unit ON unit_conversion_rules(from_unit);
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_to_unit ON unit_conversion_rules(to_unit);
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_formula_type ON unit_conversion_rules(formula_type);
CREATE INDEX IF NOT EXISTS ix_unit_conversion_rules_status ON unit_conversion_rules(status);

DO $$
DECLARE
    v_lumber uuid;
    v_wall uuid;
    v_gas_blocks uuid;
    v_tray_blocks uuid;
    v_sheet uuid;
    v_osb uuid;
    v_gkl uuid;
    v_gvl uuid;
    v_gypsum uuid;
    v_dry_mix uuid;
    v_electric uuid;
    v_cable uuid;
    v_fasteners uuid;
BEGIN
    SELECT id INTO v_lumber FROM material_categories WHERE parent_id IS NULL AND name = 'Пиломатериалы' LIMIT 1;
    SELECT id INTO v_wall FROM material_categories WHERE parent_id IS NULL AND name = 'Стеновые материалы' LIMIT 1;
    SELECT id INTO v_sheet FROM material_categories WHERE parent_id IS NULL AND name = 'Листовые и плитные материалы' LIMIT 1;
    SELECT id INTO v_dry_mix FROM material_categories WHERE parent_id IS NULL AND name = 'Сухие смеси' LIMIT 1;
    SELECT id INTO v_electric FROM material_categories WHERE parent_id IS NULL AND name = 'Электрика' LIMIT 1;
    SELECT id INTO v_fasteners FROM material_categories WHERE parent_id IS NULL AND name = 'Крепеж' LIMIT 1;

    SELECT id INTO v_gas_blocks FROM material_categories WHERE parent_id = v_wall AND name = 'Газобетонные блоки' LIMIT 1;
    SELECT id INTO v_tray_blocks FROM material_categories WHERE parent_id = v_wall AND name = 'Лотковые блоки' LIMIT 1;
    SELECT id INTO v_osb FROM material_categories WHERE parent_id = v_sheet AND name = 'OSB' LIMIT 1;
    SELECT id INTO v_gkl FROM material_categories WHERE parent_id = v_sheet AND name = 'ГКЛ' LIMIT 1;
    SELECT id INTO v_gvl FROM material_categories WHERE parent_id = v_sheet AND name = 'ГВЛ' LIMIT 1;
    SELECT id INTO v_gypsum FROM material_categories WHERE parent_id = v_sheet AND name = 'Гипсовые листы' LIMIT 1;
    SELECT id INTO v_cable FROM material_categories WHERE parent_id = v_electric AND name IN ('Кабель и провод', 'Силовой кабель', 'Кабель') LIMIT 1;

    IF v_lumber IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_lumber, 'шт', 'м3', 'PIECE_TO_VOLUME',
            jsonb_build_object('description', 'толщина_m * ширина_m * длина_m * количество_шт'),
            '["thickness", "width", "length"]'::jsonb,
            'Sprint 03 MVP rule: lumber pieces to cubic meters',
            0.9000,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE category_id = v_lumber AND subcategory_id IS NULL AND from_unit = 'шт' AND to_unit = 'м3' AND formula_type = 'PIECE_TO_VOLUME'
        );
    END IF;

    IF v_gas_blocks IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, subcategory_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_wall, v_gas_blocks, 'шт', 'м3', 'PIECE_TO_VOLUME',
            jsonb_build_object('description', 'длина_m * ширина_m * высота_m * количество_шт'),
            '["length", "width", "height"]'::jsonb,
            'Sprint 03 MVP rule: aerated concrete blocks to cubic meters',
            0.9000,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE subcategory_id = v_gas_blocks AND from_unit = 'шт' AND to_unit = 'м3' AND formula_type = 'PIECE_TO_VOLUME'
        );
    END IF;

    IF v_tray_blocks IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, subcategory_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_wall, v_tray_blocks, 'шт', 'м3', 'PIECE_TO_VOLUME',
            jsonb_build_object('description', 'длина_m * ширина_m * высота_m * количество_шт'),
            '["length", "width", "height"]'::jsonb,
            'Sprint 03 MVP rule: tray blocks to cubic meters',
            0.8500,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE subcategory_id = v_tray_blocks AND from_unit = 'шт' AND to_unit = 'м3' AND formula_type = 'PIECE_TO_VOLUME'
        );
    END IF;

    IF v_osb IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, subcategory_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_sheet, v_osb, 'лист', 'м2', 'PIECE_TO_AREA',
            jsonb_build_object('description', 'длина_m * ширина_m * количество_листов'),
            '["length", "width"]'::jsonb,
            'Sprint 03 MVP rule: OSB sheets to square meters',
            0.9000,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE subcategory_id = v_osb AND from_unit = 'лист' AND to_unit = 'м2' AND formula_type = 'PIECE_TO_AREA'
        );
    END IF;

    INSERT INTO unit_conversion_rules (
        id, category_id, subcategory_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
    )
    SELECT gen_random_uuid(), v_sheet, subcategory_id, 'лист', 'м2', 'PIECE_TO_AREA',
        jsonb_build_object('description', 'длина_m * ширина_m * количество_листов'),
        '["length", "width"]'::jsonb,
        'Sprint 03 MVP rule: gypsum sheets to square meters',
        0.8500,
        'NEEDS_REVIEW',
        now(),
        now()
    FROM (VALUES (v_gkl), (v_gvl), (v_gypsum)) AS sheet_rules(subcategory_id)
    WHERE subcategory_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM unit_conversion_rules
          WHERE unit_conversion_rules.subcategory_id = sheet_rules.subcategory_id
            AND from_unit = 'лист'
            AND to_unit = 'м2'
            AND formula_type = 'PIECE_TO_AREA'
      );

    IF v_dry_mix IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_dry_mix, 'мешок', 'кг', 'PACKAGE_TO_UNIT',
            jsonb_build_object('description', 'вес_мешка_кг * количество_мешков'),
            '["package_weight"]'::jsonb,
            'Sprint 03 MVP rule: dry mix bags to kilograms',
            0.9000,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE category_id = v_dry_mix AND subcategory_id IS NULL AND from_unit = 'мешок' AND to_unit = 'кг' AND formula_type = 'PACKAGE_TO_UNIT'
        );
    END IF;

    IF v_cable IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, subcategory_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_electric, v_cable, 'бухта', 'м', 'PACKAGE_TO_UNIT',
            jsonb_build_object('description', 'длина_бухты_м * количество_бухт'),
            '["roll_length"]'::jsonb,
            'Sprint 03 MVP rule: cable coil to meters',
            0.8000,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE subcategory_id = v_cable AND from_unit = 'бухта' AND to_unit = 'м' AND formula_type = 'PACKAGE_TO_UNIT'
        );
    END IF;

    IF v_fasteners IS NOT NULL THEN
        INSERT INTO unit_conversion_rules (
            id, category_id, from_unit, to_unit, formula_type, formula, required_specifications, source, confidence, status, created_at, updated_at
        )
        SELECT gen_random_uuid(), v_fasteners, 'кг', 'шт', 'WEIGHT_TO_PIECE',
            jsonb_build_object('description', 'масса_кг / вес_одной_штуки_кг'),
            '["single_piece_weight"]'::jsonb,
            'Sprint 03 MVP rule: fastener weight to pieces only with confirmed piece weight',
            0.7500,
            'NEEDS_REVIEW',
            now(),
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM unit_conversion_rules
            WHERE category_id = v_fasteners AND subcategory_id IS NULL AND from_unit = 'кг' AND to_unit = 'шт' AND formula_type = 'WEIGHT_TO_PIECE'
        );
    END IF;

    INSERT INTO audit_events (id, event_type, entity_type, entity_id, user_id, details, ip_address, created_at)
    VALUES (
        gen_random_uuid(),
        'knowledge_and_conversion_prepared',
        'MaterialHub',
        NULL,
        NULL,
        json_build_object('migration', '20260620_sprint03_knowledge_and_conversion'),
        NULL,
        now()
    );
END $$;

COMMIT;
