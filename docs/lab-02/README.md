# Lab 02 - Complete ML Platform Integration

This lab extends the remote `origin/lab-02` baseline into an operable local
platform with reliable startup behavior, lifecycle-oriented Make targets, and
the SupportOps API.

## Baseline and comparison

The working branch is `lab-02`, tracking `origin/lab-02` at commit `15ceb66`.
The remote branch introduced the first MLflow deployment and is itself ahead of
`origin/main` by the MLflow image, manifest, host configuration, and original
lab workflow.

Use these commands to reproduce the comparison:

```bash
git branch -vv
git log --oneline --decorate -12
git diff --stat origin/main...origin/lab-02
git diff --stat origin/lab-02
git diff --name-status origin/lab-02
git status --short
```

`git diff` reports tracked changes only. `git status --short` must also be used
to include new files such as the SupportOps API, its Kubernetes manifest, the
operations guide, and the database loading SQL.

## Implementation delta from `origin/lab-02`

### 1. Correct database loading from Make

The original inline SQL heredoc was split across independent Make recipe
shells, causing `CREATE: command not found`. The SQL was moved to
`platform/data/load-tickets.sql` and is now executed with input redirection:

```bash
kubectl --context kind-supportops-ai \
  -n supportops-data exec -i postgresql-0 -- \
  psql -v ON_ERROR_STOP=1 -U supportops -d supportops \
  < platform/data/load-tickets.sql
```

Validation commands:

```bash
make --dry-run database
bash -n <(make --dry-run database)
git diff --check
```

### 2. Validate and build the MLflow image

The image `ghcr.io/mlflow/mlflow:v3.15.0-full` is public and supports amd64 and
arm64. A stale Docker Desktop credential caused GHCR to return `denied`.

Commands used to isolate and fix the issue:

```bash
docker manifest inspect ghcr.io/mlflow/mlflow:v3.15.0-full
mkdir -p /tmp/codex-mlflow-docker-config
docker --config /tmp/codex-mlflow-docker-config \
  manifest inspect ghcr.io/mlflow/mlflow:v3.15.0-full
docker logout ghcr.io
docker manifest inspect ghcr.io/mlflow/mlflow:v3.15.0-full
make mlflow-image
```

The successful image was pushed as
`localhost:5001/supportops/mlflow:3.15.0` with digest
`sha256:b5e1e574a01a5da8b6e67f780d39f8b01a94e76dbf47da06b369da4bf9ee92c0`.

### 3. Diagnose `ContainerCreating` and restart loops

The initial pod investigation used:

```bash
kubectl --context kind-supportops-ai -n supportops-ml get pods -o wide
kubectl --context kind-supportops-ai -n supportops-ml describe pods
kubectl --context kind-supportops-ai -n supportops-ml get events \
  --sort-by=.lastTimestamp
kubectl --context kind-supportops-ai -n supportops-ml logs deployment/mlflow \
  --tail=200
kubectl --context kind-supportops-ai -n kube-system get pods -o wide
kubectl --context kind-supportops-ai -n supportops-data get pods,svc -o wide
```

Docker Desktop stopped responding during the investigation, and the Kind
control-plane container exited. Recovery preserved the existing cluster data:

```bash
docker info
docker ps -a --filter name=supportops-ai
docker start supportops-ai-control-plane
kubectl --context kind-supportops-ai -n kube-system get pods
```

If the Docker CLI itself cannot restart Docker Desktop, restart Docker Desktop
from the desktop application before starting the existing Kind node.

MLflow then exposed a second issue: database/DNS initialization and four worker
processes took longer than the liveness window. Kubernetes killed the container
before port 5000 opened. A startup probe now allows up to three minutes before
liveness begins:

```yaml
startupProbe:
  httpGet:
    path: /health
    port: http
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 36
```

Equivalent startup protection was added to platform-health, PostgreSQL,
SeaweedFS, and the SupportOps API.

### 4. Refactor platform lifecycle targets

Lab-number Make targets were replaced by lifecycle and component targets:

```bash
make install
make verify
make status
make restore
make clean
make reset

make foundation
make data
make dvc
make mlflow
make api
```

The dependency chain installs the registry, Kind, namespaces, ingress,
platform-health, PostgreSQL, SeaweedFS, dataset/DVC, MLflow, and SupportOps API,
then runs all verification gates. Local credentials now live under
`.local/platform`.

