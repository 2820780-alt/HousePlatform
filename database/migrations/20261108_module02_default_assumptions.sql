-- A2.1: additive, revisioned M2 defaults. No M1/M3 schema or data changes.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-default-assumptions'));

CREATE TABLE IF NOT EXISTS module2_technology_default_assumptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
    assumption_code varchar(120) NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    parameter_code varchar(120) NOT NULL,
    name_ru varchar(255) NOT NULL,
    value_type varchar(30) NOT NULL,
    unit varchar(40),
    default_value jsonb NOT NULL,
    source_kind varchar(40) NOT NULL,
    applicability jsonb NOT NULL DEFAULT '{}'::jsonb,
    auto_fallback boolean NOT NULL DEFAULT false,
    warning_level varchar(20) NOT NULL DEFAULT 'WARNING',
    warning_text text,
    allowed_values_strategy varchar(40) NOT NULL,
    allowed_values jsonb NOT NULL DEFAULT '{}'::jsonb,
    material_requirement_id uuid REFERENCES module2_technology_material_requirements(id) ON DELETE RESTRICT,
    evidence_reference_id uuid REFERENCES module2_technology_evidence_references(id) ON DELETE RESTRICT,
    status varchar(20) NOT NULL DEFAULT 'ACTIVE',
    created_by_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamp without time zone NOT NULL DEFAULT now(),
    CONSTRAINT uq_module2_default_revision UNIQUE (technology_id, assumption_code, revision),
    CONSTRAINT ck_module2_default_revision_positive CHECK (revision >= 1),
    CONSTRAINT ck_module2_default_value_type CHECK (value_type IN ('NUMBER', 'MATERIAL', 'MATERIAL_CLASS', 'ENUM', 'BOOLEAN', 'TEXT')),
    CONSTRAINT ck_module2_default_source_kind CHECK (source_kind IN ('EVIDENCE_BACKED_TYPICAL', 'PLATFORM_ASSUMPTION')),
    CONSTRAINT ck_module2_default_status CHECK (status IN ('ACTIVE', 'SUPERSEDED')),
    CONSTRAINT ck_module2_default_warning_level CHECK (warning_level IN ('INFO', 'WARNING', 'CRITICAL'))
);
CREATE INDEX IF NOT EXISTS ix_module2_technology_default_assumptions_technology_id
    ON module2_technology_default_assumptions(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_technology_default_assumptions_material_requirement_id
    ON module2_technology_default_assumptions(material_requirement_id);
CREATE INDEX IF NOT EXISTS ix_module2_technology_default_assumptions_evidence_reference_id
    ON module2_technology_default_assumptions(evidence_reference_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_module2_default_active
    ON module2_technology_default_assumptions(technology_id, assumption_code)
    WHERE status = 'ACTIVE';
CREATE UNIQUE INDEX IF NOT EXISTS uq_module2_default_active_parameter
    ON module2_technology_default_assumptions(technology_id, parameter_code)
    WHERE status = 'ACTIVE';
COMMIT;
