#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CSV_PATH="${ROOT_DIR}/datasets/releases/sample/tickets.csv"
MANIFEST_PATH="${ROOT_DIR}/datasets/releases/sample/manifest.json"
MODE="${1:-kubernetes}"

python3 "${ROOT_DIR}/datasets/generate_supportops.py"
python3 "${ROOT_DIR}/datasets/verify_supportops.py" "${CSV_PATH}"

read_manifest() {
  python3 - "${MANIFEST_PATH}" "$1" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])
PY
}

SHA256="$(read_manifest sha256)"
ROW_COUNT="$(read_manifest rows)"

import_kubernetes() {
  local context="${KUBE_CONTEXT:-kind-supportops-ai}"
  local namespace="${POSTGRES_NAMESPACE:-supportops-data}"
  local pod="${POSTGRES_POD:-postgresql-0}"
  kubectl --context "${context}" -n "${namespace}" cp "${CSV_PATH}" "${pod}:/tmp/tickets.csv"
  kubectl --context "${context}" -n "${namespace}" exec -i "${pod}" -- \
    psql -v ON_ERROR_STOP=1 -U supportops -d supportops <<SQL
BEGIN;
TRUNCATE helpdesk.tickets;
COPY helpdesk.tickets FROM '/tmp/tickets.csv' WITH (FORMAT csv, HEADER true);
INSERT INTO helpdesk.dataset_releases (release_name, dataset_path, sha256, row_count)
VALUES ('sample', 'datasets/releases/sample/tickets.csv', '${SHA256}', ${ROW_COUNT})
ON CONFLICT (release_name) DO UPDATE SET
  dataset_path = EXCLUDED.dataset_path,
  sha256 = EXCLUDED.sha256,
  row_count = EXCLUDED.row_count,
  imported_at = now();
COMMIT;
SQL
}

import_local() {
  : "${DATABASE_URL:?Set DATABASE_URL for local import mode}"
  command -v psql >/dev/null || { echo "psql is required" >&2; exit 1; }
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 <<SQL
BEGIN;
TRUNCATE helpdesk.tickets;
\copy helpdesk.tickets FROM '${CSV_PATH}' WITH (FORMAT csv, HEADER true)
INSERT INTO helpdesk.dataset_releases (release_name, dataset_path, sha256, row_count)
VALUES ('sample', 'datasets/releases/sample/tickets.csv', '${SHA256}', ${ROW_COUNT})
ON CONFLICT (release_name) DO UPDATE SET
  dataset_path = EXCLUDED.dataset_path,
  sha256 = EXCLUDED.sha256,
  row_count = EXCLUDED.row_count,
  imported_at = now();
COMMIT;
SQL
}

case "${MODE}" in
  kubernetes) import_kubernetes ;;
  local) import_local ;;
  *) echo "Usage: $0 [kubernetes|local]" >&2; exit 2 ;;
esac
