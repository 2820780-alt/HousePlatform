-- M2 content catalog foundation. No category or technology content is seeded.
BEGIN;

CREATE TABLE IF NOT EXISTS module2_technology_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(120) NOT NULL,
    parent_id uuid REFERENCES module2_technology_categories(id) ON DELETE RESTRICT,
    name varchar(255) NOT NULL,
    description text,
    sort_order integer NOT NULL DEFAULT 0,
    scope_code varchar(80) NOT NULL DEFAULT 'RESIDENTIAL',
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    content_status varchar(30) NOT NULL DEFAULT 'EMPTY',
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ck_module2_category_status
        CHECK (status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')),
    CONSTRAINT ck_module2_category_content_status
        CHECK (content_status IN ('EMPTY', 'IN_PROGRESS', 'CONTENT_COMPLETE')),
    CONSTRAINT ck_module2_category_sort_order CHECK (sort_order >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_module2_technology_categories_code
    ON module2_technology_categories(code);
CREATE INDEX IF NOT EXISTS ix_module2_technology_categories_parent_id
    ON module2_technology_categories(parent_id);
CREATE INDEX IF NOT EXISTS ix_module2_technology_categories_status
    ON module2_technology_categories(status);

ALTER TABLE module2_technologies ADD COLUMN IF NOT EXISTS category_id uuid;
DO $module2_category_fk$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_module2_technologies_category_id'
    ) THEN
        ALTER TABLE module2_technologies
            ADD CONSTRAINT fk_module2_technologies_category_id
            FOREIGN KEY (category_id) REFERENCES module2_technology_categories(id)
            ON DELETE RESTRICT;
    END IF;
END
$module2_category_fk$;

CREATE INDEX IF NOT EXISTS ix_module2_technologies_category_id
    ON module2_technologies(category_id);

COMMENT ON TABLE module2_technology_categories IS
    'M2 draft taxonomy; no production categories until product approval';

COMMIT;
