-- Module 02 / Evidence, Consumption Norms and Knowledge Rules
-- Additive only. Do not apply to the live HousePlatform database during Sprint 2.3-2.4.

BEGIN;

CREATE TABLE IF NOT EXISTS module2_consumption_norms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL
        REFERENCES module2_technologies(id) ON DELETE CASCADE,
    norm_code varchar(120) NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    scope_layer_id uuid
        REFERENCES module2_technology_layers(id) ON DELETE SET NULL,
    scope_requirement_id uuid
        REFERENCES module2_technology_material_requirements(id) ON DELETE SET NULL,
    scope_work_step_id uuid
        REFERENCES module2_technology_work_steps(id) ON DELETE SET NULL,
    resource_kind varchar(40) NOT NULL,
    resource_selector jsonb NOT NULL,
    basis_quantity numeric(18, 6) NOT NULL,
    basis_unit varchar(20) NOT NULL,
    consumption_quantity numeric(18, 6) NOT NULL,
    consumption_unit varchar(20) NOT NULL,
    conditions jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    owner_module_code varchar(120) NOT NULL DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    source_kind varchar(40) NOT NULL DEFAULT 'HUMAN_CURATED',
    blockers jsonb NOT NULL DEFAULT '[]'::jsonb,
    supersedes_id uuid
        REFERENCES module2_consumption_norms(id) ON DELETE SET NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_module2_consumption_norm_revision
        UNIQUE (technology_id, norm_code, revision),
    CONSTRAINT ck_module2_consumption_norm_revision CHECK (revision >= 1),
    CONSTRAINT ck_module2_consumption_norm_basis CHECK (basis_quantity > 0),
    CONSTRAINT ck_module2_consumption_norm_quantity
        CHECK (consumption_quantity > 0),
    CONSTRAINT ck_module2_consumption_norm_resource_kind CHECK (
        resource_kind IN (
            'CANONICAL_MATERIAL',
            'MATERIAL_CLASS',
            'MATERIAL_REQUIREMENT',
            'TECHNICAL_CONSTRAINTS',
            'ROLE'
        )
    ),
    CONSTRAINT ck_module2_consumption_norm_status CHECK (
        status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')
    )
);

CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_technology_id
    ON module2_consumption_norms(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_status
    ON module2_consumption_norms(status);
CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_scope_layer_id
    ON module2_consumption_norms(scope_layer_id);
CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_scope_requirement_id
    ON module2_consumption_norms(scope_requirement_id);
CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_scope_work_step_id
    ON module2_consumption_norms(scope_work_step_id);
CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_supersedes_id
    ON module2_consumption_norms(supersedes_id);
CREATE INDEX IF NOT EXISTS ix_module2_consumption_norms_created_by_user_id
    ON module2_consumption_norms(created_by_user_id);

CREATE TABLE IF NOT EXISTS module2_compatibility_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL
        REFERENCES module2_technologies(id) ON DELETE CASCADE,
    rule_code varchar(120) NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    subject_kind varchar(40) NOT NULL,
    subject_selector jsonb NOT NULL,
    object_kind varchar(40) NOT NULL,
    object_selector jsonb NOT NULL,
    relation varchar(30) NOT NULL,
    conditions jsonb NOT NULL DEFAULT '[]'::jsonb,
    reason text,
    is_symmetric boolean NOT NULL DEFAULT true,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    owner_module_code varchar(120) NOT NULL DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    source_kind varchar(40) NOT NULL DEFAULT 'HUMAN_CURATED',
    blockers jsonb NOT NULL DEFAULT '[]'::jsonb,
    supersedes_id uuid
        REFERENCES module2_compatibility_rules(id) ON DELETE SET NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_module2_compatibility_rule_revision
        UNIQUE (technology_id, rule_code, revision),
    CONSTRAINT ck_module2_compatibility_rule_revision CHECK (revision >= 1),
    CONSTRAINT ck_module2_compatibility_subject_kind CHECK (
        subject_kind IN (
            'CANONICAL_MATERIAL', 'MATERIAL_CLASS', 'MATERIAL_REQUIREMENT',
            'TECHNICAL_CONSTRAINTS', 'ROLE'
        )
    ),
    CONSTRAINT ck_module2_compatibility_object_kind CHECK (
        object_kind IN (
            'CANONICAL_MATERIAL', 'MATERIAL_CLASS', 'MATERIAL_REQUIREMENT',
            'TECHNICAL_CONSTRAINTS', 'ROLE'
        )
    ),
    CONSTRAINT ck_module2_compatibility_relation CHECK (
        relation IN ('COMPATIBLE', 'INCOMPATIBLE', 'CONDITIONAL', 'UNKNOWN')
    ),
    CONSTRAINT ck_module2_compatibility_status CHECK (
        status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')
    )
);

