#!/usr/bin/env bash

set -euo pipefail

BASE_URL="${FOLDSEEK_AGENT_BASE_URL:-http://127.0.0.1:8100}"

echo "[1/3] health"
curl -fsS "${BASE_URL}/health"
echo

echo "[2/3] ui status"
curl -fsS "${BASE_URL}/ui/status"
echo

if [[ -n "${FOLDSEEK_AGENT_SMOKE_PDB_PATH:-}" ]]; then
  echo "[3/3] search_structure"
  curl -fsS -X POST "${BASE_URL}/search_structure" \
    -H "Content-Type: application/json" \
    -d "{\"pdb_path\":\"${FOLDSEEK_AGENT_SMOKE_PDB_PATH}\",\"database\":\"${FOLDSEEK_AGENT_SMOKE_DATABASE:-afdb50}\",\"topk\":3}"
  echo
else
  echo "[3/3] skipped search_structure because FOLDSEEK_AGENT_SMOKE_PDB_PATH is not set"
fi
