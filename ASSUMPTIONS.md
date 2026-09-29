Assumptions and Notes

- Both repositories remain independent; `motel-stack` orchestrates them via Docker Compose.
- `motel-pos` already contains production scripts and health endpoints; `motel-stack` calls into them where appropriate.
- Room Pulse (`Garage_Door_Detection`) is expected to run its scheduler/workers in-process by default. To avoid duplicate workers in multi-replica setups, set environment flags in `.env` such as `SNAPSHOT_SCHEDULER_ENABLED=false` and run the scheduler as a single service when needed.
- Postgres runs as a single container; the init script `init/create_room_db_and_user.sh` creates two databases and users idempotently.
- In production, Caddy is the only externally exposed service; both apps are reachable by hostname mapping in Caddyfile.
- Development compose mounts source trees for hot reload; production uses images and read-only media mounts.
- Secrets must be provided via `.env` or an external secret manager — do not commit secrets.

Verification steps

1. Run the dev stack and ensure `postgres` and `redis` pass healthchecks.
2. Run `motel-pos` init/migrations and verify `/api/health/` returns 200.
3. Initialize Room Pulse DB with `python -m app.db.init_db` and verify its health endpoint.
4. Post a sample webhook using `scripts/smoke_test_webhook.sh` and confirm Motel POS accepted the event and responded 2xx.
