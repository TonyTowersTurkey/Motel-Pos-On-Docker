#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env.production}"
BACKUP_ROOT="${BACKUP_ROOT:-${PROJECT_ROOT}/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINATION="${BACKUP_ROOT}/${STAMP}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE." >&2
    exit 1
fi

mkdir -p "$DESTINATION"
compose=(docker compose --project-directory "$PROJECT_ROOT" --env-file "$ENV_FILE")

database_tmp="${DESTINATION}/postgres.dump.tmp"
files_tmp="${DESTINATION}/files.tar.gz.tmp"

"${compose[@]}" exec -T postgres sh -c \
    'exec pg_dump --format=custom --no-owner --no-privileges --username "$POSTGRES_USER" "$POSTGRES_DB"' \
    >"$database_tmp"
mv "$database_tmp" "${DESTINATION}/postgres.dump"

"${compose[@]}" run --rm --no-deps --entrypoint sh init -c \
    'exec tar -C /app -czf - media data/reports' >"$files_tmp"
mv "$files_tmp" "${DESTINATION}/files.tar.gz"

sha256sum "${DESTINATION}/postgres.dump" "${DESTINATION}/files.tar.gz" \
    >"${DESTINATION}/SHA256SUMS"

echo "Backup written to ${DESTINATION}"
echo "Copy this directory to storage outside the Proxmox host."
