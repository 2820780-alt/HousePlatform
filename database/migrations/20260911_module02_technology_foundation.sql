-- Module 02 / Technology Domain Foundation
-- Additive only. This migration is not applied automatically by Sprint 2.1-2.2.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS module2_technologies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_code varchar(120) NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    name varchar(255) NOT NULL,
    description text,
    system_code varchar(120),
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    owner_module_code varchar(120) NOT NULL DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    source_kind varchar(40) NOT NULL DEFAULT 'HUMAN_CURATED',
    input_missing_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
    input_blockers jsonb NOT NULL DEFAULT '[]'::jsonb,
    supersedes_id uuid REFERENCES module2_technologies(id) ON DELETE SET NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_module2_technology_code_revision UNIQUE (technology_code, revision),
    CONSTRAINT ck_module2_technology_revision_positive CHECK (revision >= 1),
    CONSTRAINT ck_module2_technology_status
        CHECK (status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED'))
);

CREATE INDEX IF NOT EXISTS ix_module2_technologies_technology_code
    ON module2_technologies(technology_code);
CREATE INDEX IF NOT EXISTS ix_module2_technologies_system_code
    ON module2_technologies(system_code);
CREATE INDEX IF NOT EXISTS ix_module2_technologies_status
    ON module2_technologies(status);
CREATE INDEX IF NOT EXISTS ix_module2_technologies_supersedes_id
    ON module2_technologies(supersedes_id);
CREATE INDEX IF NOT EXISTS ix_module2_technologies_created_by_user_id
    ON module2_technologies(created_by_user_id);

CREATE TABLE IF NOT EXISTS module2_technology_material_requirements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    code varchar(120) NOT NULL,
    selector_kind varchar(40) NOT NULL,
    material_role_code varchar(120),
    canonical_material_id uuid REFERENCES materials(id) ON DELETE RESTRICT,
    material_category_id uuid REFERENCES material_categories(id) ON DELETE RESTRICT,
    material_type_id uuid REFERENCES material_types(id) ON DELETE RESTRICT,
    technical_constraints jsonb NOT NULL DEFAULT '{}'::jsonb,
    notes text,
    CONSTRAINT uq_module2_requirement_code UNIQUE (technology_id, code),
    CONSTRAINT ck_module2_requirement_selector_kind CHECK (
        selector_kind IN (
            'CANONICAL_MATERIAL',
            'MATERIAL_CLASS',
            'TECHNICAL_CONSTRAINTS',
            'ROLE'
        )
    )
);

CREATE INDEX IF NOT EXISTS ix_module2_requirement_technology_id
    ON module2_technology_material_requirements(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_requirement_canonical_material_id
    ON module2_technology_material_requirements(canonical_material_id);
CREATE INDEX IF NOT EXISTS ix_module2_requirement_material_category_id
    ON module2_technology_material_requirements(material_category_id);
CREATE INDEX IF NOT EXISTS ix_module2_requirement_material_type_id
    ON module2_technology_material_requirements(material_type_id);

CREATE TABLE IF NOT EXISTS module2_technology_layers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    position integer NOT NULL,
    functional_role varchar(120) NOT NULL,
    material_requirement_id uuid
        REFERENCES module2_technology_material_requirements(id) ON DELETE RESTRICT,
    thickness_expression varchar(500),
    is_mandatory boolean NOT NULL DEFAULT true,
    notes text,
    restrictions jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_module2_layer_position UNIQUE (technology_id, position),
    CONSTRAINT ck_module2_layer_position_positive CHECK (position >= 1)
);

CREATE INDEX IF NOT EXISTS ix_module2_layer_technology_id
    ON module2_technology_layers(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_layer_material_requirement_id
    ON module2_technology_layers(material_requirement_id);

CREATE TABLE IF NOT EXISTS module2_technology_nodes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    code varchar(120) NOT NULL,
    node_type varchar(80) NOT NULL,
    name varchar(255) NOT NULL,
    description text,
    conditions jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_module2_node_code UNIQUE (technology_id, code)
);

CREATE INDEX IF NOT EXISTS ix_module2_node_technology_id
    ON module2_technology_nodes(technology_id);

CREATE TABLE IF NOT EXISTS module2_technology_work_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    position integer NOT NULL,
    work_code varchar(120) NOT NULL,
    applicability_expression text,
    dependency_step_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
    instructions text,
    CONSTRAINT uq_module2_work_step_position UNIQUE (technology_id, position),
    CONSTRAINT ck_module2_work_step_position_positive CHECK (position >= 1)
);

CREATE INDEX IF NOT EXISTS ix_module2_work_step_technology_id
    ON module2_technology_work_steps(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_work_step_work_code
    ON module2_technology_work_steps(work_code);

CREATE TABLE IF NOT EXISTS module2_technology_evidence_references (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    document_id uuid REFERENCES material_documents(id) ON DELETE RESTRICT,
    knowledge_resource_id uuid REFERENCES knowledge_resources(id) ON DELETE RESTRICT,
    target_kind varchar(40) NOT NULL DEFAULT 'TECHNOLOGY',
    target_reference varchar(120),
    interpretation text,
    CONSTRAINT ck_module2_evidence_exactly_one_reference CHECK (
        (document_id IS NOT NULL AND knowledge_resource_id IS NULL)
        OR (document_id IS NULL AND knowledge_resource_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_module2_evidence_technology_id
    ON module2_technology_evidence_references(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_evidence_document_id
    ON module2_technology_evidence_references(document_id);
CREATE INDEX IF NOT EXISTS ix_module2_evidence_knowledge_resource_id
    ON module2_technology_evidence_references(knowledge_resource_id);

COMMIT;

-- Manual rollback, only when explicitly approved and after dependency review:
-- DROP TABLE module2_technology_evidence_references;
-- DROP TABLE module2_technology_work_steps;
-- DROP TABLE module2_technology_nodes;
-- DROP TABLE module2_technology_layers;
-- DROP TABLE module2_technology_material_requirements;
-- DROP TABLE module2_technologies;
