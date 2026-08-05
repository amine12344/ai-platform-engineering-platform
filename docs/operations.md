# Platform operations

The root `Makefile` is the supported interface for installing, verifying,
recovering, and removing the local platform.

## Complete installation

```bash
make install
```

The installation runs in dependency order:

1. Validate required tools.
2. Start the local OCI registry.
3. Create or recover the Kind cluster and configure registry access.
4. Install namespaces, ingress-nginx, and platform health.
5. Generate credentials under `.local/platform`.
6. Deploy PostgreSQL and SeaweedFS.
7. Apply the versioned PostgreSQL migrations.
8. Generate and validate the 250-row ticket dataset.
9. Load `helpdesk.tickets`, record dataset provenance, and publish with DVC.
10. Build and deploy MLflow and create its artifact bucket.
11. Create API database credentials and deploy the SupportOps API.
12. Run all verification gates.

The install targets are idempotent and can be rerun after changing an image or
manifest. Kubernetes resources are applied declaratively, and named buckets are
created only when absent.

## Verification

```bash
make verify
```

Verification checks:

- ingress-nginx and platform-health rollouts;
- the platform health endpoint;
- PostgreSQL and SeaweedFS StatefulSets;
- two recorded schema migrations and exactly 250 imported tickets;
- the sample dataset release row count and SHA-256 provenance;
- the DVC bucket and remote dataset state;
- the MLflow rollout, health endpoint, and artifact bucket;
- the SupportOps API rollout, database readiness, ticket, and summary endpoints.

Individual gates are available as `verify-foundation`, `verify-data`,
`verify-mlflow`, and `verify-api`.

## Development checks and demonstrations

Install the API development dependencies, then run the same checks used by CI:

```bash
python3 -m pip install -r services/supportops-api/requirements-dev.txt
make validate
make test
```

Focused targets are `test-foundation`, `test-api`, and `lint-api`.
Executable demonstrations are available through `demo-foundation`,
`demo-api-local`, and `demo-api-kubernetes`.

## Recovery

Use `make restore` to rebuild custom images, reapply every component, reload the
dataset, and run verification. Use `make status` to inspect resources before or
after recovery.

All long-starting workloads use Kubernetes startup probes. This prevents their
liveness probes from restarting containers while PostgreSQL, SeaweedFS, MLflow,
or application processes are initializing.

## Cleanup

```bash
make clean
```

Cleanup removes the Kind cluster, registry container, registry data volume, and
Kind Docker network. Kubernetes persistent volumes are part of the local Kind
runtime and are removed with the cluster. Local credentials under
`.local/platform` and `.venv` are preserved.

To prove a reproducible rebuild, run:

```bash
make reset
```
