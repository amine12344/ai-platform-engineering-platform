#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo '[1/4] Validating repository contract'
python3 scripts/validate_repository.py

echo '[2/4] Regenerating deterministic sample dataset'
python3 datasets/generate_supportops.py

echo '[3/4] Validating generated dataset'
python3 datasets/verify_supportops.py datasets/releases/sample/tickets.csv

echo '[4/4] Running automated tests'
python3 -m unittest discover -s tests -v

echo 'PASS  foundation demonstration completed'
