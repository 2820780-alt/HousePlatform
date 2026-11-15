BEGIN;
CREATE TABLE IF NOT EXISTS module7_foundation_geometry_revisions (
    id uuid PRIMARY KEY,
    object_id uuid NOT NULL REFERENCES module7_digital_house_objects(id) ON DELETE RESTRICT,
    version integer NOT NULL,
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE RESTRICT,
    inputs json NOT NULL,
    created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_m7_foundation_geometry_version UNIQUE(object_id, version),
    CONSTRAINT ck_m7_foundation_geometry_version_positive CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS ix_module7_foundation_geometry_revisions_object_id
    ON module7_foundation_geometry_revisions(object_id);
COMMIT;
