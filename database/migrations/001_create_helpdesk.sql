BEGIN;

CREATE SCHEMA IF NOT EXISTS helpdesk;

CREATE TABLE IF NOT EXISTS helpdesk.schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS helpdesk.tickets (
  ticket_id text PRIMARY KEY,
  created_at timestamptz NOT NULL,
  channel text NOT NULL,
  language text NOT NULL,
  customer_tier text NOT NULL,
  product text NOT NULL,
  subject text NOT NULL,
  body text NOT NULL,
  category text NOT NULL,
  priority text NOT NULL CHECK (priority IN ('P1','P2','P3','P4')),
  escalated boolean NOT NULL,
  resolution_time_minutes integer NOT NULL CHECK (resolution_time_minutes > 0),
  agent_response text NOT NULL,
  satisfaction_score integer NOT NULL CHECK (satisfaction_score BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS tickets_created_at_idx
  ON helpdesk.tickets (created_at DESC);
CREATE INDEX IF NOT EXISTS tickets_priority_idx
  ON helpdesk.tickets (priority);
CREATE INDEX IF NOT EXISTS tickets_category_idx
  ON helpdesk.tickets (category);
CREATE INDEX IF NOT EXISTS tickets_escalated_idx
  ON helpdesk.tickets (escalated) WHERE escalated;
CREATE INDEX IF NOT EXISTS tickets_search_idx
  ON helpdesk.tickets
  USING gin (to_tsvector('simple', subject || ' ' || body || ' ' || product));

INSERT INTO helpdesk.schema_migrations (version)
VALUES ('001_create_helpdesk')
ON CONFLICT (version) DO NOTHING;

COMMIT;
