# Lab 01 - PostgreSQL Data Layer

This lab documents the PostgreSQL data-layer deployment workflow for the platform repository.

## Purpose

Deploy the PostgreSQL StatefulSet defined in `platform/data/postgresql.yaml` into the `supportops-data` namespace.

## Command history lookup

A search of `~/.bash_history` did not return exact `supportops-data` or `platform/data/postgresql.yaml` commands. The workflow below is reconstructed from the repository manifest and expected deployment steps.

## Commands

1. Create the data namespace:
   - `kubectl create namespace supportops-data --dry-run=client -o yaml | kubectl apply -f -`

2. Create PostgreSQL credentials secret:
   - `kubectl create secret generic postgresql-credentials --from-literal=password=<strong-password> -n supportops-data`

3. Apply the PostgreSQL manifest:
   - `kubectl apply -f platform/data/postgresql.yaml`

4. Verify deployment and service:
   - `kubectl -n supportops-data get pods,svc,statefulset`
   - `kubectl -n supportops-data describe pod postgresql-0`

5. Access PostgreSQL locally:
   - `kubectl -n supportops-data port-forward svc/postgresql 5432:5432`

6. Optional cleanup:
   - `kubectl -n supportops-data delete -f platform/data/postgresql.yaml`
   - `kubectl -n supportops-data delete namespace supportops-data`

## Notes

- The database container runs as non-root and uses a `StatefulSet` with persistent storage.
- The manifest defines a `ServiceAccount`, `Service`, and `StatefulSet` in `platform/data/postgresql.yaml`.
- Add a strong password secret before applying the manifest.
