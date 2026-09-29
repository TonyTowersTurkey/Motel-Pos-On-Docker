#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.example and configure values." >&2
  exit 1
fi

docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.dev.yaml" up --build -d

echo "Waiting for postgres and redis to become healthy..."
docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.dev.yaml" ps

# Create additional DB and user for room pulse
docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.dev.yaml" exec -T postgres sh -c "/scripts/create_room_db_and_user.sh"

echo "Stack started. Check logs with: docker compose --env-file $ENV_FILE -f $ROOT_DIR/docker-compose.dev.yaml logs -f"
