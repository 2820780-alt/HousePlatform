-- Reconcile M2 tables created by the former application startup with the
-- canonical 20260911/20260913 migrations. Run only after those migrations.
BEGIN;

DO $module2_empty_schema$
DECLARE
    table_name text;
    row_count bigint;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'module2_technologies', 'module2_technology_material_requirements',
        'module2_technology_layers', 'module2_technology_nodes',
        'module2_technology_work_steps', 'module2_technology_evidence_references',
        'module2_consumption_norms', 'module2_compatibility_rules',
        'module2_knowledge_rules'
    ] LOOP
        EXECUTE format('SELECT count(*) FROM %I', table_name) INTO row_count;
        IF row_count <> 0 THEN
            RAISE EXCEPTION 'M2 schema reconciliation requires empty table: %', table_name;
        END IF;
    END LOOP;
END
$module2_empty_schema$;

ALTER TABLE module2_technologies
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN revision SET DEFAULT 1,
    ALTER COLUMN status SET DEFAULT 'DRAFT',
    ALTER COLUMN owner_module_code SET DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    ALTER COLUMN source_kind SET DEFAULT 'HUMAN_CURATED',
    ALTER COLUMN input_missing_fields TYPE jsonb USING input_missing_fields::jsonb,
    ALTER COLUMN input_missing_fields SET DEFAULT '[]'::jsonb,
    ALTER COLUMN input_blockers TYPE jsonb USING input_blockers::jsonb,
    ALTER COLUMN input_blockers SET DEFAULT '[]'::jsonb,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE module2_technology_material_requirements
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN technical_constraints TYPE jsonb USING technical_constraints::jsonb,
    ALTER COLUMN technical_constraints SET DEFAULT '{}'::jsonb;

ALTER TABLE module2_technology_layers
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN is_mandatory SET DEFAULT true,
    ALTER COLUMN restrictions TYPE jsonb USING restrictions::jsonb,
    ALTER COLUMN restrictions SET DEFAULT '{}'::jsonb;

ALTER TABLE module2_technology_nodes
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN conditions TYPE jsonb USING conditions::jsonb,
    ALTER COLUMN conditions SET DEFAULT '{}'::jsonb;

ALTER TABLE module2_technology_work_steps
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN dependency_step_codes TYPE jsonb USING dependency_step_codes::jsonb,
    ALTER COLUMN dependency_step_codes SET DEFAULT '[]'::jsonb;

ALTER TABLE module2_technology_evidence_references
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN target_kind SET DEFAULT 'TECHNOLOGY';

ALTER TABLE module2_consumption_norms
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN revision SET DEFAULT 1,
    ALTER COLUMN resource_selector TYPE jsonb USING resource_selector::jsonb,
    ALTER COLUMN conditions TYPE jsonb USING conditions::jsonb,
    ALTER COLUMN conditions SET DEFAULT '[]'::jsonb,
    ALTER COLUMN status SET DEFAULT 'DRAFT',
    ALTER COLUMN owner_module_code SET DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    ALTER COLUMN source_kind SET DEFAULT 'HUMAN_CURATED',
    ALTER COLUMN blockers TYPE jsonb USING blockers::jsonb,
    ALTER COLUMN blockers SET DEFAULT '[]'::jsonb,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE module2_compatibility_rules
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN revision SET DEFAULT 1,
    ALTER COLUMN subject_selector TYPE jsonb USING subject_selector::jsonb,
    ALTER COLUMN object_selector TYPE jsonb USING object_selector::jsonb,
    ALTER COLUMN conditions TYPE jsonb USING conditions::jsonb,
    ALTER COLUMN conditions SET DEFAULT '[]'::jsonb,
    ALTER COLUMN is_symmetric SET DEFAULT true,
    ALTER COLUMN status SET DEFAULT 'DRAFT',
    ALTER COLUMN owner_module_code SET DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    ALTER COLUMN source_kind SET DEFAULT 'HUMAN_CURATED',
    ALTER COLUMN blockers TYPE jsonb USING blockers::jsonb,
    ALTER COLUMN blockers SET DEFAULT '[]'::jsonb,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

ALTER TABLE module2_knowledge_rules
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN revision SET DEFAULT 1,
    ALTER COLUMN conditions TYPE jsonb USING conditions::jsonb,
    ALTER COLUMN outcome_payload TYPE jsonb USING outcome_payload::jsonb,
    ALTER COLUMN outcome_payload SET DEFAULT '{}'::jsonb,
    ALTER COLUMN status SET DEFAULT 'DRAFT',
    ALTER COLUMN owner_module_code SET DEFAULT 'MODULE_02_KNOWLEDGE_BASE',
    ALTER COLUMN source_kind SET DEFAULT 'HUMAN_CURATED',
    ALTER COLUMN blockers TYPE jsonb USING blockers::jsonb,
    ALTER COLUMN blockers SET DEFAULT '[]'::jsonb,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET DEFAULT now();

COMMENT ON TABLE module2_technologies IS
    'HousePlatform M2 schema: 20260911 + 20260913 + 20261106';

COMMIT;
