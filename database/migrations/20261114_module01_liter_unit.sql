BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM units WHERE abbreviation = 'liter' AND unit_type::text <> 'VOLUME') THEN
        RAISE EXCEPTION 'Existing liter unit has a conflicting dimension';
    END IF;
END $$;

INSERT INTO units (id, name, abbreviation, unit_type, is_base, created_at)
VALUES ('b225ebc7-113e-4bdb-af5c-2201b28e080d', 'Литр', 'liter', 'VOLUME', false, now())
ON CONFLICT (abbreviation) DO NOTHING;

COMMIT;
