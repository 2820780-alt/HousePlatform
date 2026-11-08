-- A2.2: additive M2 resolution state; canonical material rows remain in M1.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-material-gaps'));

CREATE TABLE IF NOT EXISTS module2_material_gaps (
 id uuid PRIMARY KEY,
 technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE CASCADE,
 technology_revision integer NOT NULL,
 requirement_id uuid NOT NULL UNIQUE REFERENCES module2_technology_material_requirements(id) ON DELETE CASCADE,
 search_phrase varchar(500) NOT NULL,
 expected_category_id uuid REFERENCES material_categories(id),
 required_characteristics json NOT NULL DEFAULT '{}',
 evidence_context json NOT NULL DEFAULT '{}',
 status varchar(30) NOT NULL DEFAULT 'OPEN',
 resolution_note text,
 resolved_material_id uuid REFERENCES materials(id),
 source_task_id uuid REFERENCES source_tasks(id),
 created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT ck_module2_material_gap_status CHECK (status IN
  ('OPEN','REVIEWING','RESOLVED_EXISTING','SEARCH_REQUESTED','RESOLVED_NEW_MATERIAL','DISMISSED'))
);
CREATE INDEX IF NOT EXISTS ix_module2_material_gaps_technology_id ON module2_material_gaps(technology_id);
CREATE INDEX IF NOT EXISTS ix_module2_material_gaps_status ON module2_material_gaps(status);

INSERT INTO module2_material_gaps
 (id,technology_id,technology_revision,requirement_id,search_phrase,expected_category_id,
  required_characteristics,evidence_context,status,created_at,updated_at)
SELECT gen_random_uuid(),t.id,t.revision,r.id,COALESCE(c.name,r.code),r.material_category_id,
 COALESCE(r.technical_constraints::json,'{}'::json),'{}'::json,'OPEN',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
FROM module2_technology_material_requirements r
JOIN module2_technologies t ON t.id=r.technology_id
LEFT JOIN material_categories c ON c.id=r.material_category_id
WHERE t.status='ACTIVE' AND t.technology_code LIKE 'FND_%'
 AND NOT EXISTS (SELECT 1 FROM module2_material_gaps g WHERE g.requirement_id=r.id)
 AND NOT EXISTS (
  SELECT 1 FROM materials m WHERE m.status='VERIFIED'
   AND (m.id=r.canonical_material_id OR
    (r.material_category_id IS NOT NULL AND (m.category_id=r.material_category_id OR m.subcategory_id=r.material_category_id)))
 );

INSERT INTO source_tasks
 (id,source_id,action_type,status,parameters,created_at,updated_at)
SELECT gen_random_uuid(),NULL,'FIND_NEW_PRODUCTS','NEEDS_REVIEW',
 json_build_object('origin','M2_MATERIAL_GAP','gap_id',g.id::text,
  'technology_code',t.technology_code,'requirement_code',r.code,
  'search_phrase',g.search_phrase,'category_id',g.expected_category_id::text),
 CURRENT_TIMESTAMP,CURRENT_TIMESTAMP
FROM module2_material_gaps g
JOIN module2_technologies t ON t.id=g.technology_id
JOIN module2_technology_material_requirements r ON r.id=g.requirement_id
WHERE g.source_task_id IS NULL AND g.status IN ('OPEN','REVIEWING','SEARCH_REQUESTED');

UPDATE module2_material_gaps g SET source_task_id=task.id
FROM source_tasks task
WHERE g.source_task_id IS NULL
 AND task.parameters->>'origin'='M2_MATERIAL_GAP'
 AND task.parameters->>'gap_id'=g.id::text;
COMMIT;
