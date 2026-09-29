#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.example and configure values." >&2
  exit 1
fi

compose=(docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE")

echo "Validating compose files..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" config --quiet

echo "Building images (if MOTEL_POS_IMAGE or ROOM_PULSE_IMAGE are not set, local builds may be used)..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" build --pull --parallel || true

echo "Starting postgres and redis..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" up -d postgres redis

echo "Ensuring databases and users exist..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" exec -T postgres sh -c "/scripts/create_room_db_and_user.sh"

echo "Running Motel POS init and checks..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" run --rm motel-pos init
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" run --rm --no-deps motel-pos check

echo "Initializing Room Pulse DB..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" run --rm --no-deps room-pulse python -m app.db.init_db

echo "Starting application containers and proxy..."
"${compose[@]}" -f "$ROOT_DIR/docker-compose.prod.yaml" up -d --no-deps --wait motel-pos room-pulse caddy

echo "Deployment finished. Use the compose ps and logs commands to inspect services."
