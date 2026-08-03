# SupportOps AI Platform Architecture

## Goal

Build one incremental AI platform that begins with a reproducible local Kubernetes and data foundation, then adds APIs, AI services, retrieval, observability, security, CI/CD, and deployment capabilities without discarding earlier work.

## Current components

```text
Developer workstation
├── Makefile orchestration
├── Kind Kubernetes cluster
│   ├── ingress-nginx
│   ├── supportops-platform
│   │   └── platform-health
│   ├── supportops-data
│   │   ├── PostgreSQL
│   │   └── SeaweedFS S3 endpoint
│   ├── supportops-ml
│   ├── supportops-observability
│   └── supportops-security
├── Local OCI registry on localhost:5001
└── Deterministic SupportOps dataset + DVC metadata
```

## Design principles

1. Each lab becomes a platform milestone rather than an isolated solution.
2. Every milestone must preserve previous functionality and add regression tests.
3. Component versions are pinned in `platform/versions.env`.
4. Secrets are generated locally and never committed.
5. Workloads run non-root with minimal privileges whenever the upstream image permits it.
6. Data schemas and API contracts must become versioned artifacts.
7. Every milestone ends with an executable demonstration and updated progress record.

## Target evolution

1. Foundation reliability.
2. Versioned PostgreSQL migrations and SupportOps API.
3. Dataset ingestion and DVC object-store lifecycle.
4. AI classification and summarization service.
5. Retrieval and knowledge workflows.
6. User interface and authentication.
7. Metrics, logs, traces, and model evaluation.
8. CI/CD, supply-chain controls, and deployable release bundles.
