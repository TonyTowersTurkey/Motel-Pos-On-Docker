#!/usr/bin/env bash
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

source "$ENV_FILE"

WEBHOOK_URL="http://${MOTEL_HOSTNAME:-localhost}:8000/api/webhooks/room-pulse/"
TOKEN="${ROOM_PULSE_WEBHOOK_TOKEN:-}" 

PAYLOAD='{"schema_version":"1.0","event_id":"00000000-0000-0000-0000-000000000001","event_type":"test","generated_at":"2026-01-01T00:00:00+00:00","source":"smoke","room_count":0,"rooms":[]}'

echo "Posting test webhook to $WEBHOOK_URL"

if [[ -n "$TOKEN" ]]; then
  curl -s -o /dev/null -w "%{http_code}\n" -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -H "X-Room-Pulse-Event: 00000000-0000-0000-0000-000000000001" -d "$PAYLOAD"
else
  curl -s -o /dev/null -w "%{http_code}\n" -X POST "$WEBHOOK_URL" -H "Content-Type: application/json" -H "X-Room-Pulse-Event: 00000000-0000-0000-0000-000000000001" -d "$PAYLOAD"
fi
