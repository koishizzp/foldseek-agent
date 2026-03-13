#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

AGENT_PID_FILE="${FOLDSEEK_AGENT_API_PID_FILE:-logs/foldseek-agent.pid}"
STOP_TIMEOUT="${FOLDSEEK_AGENT_STOP_WAIT_TIMEOUT:-20}"

read_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    tr -d '[:space:]' <"$file"
    return 0
  fi
  return 1
}

stop_pid() {
  local name="$1"
  local pid="$2"
  local timeout="$3"

  if [[ -z "$pid" ]] || ! kill -0 "$pid" >/dev/null 2>&1; then
    return 1
  fi

  echo "Stopping ${name} (PID: ${pid})..."
  kill "$pid" >/dev/null 2>&1 || true

  for ((i=1; i<=timeout; i++)); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "${name} stopped."
      return 0
    fi
    sleep 1
  done

  echo "${name} did not exit within ${timeout}s, sending SIGKILL..."
  kill -9 "$pid" >/dev/null 2>&1 || true
  sleep 1
  ! kill -0 "$pid" >/dev/null 2>&1
}

find_pid_by_pattern() {
  local pattern="$1"
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f "$pattern" | head -n 1
    return 0
  fi
  return 1
}

STOPPED_ANY=0
AGENT_PID="$(read_pid_file "$AGENT_PID_FILE" 2>/dev/null || true)"
if [[ -n "$AGENT_PID" ]] && stop_pid "Foldseek Agent API" "$AGENT_PID" "$STOP_TIMEOUT"; then
  STOPPED_ANY=1
fi

rm -f "$AGENT_PID_FILE"

if [[ "$STOPPED_ANY" -eq 0 ]]; then
  FALLBACK_PID="$(find_pid_by_pattern 'uvicorn api.main:app' 2>/dev/null || true)"
  if [[ -n "$FALLBACK_PID" ]] && stop_pid "Foldseek Agent API" "$FALLBACK_PID" "$STOP_TIMEOUT"; then
    STOPPED_ANY=1
  fi
fi

if [[ "$STOPPED_ANY" -eq 0 ]]; then
  echo "No running Foldseek Agent API process was found."
  exit 0
fi

echo "Stop completed."
