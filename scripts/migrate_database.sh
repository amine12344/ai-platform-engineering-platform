#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATION_DIR="${ROOT_DIR}/database/migrations"
MODE="${1:-kubernetes}"

run_kubernetes() {
  local context="${KUBE_CONTEXT:-kind-supportops-ai}"
  local namespace="${POSTGRES_NAMESPACE:-supportops-data}"
  local pod="${POSTGRES_POD:-postgresql-0}"

  kubectl --context "${context}" -n "${namespace}" wait \
    --for=condition=Ready "pod/${pod}" --timeout=180s

  for migration in "${MIGRATION_DIR}"/*.sql; do
    echo "[migrate] applying $(basename "${migration}")"
    kubectl --context "${context}" -n "${namespace}" exec -i "${pod}" -- \
      psql -v ON_ERROR_STOP=1 -U supportops -d supportops < "${migration}"
  done
}

run_local() {
  : "${DATABASE_URL:?Set DATABASE_URL for local migration mode}"
  command -v psql >/dev/null || {
    echo "psql is required for local migration mode" >&2
    exit 1
  }
  for migration in "${MIGRATION_DIR}"/*.sql; do
    echo "[migrate] applying $(basename "${migration}")"
    psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -f "${migration}"
  done
}

case "${MODE}" in
  kubernetes) run_kubernetes ;;
  local) run_local ;;
  *) echo "Usage: $0 [kubernetes|local]" >&2; exit 2 ;;
esac
