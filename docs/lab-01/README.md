# Lab 01 - PostgreSQL Data Layer

This lab documents the PostgreSQL data-layer deployment workflow for the platform repository.

## Purpose

Deploy the PostgreSQL StatefulSet defined in `platform/data/postgresql.yaml` into the `supportops-data` namespace.

## Command history executed

The following commands were used while completing the PostgreSQL data-layer work for this lab:

```bash
kubectl create namespace supportops-data --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic postgresql-credentials --from-literal=password=<strong-password> -n supportops-data
kubectl apply -f platform/data/postgresql.yaml
kubectl -n supportops-data rollout status statefulset/postgresql --timeout=240s
python3 datasets/generate_supportops.py
python3 datasets/verify_supportops.py datasets/releases/sample/tickets.csv
make database
kubectl --context kind-supportops-ai -n supportops-data exec postgresql-0 -- psql -U supportops -d supportops -c 'SELECT COUNT(*) AS ticket_count FROM helpdesk.tickets;'
```

The PostgreSQL import was also verified with the working stdin-based copy flow:

```bash
kubectl --context kind-supportops-ai \
  -n supportops-data exec -i postgresql-0 -- \
  psql -v ON_ERROR_STOP=1 \
  -U supportops \
  -d supportops <<'SQL'
TRUNCATE helpdesk.tickets;

COPY helpdesk.tickets
FROM '/tmp/tickets.csv'
WITH (
  FORMAT csv,
  HEADER true
);
SQL
```

## Notes

- The database container runs as non-root and uses a `StatefulSet` with persistent storage.
- The manifest defines a `ServiceAccount`, `Service`, and `StatefulSet` in `platform/data/postgresql.yaml`.
- The sample SupportOps dataset was generated deterministically and loaded successfully into PostgreSQL.
