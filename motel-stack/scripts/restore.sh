#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
BACKUP_DIR=""
CONFIRMED=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup)
      BACKUP_DIR="${2:-}"
      shift 2
      ;;
    --yes)
      CONFIRMED=true
      shift
      ;;
    *)
      echo "Usage: $0 --backup /absolute/path/to/backup [--yes]" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$BACKUP_DIR" || ! -f "${BACKUP_DIR}/postgres_motel.dump" ]]; then
  echo "The backup directory must contain postgres_motel.dump" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi
if [[ "$CONFIRMED" != true ]]; then
  echo "This replaces the current databases with dumps from ${BACKUP_DIR}" >&2
  read -r -p "Type RESTORE to continue: " answer
  [[ "$answer" == "RESTORE" ]] || exit 1
fi

compose=(docker compose --project-directory "$ROOT_DIR" --env-file "$ENV_FILE")

echo "Stopping apps..."
"${compose[@]}" stop motel-pos room-pulse caddy || true

echo "Restoring motel-pos DB..."
"${compose[@]}" exec -T postgres sh -c \
  'exec pg_restore --clean --if-exists --exit-on-error --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' <"${BACKUP_DIR}/postgres_motel.dump"

if [[ -f "${BACKUP_DIR}/postgres_room.dump" ]]; then
  echo "Restoring room-pulse DB..."
  "${compose[@]}" exec -T postgres sh -c \
    'exec pg_restore --clean --if-exists --exit-on-error --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$ROOM_POSTGRES_DB"' <"${BACKUP_DIR}/postgres_room.dump" || true
fi

if [[ -f "${BACKUP_DIR}/motel_files.tar.gz" ]]; then
  echo "Restoring motel files..."
  "${compose[@]}" run --rm --no-deps --entrypoint sh motel-pos -c 'exec tar -C /app -xzf -' <"${BACKUP_DIR}/motel_files.tar.gz"
fi
if [[ -f "${BACKUP_DIR}/room_files.tar.gz" ]]; then
  echo "Restoring room files..."
  "${compose[@]}" run --rm --no-deps --entrypoint sh room-pulse -c 'exec tar -C /app -xzf -' <"${BACKUP_DIR}/room_files.tar.gz"
fi

echo "Running migrations and inits..."
"${compose[@]}" run --rm motel-pos init || true
"${compose[@]}" run --rm --no-deps room-pulse python -m app.db.init_db || true

echo "Starting services..."
"${compose[@]}" up -d --no-deps --wait motel-pos room-pulse caddy

echo "Restore completed. Verify services and health endpoints."
