CREATE SCHEMA IF NOT EXISTS helpdesk;

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

TRUNCATE helpdesk.tickets;

COPY helpdesk.tickets
FROM '/tmp/tickets.csv'
WITH (
  FORMAT csv,
  HEADER true
);
