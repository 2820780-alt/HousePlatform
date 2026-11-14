BEGIN;
CREATE TABLE IF NOT EXISTS module5_estimate_preview_snapshots (
    id uuid PRIMARY KEY,
    owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    geometry_revision_id uuid NOT NULL REFERENCES module7_strip_geometry_revisions(id) ON DELETE RESTRICT,
    mode varchar(20) NOT NULL DEFAULT 'PREVIEW' CHECK (mode = 'PREVIEW'),
    payload json NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_module5_estimate_preview_snapshots_owner_user_id ON module5_estimate_preview_snapshots(owner_user_id);
COMMIT;
