#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

compose=(docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE")

echo "This script performs a rollback by re-deploying the previous tag."
echo "Check your deployment process and image tags before using."

read -r -p "Enter motel-pos image tag to roll back to (e.g. motel-pos:previous): " MOTEL_TAG
read -r -p "Enter room-pulse image tag to roll back to (e.g. room-pulse:previous): " ROOM_TAG

export MOTEL_POS_IMAGE="$MOTEL_TAG"
export ROOM_PULSE_IMAGE="$ROOM_TAG"

"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" pull --quiet
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" up -d --no-deps motel-pos room-pulse caddy

echo "Rollback in progress. Monitor logs and health endpoints."
