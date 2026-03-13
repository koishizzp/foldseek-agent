#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

mkdir -p logs

API_HOST="${FOLDSEEK_AGENT_API_HOST:-0.0.0.0}"
API_PORT="${FOLDSEEK_AGENT_API_PORT:-8000}"
BASE_URL="${FOLDSEEK_AGENT_BASE_URL:-http://127.0.0.1:${API_PORT}}"
WAIT_TIMEOUT="${FOLDSEEK_AGENT_START_WAIT_TIMEOUT:-60}"
AGENT_LOG="${FOLDSEEK_AGENT_API_LOG:-logs/foldseek-agent.log}"
AGENT_PID_FILE="${FOLDSEEK_AGENT_API_PID_FILE:-logs/foldseek-agent.pid}"

health_check() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "$url" >/dev/null 2>&1
    return $?
  fi

  local python_bin="${PYTHON:-python3}"
  "$python_bin" - "$url" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen

with urlopen(sys.argv[1], timeout=3) as resp:
    raise SystemExit(0 if 200 <= getattr(resp, "status", 0) < 300 else 1)
PY
}

read_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    tr -d '[:space:]' <"$file"
    return 0
  fi
  return 1
}

is_running_pid() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

wait_for_service() {
  local url="$1"
  local timeout="$2"
  local pid="$3"

  for ((i=1; i<=timeout; i++)); do
    if health_check "$url"; then
      return 0
    fi
    if [[ -n "$pid" ]] && ! kill -0 "$pid" >/dev/null 2>&1; then
      return 1
    fi
    sleep 1
  done
  return 1
}

discover_access_urls() {
  local host="$1"
  local port="$2"
  local urls=()

  if [[ "$host" != "0.0.0.0" ]]; then
    urls+=("http://${host}:${port}")
  fi

  if command -v hostname >/dev/null 2>&1; then
    local host_ips
    host_ips="$(hostname -I 2>/dev/null || true)"
    for ip in $host_ips; do
      [[ -z "$ip" ]] && continue
      urls+=("http://${ip}:${port}")
    done
  fi

  if [[ ${#urls[@]} -eq 0 ]]; then
    urls+=("${BASE_URL}")
  fi

  printf '%s\n' "${urls[@]}" | awk '!seen[$0]++'
}

EXISTING_PID="$(read_pid_file "$AGENT_PID_FILE" 2>/dev/null || true)"
if is_running_pid "$EXISTING_PID"; then
  echo "Foldseek Agent API is already running (PID: $EXISTING_PID)"
  echo "Health: ${BASE_URL}/health"
  exit 0
fi

echo "Starting Foldseek Agent API on ${API_HOST}:${API_PORT}..."
bash ./start_agent.sh >"$AGENT_LOG" 2>&1 &
AGENT_PID=$!
echo "$AGENT_PID" >"$AGENT_PID_FILE"

if ! wait_for_service "${BASE_URL}/health" "$WAIT_TIMEOUT" "$AGENT_PID"; then
  echo "Failed to start Foldseek Agent API. Recent log output:" >&2
  tail -n 50 "$AGENT_LOG" >&2 || true
  rm -f "$AGENT_PID_FILE"
  exit 1
fi

echo
echo "Foldseek Agent API started:"
echo "- URL:      ${BASE_URL}"
echo "- Health:   ${BASE_URL}/health"
echo "- Log file: ${AGENT_LOG}"
echo "- PID file: ${AGENT_PID_FILE}"
echo "- Browser:"
discover_access_urls "$API_HOST" "$API_PORT" | while read -r url; do
  [[ -z "$url" ]] && continue
  echo "  * ${url}"
done
