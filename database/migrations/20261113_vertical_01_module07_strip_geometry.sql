BEGIN;
CREATE TABLE IF NOT EXISTS module7_digital_house_objects (
    id uuid PRIMARY KEY,
    owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_module7_digital_house_objects_owner_user_id ON module7_digital_house_objects(owner_user_id);
CREATE TABLE IF NOT EXISTS module7_strip_geometry_revisions (
    id uuid PRIMARY KEY,
    object_id uuid NOT NULL REFERENCES module7_digital_house_objects(id) ON DELETE RESTRICT,
    version integer NOT NULL,
    technology_id uuid NOT NULL REFERENCES module2_technologies(id) ON DELETE RESTRICT,
    length_m numeric(16,6) NOT NULL,
    width_m numeric(16,6) NOT NULL,
    height_m numeric(16,6) NOT NULL,
    created_by_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_m7_strip_geometry_version UNIQUE(object_id, version),
    CONSTRAINT ck_m7_strip_geometry_positive CHECK (version > 0 AND length_m > 0 AND width_m > 0 AND height_m > 0)
);
CREATE INDEX IF NOT EXISTS ix_module7_strip_geometry_revisions_object_id ON module7_strip_geometry_revisions(object_id);
COMMIT;
