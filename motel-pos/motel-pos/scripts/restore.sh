#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/.env.production}"
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

if [[ -z "$BACKUP_DIR" || ! -f "${BACKUP_DIR}/postgres.dump" ]]; then
    echo "The backup directory must contain postgres.dump." >&2
    exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Missing $ENV_FILE." >&2
    exit 1
fi
if [[ "$CONFIRMED" != true ]]; then
    echo "This replaces the current database with ${BACKUP_DIR}/postgres.dump." >&2
    read -r -p "Type RESTORE to continue: " answer
    [[ "$answer" == "RESTORE" ]] || exit 1
fi

compose=(docker compose --project-directory "$PROJECT_ROOT" --env-file "$ENV_FILE")

if [[ -f "${BACKUP_DIR}/SHA256SUMS" ]]; then
    (cd "$BACKUP_DIR" && sha256sum --check SHA256SUMS)
fi

"${compose[@]}" stop motel-pos
"${compose[@]}" exec -T postgres sh -c \
    'exec pg_restore --clean --if-exists --exit-on-error --no-owner --no-privileges --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' \
    <"${BACKUP_DIR}/postgres.dump"

if [[ -f "${BACKUP_DIR}/files.tar.gz" ]]; then
    "${compose[@]}" run --rm --no-deps --entrypoint sh -T init -c \
        'exec tar -C /app -xzf -' <"${BACKUP_DIR}/files.tar.gz"
fi

"${compose[@]}" run --rm init
"${compose[@]}" up -d --no-deps --wait motel-pos proxy
echo "Restore completed. Verify login, occupancy updates, media, and reports."