CREATE INDEX IF NOT EXISTS ix_module2_compatibility_rules_technology_id
    ON module2_compatibility_rules(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_compatibility_rules_status
    ON module2_compatibility_rules(status);
CREATE INDEX IF NOT EXISTS ix_module2_compatibility_rules_supersedes_id
    ON module2_compatibility_rules(supersedes_id);
CREATE INDEX IF NOT EXISTS ix_module2_compatibility_rules_created_by_user_id
    ON module2_compatibility_rules(created_by_user_id);

CREATE TABLE IF NOT EXISTS module2_knowledge_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL
        REFERENCES module2_technologies(id) ON DELETE CASCADE,
    rule_code varchar(120) NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    scope_kind varchar(40) NOT NULL,
    scope_reference varchar(120),
    conditions jsonb NOT NULL,
    outcome_type varchar(30) NOT NULL,
    outcome_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(30) NOT NULL DEFAULT 'DRAFT',
    owner_module_code varchar(120) NOT NULL DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    source_kind varchar(40) NOT NULL DEFAULT 'HUMAN_CURATED',
    blockers jsonb NOT NULL DEFAULT '[]'::jsonb,
    supersedes_id uuid
        REFERENCES module2_knowledge_rules(id) ON DELETE SET NULL,
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    updated_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_module2_knowledge_rule_revision
        UNIQUE (technology_id, rule_code, revision),
    CONSTRAINT ck_module2_knowledge_rule_revision CHECK (revision >= 1),
    CONSTRAINT ck_module2_knowledge_rule_scope_kind CHECK (
        scope_kind IN (
            'TECHNOLOGY', 'LAYER', 'MATERIAL_REQUIREMENT', 'NODE', 'WORK_STEP',
            'CONSUMPTION_NORM', 'COMPATIBILITY_RULE'
        )
    ),
    CONSTRAINT ck_module2_knowledge_rule_scope_reference CHECK (
        scope_kind = 'TECHNOLOGY' OR scope_reference IS NOT NULL
    ),
    CONSTRAINT ck_module2_knowledge_rule_outcome CHECK (
        outcome_type IN (
            'REQUIREMENT',
            'WARNING',
            'PROHIBITION',
            'CONSTRAINT',
            'INFORMATION'
        )
    ),
    CONSTRAINT ck_module2_knowledge_rule_status CHECK (
        status IN ('DRAFT', 'REVIEW', 'ACTIVE', 'ARCHIVED')
    )
);

CREATE INDEX IF NOT EXISTS ix_module2_knowledge_rules_technology_id
    ON module2_knowledge_rules(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_knowledge_rules_status
    ON module2_knowledge_rules(status);
CREATE INDEX IF NOT EXISTS ix_module2_knowledge_rules_supersedes_id
    ON module2_knowledge_rules(supersedes_id);
CREATE INDEX IF NOT EXISTS ix_module2_knowledge_rules_created_by_user_id
    ON module2_knowledge_rules(created_by_user_id);

DO $module2_evidence_constraints$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_module2_evidence_target_kind'
    ) THEN
        ALTER TABLE module2_technology_evidence_references
            ADD CONSTRAINT ck_module2_evidence_target_kind CHECK (
                target_kind IN (
                    'TECHNOLOGY',
                    'LAYER',
                    'MATERIAL_REQUIREMENT',
                    'NODE',
                    'WORK_STEP',
                    'CONSUMPTION_NORM',
                    'COMPATIBILITY_RULE',
                    'KNOWLEDGE_RULE'
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_module2_evidence_target_reference'
    ) THEN
        ALTER TABLE module2_technology_evidence_references
            ADD CONSTRAINT ck_module2_evidence_target_reference CHECK (
                target_kind = 'TECHNOLOGY' OR target_reference IS NOT NULL
            );
    END IF;
END
$module2_evidence_constraints$;

COMMIT;

-- Manual rollback, only when explicitly approved and after dependency review:
-- ALTER TABLE module2_technology_evidence_references
--     DROP CONSTRAINT ck_module2_evidence_target_reference;
-- ALTER TABLE module2_technology_evidence_references
--     DROP CONSTRAINT ck_module2_evidence_target_kind;
-- DROP TABLE module2_knowledge_rules;
-- DROP TABLE module2_compatibility_rules;
-- DROP TABLE module2_consumption_norms;
