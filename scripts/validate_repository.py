#!/usr/bin/env python3
"""Fail fast when the platform repository is incomplete or inconsistent."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "Makefile",
    "platform/versions.env",
    "platform/kind/profiles/16gb.yaml",
    "platform/foundation/namespaces.yaml",
    "platform/foundation/ingress-nginx-values.yaml",
    "platform/foundation/platform-health.yaml",
    "platform/data/postgresql.yaml",
    "platform/data/seaweedfs.yaml",
    "platform/mlflow/mlflow.yaml",
    "starter-project/mlflow/Dockerfile",
    "starter-project/platform-health/Dockerfile",
    "datasets/generate_supportops.py",
    "datasets/verify_supportops.py",
    "datasets/releases/sample/manifest.json",
    "database/migrations/001_create_helpdesk.sql",
    "database/migrations/002_dataset_metadata.sql",
    "services/supportops-api/Dockerfile",
    "services/supportops-api/requirements.txt",
    "services/supportops-api/src/supportops_api/main.py",
    "platform/apps/supportops-api.yaml",
    "scripts/migrate_database.sh",
    "scripts/import_dataset.sh",
)

VERSION_KEYS = (
    "KIND_NODE_IMAGE",
    "REGISTRY_IMAGE",
    "PLATFORM_HEALTH_BASE_IMAGE",
    "PLATFORM_HEALTH_IMAGE",
    "INGRESS_NGINX_CHART_VERSION",
    "POSTGRES_IMAGE",
    "SEAWEEDFS_IMAGE",
    "DVC_VERSION",
    "PYTHON_IMAGE",
    "SUPPORTOPS_API_IMAGE",
    "MLFLOW_BASE_IMAGE",
    "MLFLOW_IMAGE",
)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    print(f"FAIL  {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"^([A-Z0-9_]+)\s*:?=\s*(\S+)\s*$")

    for raw_line in read("platform/versions.env").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if not match:
            fail(f"invalid versions.env line: {raw_line}")
        values[match.group(1)] = match.group(2)

    missing = [key for key in VERSION_KEYS if key not in values]
    if missing:
        fail(f"missing version keys: {', '.join(missing)}")
    return values


def require_manifest_value(path: str, expected: str) -> None:
    if expected not in read(path):
        fail(f"{path} does not reference pinned value {expected}")


def main() -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        fail(f"required files are missing: {', '.join(missing)}")

    versions = parse_versions()
    makefile = read("Makefile")
    if "include platform/versions.env" not in makefile:
        fail("Makefile does not include platform/versions.env")

    require_manifest_value(
        "platform/foundation/platform-health.yaml",
        versions["PLATFORM_HEALTH_IMAGE"],
    )
    require_manifest_value(
        "platform/data/postgresql.yaml",
        versions["POSTGRES_IMAGE"],
    )
    require_manifest_value(
        "platform/data/seaweedfs.yaml",
        versions["SEAWEEDFS_IMAGE"],
    )
    require_manifest_value(
        "platform/apps/supportops-api.yaml",
        versions["SUPPORTOPS_API_IMAGE"],
    )
    require_manifest_value(
        "platform/mlflow/mlflow.yaml",
        versions["MLFLOW_IMAGE"],
    )

    namespaces = read("platform/foundation/namespaces.yaml")
    for namespace in (
        "supportops-platform",
        "supportops-data",
        "supportops-ml",
        "supportops-observability",
        "supportops-security",
    ):
        if f"name: {namespace}" not in namespaces:
            fail(f"namespace manifest is missing {namespace}")

    print(
        "PASS  repository contract is complete; "
        f"validated_files={len(REQUIRED_FILES)} "
        f"version_keys={len(VERSION_KEYS)}"
    )


if __name__ == "__main__":
    main()
