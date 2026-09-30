#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
BACKUP_ROOT="${BACKUP_ROOT:-${ROOT_DIR}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINATION="${BACKUP_ROOT}/${STAMP}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

mkdir -p "$DESTINATION"
compose=(docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE")

echo "Dumping postgres database for motel-pos..."
"${compose[@]}" exec -T postgres sh -c \
  'exec pg_dump --format=custom --no-owner --no-privileges --username "$POSTGRES_USER" "$POSTGRES_DB"' >"${DESTINATION}/postgres_motel.dump"

echo "Dumping postgres database for room-pulse..."
"${compose[@]}" exec -T postgres sh -c \
  'exec pg_dump --format=custom --no-owner --no-privileges --username "$POSTGRES_USER" "$ROOM_POSTGRES_DB"' >"${DESTINATION}/postgres_room.dump" || true

echo "Archiving media and models from room-pulse..."
"${compose[@]}" run --rm --no-deps --entrypoint sh motel-pos -c 'exec tar -C /app -czf - media data/reports' >"${DESTINATION}/motel_files.tar.gz" || true
"${compose[@]}" run --rm --no-deps --entrypoint sh room-pulse -c 'exec tar -C /app -czf - media classificationModels' >"${DESTINATION}/room_files.tar.gz" || true

sha256sum "${DESTINATION}"/* >"${DESTINATION}/SHA256SUMS" || true

echo "Backup written to ${DESTINATION}"
