# AI Platform Engineering Platform

This repository contains a platform engineering reference setup for local Kubernetes development and platform health checks.

## Repository Layout

- `platform/`
  - `versions.env` - version definitions for platform components
  - `foundation/` - platform bootstrap manifests and values
  - `kind/` - kind cluster profiles and local cluster configuration
  - `data/` - platform data-layer manifests, including PostgreSQL manifests
- `starter-project/`
  - `platform-health/` - simple health probe app used for platform validation
    - `Dockerfile`
    - `www/` - static health endpoints (`healthz`, `readyz`, `index.html`)
- `doc/` - lab and deployment documentation
- `docs/` - previous lab documentation
- `evidence/` - captured lab outputs and platform validation evidence

## Getting Started

1. Install required tools:
   - `kind`
   - `kubectl`
   - `helm`
   - `docker`

2. Create a local kind cluster using the provided profile:
   - `kind create cluster --config platform/kind/profiles/16gb.yaml`

3. Apply platform manifests from `platform/foundation/`.

4. Build and deploy the starter app to verify health endpoints.

## Progress update

The current branch now includes the following lab progress:

- A PostgreSQL data-layer deployment manifest under `platform/data/postgresql.yaml`.
- A SeaweedFS data-layer deployment manifest under `platform/data/seaweedfs.yaml`.
- A reproducible dataset workflow via the `Makefile` targets `dataset`, `database`, and `dvc`.
- A generated SupportOps sample dataset and validation workflow under `datasets/`.
- Verified PostgreSQL import and row-count checks for the loaded ticket data.

## Notes

- Keep local environment files out of source control by using `.gitignore`.
- Use the `evidence/` folder to store output from verification commands and lab checks.
