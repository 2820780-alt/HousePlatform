-- Run with psql autocommit: PostgreSQL requires the new enum value to be committed before use.
ALTER TYPE unit_type ADD VALUE IF NOT EXISTS 'PRESSURE';

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM units WHERE abbreviation = 'mm' AND unit_type::text <> 'LENGTH') OR
       EXISTS (SELECT 1 FROM units WHERE abbreviation = 'kPa' AND unit_type::text <> 'PRESSURE') THEN
        RAISE EXCEPTION 'Existing unit has a conflicting dimension';
    END IF;
END $$;

INSERT INTO units (id, name, abbreviation, unit_type, is_base, created_at)
VALUES ('b4ee557d-3431-5995-bb40-09105c9c33d1', 'Миллиметр', 'mm', 'LENGTH', false, now()),
       ('758a4588-940e-5bf7-b07a-479f9abcb986', 'Килопаскаль', 'kPa', 'PRESSURE', false, now())
ON CONFLICT (abbreviation) DO NOTHING;

UPDATE material_attributes AS a
SET value_type = 'number', unit_id = u.id
FROM materials AS m, units AS u
WHERE m.id = a.material_id
  AND m.status::text NOT IN ('ARCHIVED', 'REJECTED')
  AND a.value_type = 'text' AND a.unit_id IS NULL
  AND a.attribute_value ~ '^\s*[0-9]+([.,][0-9]+)?\s*$'
  AND ((a.attribute_name IN ('thickness_mm', 'diameter_mm', 'height_mm', 'length_mm',
                             'width_mm', 'tube_diameter_mm', 'wall_thickness_mm',
                             'blade_diameter_mm', 'section_width_mm', 'section_height_mm')
        AND u.abbreviation = 'mm')
       OR (a.attribute_name = 'cs_10_y_kpa' AND u.abbreviation = 'kPa'));

UPDATE material_attributes AS a
SET value_type = 'class'
FROM materials AS m
WHERE m.id = a.material_id AND m.status::text NOT IN ('ARCHIVED', 'REJECTED')
  AND a.value_type = 'text' AND a.unit_id IS NULL
  AND ((a.attribute_name = 'concrete_class' AND a.attribute_value ~* '^[bв][0-9]+([.,][0-9]+)?$')
    OR (a.attribute_name = 'steel_class' AND a.attribute_value ~* '^[aа][0-9]+[a-zа-я]*$')
    OR (a.attribute_name = 'water_resistance' AND a.attribute_value ~* '^[wв][0-9]+$')
    OR (a.attribute_name = 'frost_type' AND a.attribute_value ~* '^[fф][0-9]+$')
    OR (a.attribute_name = 'mobility_class' AND a.attribute_value ~* '^[pп][0-9]+$'));

COMMIT;
