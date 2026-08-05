#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTEXT="${KUBE_CONTEXT:-kind-supportops-ai}"
NAMESPACE="supportops-platform"
HOST="api.supportops.local"
BASE_URL="http://127.0.0.1"

kubectl --context "${CONTEXT}" -n "${NAMESPACE}" rollout status deployment/supportops-api --timeout=180s
curl --fail --silent -H "Host: ${HOST}" "${BASE_URL}/healthz" | python3 -m json.tool
curl --fail --silent -H "Host: ${HOST}" "${BASE_URL}/readyz" | python3 -m json.tool
curl --fail --silent -H "Host: ${HOST}" "${BASE_URL}/api/v1/tickets?priority=P1&limit=3" | python3 -m json.tool
curl --fail --silent -H "Host: ${HOST}" "${BASE_URL}/api/v1/summary" | python3 -m json.tool

code="$(curl --silent --output /tmp/supportops-api-invalid.json --write-out '%{http_code}' \
  -H "Host: ${HOST}" "${BASE_URL}/api/v1/tickets?limit=0")"
test "${code}" = "422"

kubectl --context "${CONTEXT}" -n "${NAMESPACE}" logs deployment/supportops-api --tail=50
