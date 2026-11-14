-- Additive storage for independent M2 calculation blocks and template versions.
-- No technologies, materials, prices or existing links are changed.
BEGIN;

CREATE TABLE IF NOT EXISTS module2_calculation_block_templates (
    id uuid PRIMARY KEY,
    template_key varchar(120) NOT NULL,
    version integer NOT NULL,
    name varchar(255) NOT NULL,
    description text,
    definition json NOT NULL,
    material_id uuid REFERENCES materials(id) ON DELETE RESTRICT,
    work_code varchar(120),
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_m2_block_template_key_version UNIQUE (template_key, version),
    CONSTRAINT ck_m2_block_template_version CHECK (version >= 1)
);

CREATE INDEX IF NOT EXISTS ix_module2_calculation_block_templates_template_key
    ON module2_calculation_block_templates(template_key);

CREATE TABLE IF NOT EXISTS module2_calculation_blocks (
    id uuid PRIMARY KEY,
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    template_id uuid REFERENCES module2_calculation_block_templates(id) ON DELETE RESTRICT,
    name varchar(255) NOT NULL,
    position integer NOT NULL,
    version integer NOT NULL DEFAULT 1,
    definition json NOT NULL,
    material_id uuid REFERENCES materials(id) ON DELETE RESTRICT,
    work_code varchar(120),
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_m2_calculation_block_position UNIQUE (technology_id, position),
    CONSTRAINT ck_m2_calculation_block_position CHECK (position >= 1),
    CONSTRAINT ck_m2_calculation_block_version CHECK (version >= 1)
);

CREATE INDEX IF NOT EXISTS ix_module2_calculation_blocks_technology_id
    ON module2_calculation_blocks(technology_id);

COMMIT;
