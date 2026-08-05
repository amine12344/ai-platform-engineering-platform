#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/services/supportops-api"
VENV="${ROOT_DIR}/.venv-api"
PORT="${SUPPORTOPS_API_PORT:-8080}"
LOG_FILE="${ROOT_DIR}/.local/supportops-api.log"
PID_FILE="${ROOT_DIR}/.local/supportops-api.pid"

mkdir -p "${ROOT_DIR}/.local"

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  test -x "${VENV}/bin/python" || python3 -m venv "${VENV}"
  "${VENV}/bin/python" -m pip install --upgrade pip
  "${VENV}/bin/python" -m pip install -r "${SERVICE_DIR}/requirements-dev.txt"
fi

export PYTHONPATH="${SERVICE_DIR}/src"
export SUPPORTOPS_DATABASE_HOST="${SUPPORTOPS_DATABASE_HOST:-127.0.0.1}"
export SUPPORTOPS_DATABASE_PORT="${SUPPORTOPS_DATABASE_PORT:-5432}"
export SUPPORTOPS_DATABASE_NAME="${SUPPORTOPS_DATABASE_NAME:-supportops}"
export SUPPORTOPS_DATABASE_USER="${SUPPORTOPS_DATABASE_USER:-supportops}"
: "${SUPPORTOPS_DATABASE_PASSWORD:?Set SUPPORTOPS_DATABASE_PASSWORD}"

cleanup() {
  if [[ -f "${PID_FILE}" ]]; then
    kill "$(cat "${PID_FILE}")" 2>/dev/null || true
    rm -f "${PID_FILE}"
  fi
}
trap cleanup EXIT

"${VENV}/bin/uvicorn" supportops_api.main:app \
  --app-dir "${SERVICE_DIR}/src" \
  --host 127.0.0.1 --port "${PORT}" >"${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

for _ in {1..30}; do
  if curl --fail --silent "http://127.0.0.1:${PORT}/healthz" >/dev/null; then
    break
  fi
  sleep 1
done

curl --fail --silent "http://127.0.0.1:${PORT}/healthz" | python3 -m json.tool
curl --fail --silent "http://127.0.0.1:${PORT}/readyz" | python3 -m json.tool
curl --fail --silent "http://127.0.0.1:${PORT}/api/v1/tickets?priority=P1&limit=3" | python3 -m json.tool
curl --fail --silent "http://127.0.0.1:${PORT}/api/v1/summary" | python3 -m json.tool

status="$(curl --silent --output /tmp/supportops-invalid.json --write-out '%{http_code}' \
  "http://127.0.0.1:${PORT}/api/v1/tickets?priority=P9")"
test "${status}" = "422"
echo "[demo] invalid priority correctly returned HTTP 422"
echo "[demo] logs: ${LOG_FILE}"
