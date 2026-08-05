# SupportOps AI Platform

This repository installs a complete local AI platform on a Kind Kubernetes
cluster. The platform includes ingress, health checks, PostgreSQL, SeaweedFS,
DVC dataset management, MLflow, and the SupportOps API.

## Prerequisites

Install Docker, Kind, kubectl, Helm, Python 3, and curl. On Windows, configure
the local ingress names from an elevated PowerShell terminal:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\configure-windows-hosts.ps1
```

## Platform lifecycle

Run these commands from the repository root:

```bash
make doctor
make install
make status
```

`make install` is the main entry point. It creates the registry and Kind
cluster, installs every component, loads the dataset, provisions the DVC and
MLflow buckets, and runs all verification checks.

Use the lifecycle targets as follows:

| Target | Purpose |
| --- | --- |
| `make install` | Install and verify the complete platform |
| `make verify` | Verify all running components and data |
| `make status` | Display cluster, workload, service, and ingress state |
| `make restore` | Rebuild images, reapply components, and verify them |
| `make clean` | Remove the Kind cluster, registry container, registry volume, and Kind network |
| `make reset` | Clean and reinstall the complete platform |

Component targets are available for focused work:

```bash
make foundation
make data
make dvc
make mlflow
make api
make validate
make test
```

Generated credentials are stored in `.local/platform` and are excluded from
Git. `make clean` preserves these local credentials and the Python virtual
environment; it removes the platform runtime and its Kubernetes storage.

## Services

After installation, the following endpoints are available:

- Platform health: <http://platform.supportops.local/healthz>
- SeaweedFS S3 API: <http://s3.supportops.local>
- MLflow: <http://mlflow.supportops.local>
- SupportOps API: <http://api.supportops.local/healthz>
- SupportOps API documentation: <http://api.supportops.local/docs>

## Components

- `platform/foundation/`: namespaces, ingress configuration, and platform health
- `platform/data/`: PostgreSQL, SeaweedFS, and dataset-loading SQL
- `platform/mlflow/`: MLflow tracking and model artifact service
- `platform/apps/`: application service Kubernetes manifests
- `database/migrations/`: versioned PostgreSQL schema migrations
- `services/supportops-api/`: FastAPI application, image, and tests
- `datasets/`: deterministic SupportOps dataset generation and validation
- `starter-project/`: custom platform-health and MLflow images

See [Platform operations](docs/operations.md) for target dependencies,
verification behavior, recovery, and cleanup details.
