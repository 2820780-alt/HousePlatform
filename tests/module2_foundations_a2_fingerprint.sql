-- Run read-only on both the live database and its restored dry-run copy.
-- Compare the live multiset of hashes with the dry-run multiset per table.
CREATE TEMP TABLE a2_fingerprint (
    table_name text NOT NULL,
    row_hash text NOT NULL
);

DO $audit$
DECLARE
    item record;
    row_expression text;
BEGIN
    FOR item IN SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' ORDER BY tablename
    LOOP
        row_expression := CASE item.tablename
            WHEN 'module2_technologies' THEN 'to_jsonb(t) - ''status'''
            WHEN 'module2_technology_categories' THEN 'to_jsonb(t) - ''content_status'''
            ELSE 'to_jsonb(t)'
        END;
        EXECUTE format(
            'INSERT INTO a2_fingerprint SELECT %L, md5((%s)::text) FROM %I t',
            item.tablename, row_expression, item.tablename
        );
    END LOOP;
END
$audit$;

SELECT table_name, row_hash FROM a2_fingerprint ORDER BY table_name, row_hash;
