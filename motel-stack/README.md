# motel-stack

Unified Docker Compose stack to run `motel-pos` and `Garage_Door_Detection` together for development and production.

See `docker-compose.dev.yaml` for local development (mounts source, hot-reload). See `docker-compose.prod.yaml` for production layout (images, read-only mounts, Caddy TLS).

Steps (dev):

1. Copy `.env.example` to `.env` and adjust values.
2. Start: `./scripts/up.sh`
3. After startup, run Motel init if needed: `docker compose -f docker-compose.dev.yaml run --rm motel-pos init`
4. Run Room Pulse DB init if not created: the up script attempts it.
