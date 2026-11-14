-- Persistent backing for the existing M1 work codes and append-only manual prices.
-- The approved work seed is imported separately through the guarded M1 service.
BEGIN;

CREATE TABLE IF NOT EXISTS module1_work_items (
    work_code varchar(120) PRIMARY KEY,
    work_group varchar(120) NOT NULL,
    work_category varchar(255) NOT NULL,
    work_name varchar(500) NOT NULL,
    default_unit varchar(50) NOT NULL,
    allowed_units json NOT NULL,
    is_range_allowed boolean NOT NULL,
    applies_to varchar(30) NOT NULL,
    module2_usage_hint varchar(255),
    module5_usage_hint varchar(255),
    description text,
    conditions json NOT NULL DEFAULT '{}',
    catalog_order integer NOT NULL DEFAULT 0,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    version integer NOT NULL DEFAULT 1,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ck_m1_work_item_status CHECK (status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')),
    CONSTRAINT ck_m1_work_item_version CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS module1_work_item_revisions (
    id uuid PRIMARY KEY,
    work_code varchar(120) NOT NULL REFERENCES module1_work_items(work_code) ON DELETE RESTRICT,
    version integer NOT NULL,
    snapshot json NOT NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_m1_work_item_revision UNIQUE (work_code, version)
);
CREATE INDEX IF NOT EXISTS ix_module1_work_item_revisions_work_code ON module1_work_item_revisions(work_code);

CREATE TABLE IF NOT EXISTS module1_manual_price_revisions (
    id uuid PRIMARY KEY,
    material_id uuid REFERENCES materials(id) ON DELETE RESTRICT,
    work_code varchar(120) REFERENCES module1_work_items(work_code) ON DELETE RESTRICT,
    amount numeric(18,4),
    currency varchar(10) NOT NULL,
    unit varchar(50) NOT NULL,
    region varchar(255) NOT NULL,
    terms varchar(255) NOT NULL,
    effective_from date NOT NULL,
    version integer NOT NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT ck_m1_manual_price_owner CHECK (
        (material_id IS NOT NULL AND work_code IS NULL) OR
        (material_id IS NULL AND work_code IS NOT NULL)),
    CONSTRAINT ck_m1_manual_price_positive CHECK (amount IS NULL OR amount > 0),
    CONSTRAINT ck_m1_manual_price_version CHECK (version >= 1)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_m1_manual_price_material_revision
    ON module1_manual_price_revisions(material_id, currency, unit, region, terms, version)
    WHERE material_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_m1_manual_price_work_revision
    ON module1_manual_price_revisions(work_code, currency, unit, region, terms, version)
    WHERE work_code IS NOT NULL;

COMMIT;