### 5. Integrate the SupportOps API

The API implementation includes:

- FastAPI `/healthz` and `/readyz` endpoints;
- a non-root container listening on port `8080`;
- pinned runtime and development dependencies;
- unit tests and `src`-layout pytest configuration;
- Kubernetes ServiceAccount, Deployment, Service, Ingress, probes, security
  context, and resource limits;
- local access through `api.supportops.local`;
- `api-image`, `api`, and `verify-api` Make targets.

The Dockerfile command must use valid single-instruction exec form:

```dockerfile
CMD ["uvicorn", "supportops_api.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
```

### 6. Add migrations, CI validation, and executable demonstrations

The latest implementation adds these repository files:

- `.github/workflows/ci.yml`: repository validation, foundation tests, API
  tests, Ruff, mypy, and Python compilation;
- `database/migrations/001_create_helpdesk.sql`: versioned helpdesk schema,
  migration tracking, indexes, and full-text search index;
- `database/migrations/002_dataset_metadata.sql`: dataset release provenance;
- `platform/apps/supportops-api.yaml`: canonical database-backed API deployment;
- `scripts/migrate_database.sh`: ordered Kubernetes or local SQL migrations;
- `scripts/import_dataset.sh`: deterministic generation, verification, ticket
  import, and dataset release upsert;
- `scripts/validate_repository.py`: pinned-version and required-file contract;
- `scripts/demo_foundation.sh`: foundation validation demonstration;
- `scripts/demo_api_local.sh`: local API and validation-error demonstration;
- `scripts/demo_api_kubernetes.sh`: ingress-backed Kubernetes API demonstration;
- `services/supportops-api/src/supportops_api/repository.py`: pooled PostgreSQL
  ticket queries and aggregate summaries;
- `tests/test_dataset.py`: deterministic dataset regression tests;
- `docs/ARCHITECTURE.md` and `docs/operations.md`: architecture and operator
  references.

The Makefile exposes each workflow directly:

```bash
make migrate
make database
make validate
make test-foundation
make test-api
make lint-api
make test
make demo-foundation
make demo-api-local
make demo-api-kubernetes
```

`make database` applies every migration before importing tickets and records
the dataset row count and SHA-256 digest in `helpdesk.dataset_releases`.
`make api` depends on that database state, creates the API database secret,
builds the image, and deploys `platform/apps/supportops-api.yaml`.

The database-backed API adds:

```text
GET /api/v1/tickets
GET /api/v1/tickets/{ticket_id}
GET /api/v1/summary
```

Readiness now verifies PostgreSQL connectivity. The API verification gate checks
health, readiness, ticket listing, and summary endpoints.

## Verification history

MLflow and the protected platform workloads were verified with:

```bash
kubectl --context kind-supportops-ai \
  -n supportops-ml rollout status deployment/mlflow --timeout=240s
kubectl --context kind-supportops-ai \
  -n supportops-platform rollout status deployment/platform-health --timeout=120s
kubectl --context kind-supportops-ai \
  -n supportops-data rollout status statefulset/seaweedfs --timeout=180s

curl --fail --resolve mlflow.supportops.local:80:127.0.0.1 \
  http://mlflow.supportops.local/health
curl --fail --resolve platform.supportops.local:80:127.0.0.1 \
  http://platform.supportops.local/healthz
curl --resolve s3.supportops.local:80:127.0.0.1 \
  http://s3.supportops.local/
```

Observed healthy states included MLflow, platform-health, and SeaweedFS at
`1/1 Running` with zero restarts after their updated rollouts. The unauthenticated
SeaweedFS S3 request returned `403`, confirming that the endpoint was available
and enforcing authentication.

Static validation for the final platform refactor used:

```bash
make --dry-run install
make --dry-run clean
git diff --check
python3 -m compileall -q services/supportops-api/src services/supportops-api/tests
make validate
make test-foundation
make --dry-run database
make --dry-run api
```

API tests and linting require the pinned development dependencies:

```bash
python3 -m pip install -r services/supportops-api/requirements-dev.txt
make test-api
make lint-api
```

The complete runtime acceptance command is:

```bash
make install
```

This command builds and deploys every component and finishes by running
`make verify`. See [`../operations.md`](../operations.md) for the canonical
operator workflow.
