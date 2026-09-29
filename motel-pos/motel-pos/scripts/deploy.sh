#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env.production}"
ENABLE_DETECTOR=false

if [[ "${1:-}" == "--detector" ]]; then
    ENABLE_DETECTOR=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--detector]" >&2
    exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE. Copy .env.production.example and configure it first." >&2
    exit 1
fi

compose=(docker compose --project-directory "$PROJECT_ROOT" --env-file "$ENV_FILE")

"${compose[@]}" config --quiet
"${compose[@]}" build motel-pos
"${compose[@]}" up -d postgres redis
"${compose[@]}" run --rm init
"${compose[@]}" run --rm --no-deps motel-pos check
"${compose[@]}" up -d --no-deps --wait motel-pos proxy

if [[ "$ENABLE_DETECTOR" == true ]]; then
    "${compose[@]}" --profile detector up -d --no-deps detector
fi

"${compose[@]}" ps
