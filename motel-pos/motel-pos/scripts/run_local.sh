#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Create it with: python3 -m venv .venv" >&2
  exit 1
fi

# Some shells export DEBUG with a non-boolean value. Django expects true/false.
export DEBUG=true

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
# Logged-in pages keep an SSE request open for live dashboard updates. Bound the
# development server's graceful shutdown so an open stream cannot stall reloads.
GRACEFUL_SHUTDOWN_TIMEOUT="${GRACEFUL_SHUTDOWN_TIMEOUT:-3}"

exec .venv/bin/python -m uvicorn config.asgi:application \
  --host "${HOST}" \
  --port "${PORT}" \
  --timeout-graceful-shutdown "${GRACEFUL_SHUTDOWN_TIMEOUT}" \
  --reload
