#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

API_PORT="${FOLDSEEK_AGENT_API_PORT:-8100}"
BASE_URL="${FOLDSEEK_AGENT_BASE_URL:-http://127.0.0.1:${API_PORT}}"
AGENT_PID_FILE="${FOLDSEEK_AGENT_API_PID_FILE:-logs/foldseek-agent.pid}"
AGENT_LOG="${FOLDSEEK_AGENT_API_LOG:-logs/foldseek-agent.log}"

health_body() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "$url" 2>/dev/null || return 1
    return 0
  fi

  local python_bin="${PYTHON:-python3}"
  "$python_bin" - "$url" <<'PY'
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=3) as resp:
    print(resp.read().decode("utf-8", errors="replace"))
PY
}

check_pid() {
  local pid_file="$1"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi
  local pid
  pid="$(tr -d '[:space:]' <"$pid_file")"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if kill -0 "$pid" >/dev/null 2>&1; then
    printf '%s' "$pid"
    return 0
  fi
  return 1
}

echo "=============================="
echo "Foldseek Agent API"
echo "- URL: ${BASE_URL}"
echo "- PID file: ${AGENT_PID_FILE}"
echo "- Log file: ${AGENT_LOG}"

PID_VALUE=""
if PID_VALUE="$(check_pid "$AGENT_PID_FILE")"; then
  echo "- Process: running (PID: ${PID_VALUE})"
else
  echo "- Process: no live PID found"
fi

BODY=""
if BODY="$(health_body "${BASE_URL}/health" 2>/dev/null)"; then
  echo "- Health: ok"
  echo "- Health body: ${BODY}"
  echo "=============================="
  exit 0
fi

echo "- Health: failed"
if [[ -f "$AGENT_LOG" ]]; then
  echo "- Recent log:"
  tail -n 10 "$AGENT_LOG" || true
fi
echo "=============================="
exit 1
