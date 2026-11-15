BEGIN;
ALTER TABLE module5_estimate_preview_snapshots
    ADD COLUMN IF NOT EXISTS foundation_geometry_revision_id uuid
        REFERENCES module7_foundation_geometry_revisions(id) ON DELETE RESTRICT;
ALTER TABLE module5_estimate_preview_snapshots ALTER COLUMN geometry_revision_id DROP NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'module5_estimate_preview_snapshots'::regclass
                     AND conname = 'module5_preview_one_geometry_check') THEN
        ALTER TABLE module5_estimate_preview_snapshots
            ADD CONSTRAINT module5_preview_one_geometry_check
            CHECK ((geometry_revision_id IS NULL) <> (foundation_geometry_revision_id IS NULL));
    END IF;
END $$;
COMMIT;
