# Lab 02 - MLflow Deployment and Access

This lab documents the MLflow model lifecycle deployment workflow and the browser-access setup for the local platform environment.

## Purpose

Deploy MLflow into the `supportops-ml` namespace and make it reachable locally through the ingress controller.

## Deployment

```bash
make mlflow
make verify-lab2
make status
```

## What changed

- Added an MLflow deployment manifest under `platform/mlflow/mlflow.yaml`.
- Configured the MLflow container with host allowlisting and CORS settings so the UI can be served through the local ingress.
- Increased container memory limits to avoid OOM kills during startup.
- Added ingress routing for `mlflow.supportops.local` so the UI is reachable in the browser.
- The Makefile creates the Kubernetes credentials, builds the custom image, and provisions the artifact bucket.

## Verification

The MLflow UI was verified through the ingress path with the following result:

- `GET /` returned `HTTP/1.1 200 OK`
- `/health` returned `HTTP/1.1 200 OK`

## Notes

- The MLflow service is exposed internally on port `5000`.
- The local browser URL is `http://mlflow.supportops.local/`.
- The custom image is based on `ghcr.io/mlflow/mlflow:v3.15.0-full` and adds the pinned PostgreSQL and S3 clients.
- PostgreSQL stores MLflow metadata and the `supportops-models` SeaweedFS bucket stores artifacts.
