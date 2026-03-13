#!/usr/bin/env bash

set -euo pipefail

HOST="${FOLDSEEK_AGENT_API_HOST:-0.0.0.0}"
PORT="${FOLDSEEK_AGENT_API_PORT:-8000}"

exec uvicorn api.main:app --host "${HOST}" --port "${PORT}"
