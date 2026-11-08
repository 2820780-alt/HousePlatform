-- A2.2 follow-up: carry existing M2 source reference IDs into M1 search context.
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('houseplatform:m2-material-gap-evidence'));

UPDATE module2_material_gaps g SET evidence_context=json_build_object(
 'technology_code',t.technology_code,
 'requirement_code',r.code,
 'evidence_reference_ids',COALESCE((
   SELECT json_agg(e.id::text ORDER BY e.id)
   FROM module2_technology_evidence_references e
   WHERE e.technology_id=t.id AND
    (e.target_kind='TECHNOLOGY' OR
     (e.target_kind='MATERIAL_REQUIREMENT' AND e.target_reference=r.id::text))
 ),'[]'::json))
FROM module2_technologies t, module2_technology_material_requirements r
WHERE g.technology_id=t.id AND g.requirement_id=r.id
 AND g.evidence_context->'evidence_reference_ids' IS NULL;

UPDATE source_tasks task SET parameters=(task.parameters::jsonb ||
 jsonb_build_object('evidence_reference_ids',g.evidence_context->'evidence_reference_ids'))::json
FROM module2_material_gaps g
WHERE task.id=g.source_task_id
 AND task.parameters->>'origin'='M2_MATERIAL_GAP'
 AND NOT (task.parameters::jsonb ? 'evidence_reference_ids');
COMMIT;
