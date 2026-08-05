BEGIN;

CREATE TABLE IF NOT EXISTS helpdesk.dataset_releases (
  release_name text PRIMARY KEY,
  dataset_path text NOT NULL,
  sha256 text NOT NULL CHECK (length(sha256) = 64),
  row_count integer NOT NULL CHECK (row_count >= 0),
  imported_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO helpdesk.schema_migrations (version)
VALUES ('002_dataset_metadata')
ON CONFLICT (version) DO NOTHING;

COMMIT;
