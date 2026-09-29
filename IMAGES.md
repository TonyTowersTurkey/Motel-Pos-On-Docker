Image inventory and override guide

This file lists images used by the `motel-stack` compose projects and how to override them.

- `postgres` - ${POSTGRES_IMAGE:-postgres:16-bookworm}
  - Purpose: Primary PostgreSQL server hosting both Motel POS and Room Pulse databases.
  - Override: set `POSTGRES_IMAGE` in `motel-stack/.env`.

- `redis` - ${REDIS_IMAGE:-redis:7-alpine}
  - Purpose: Redis for SSE and background job coordination.
  - Override: set `REDIS_IMAGE` in `motel-stack/.env`.

- `motel-pos` - ${MOTEL_POS_IMAGE:-motel-pos:latest}
  - Purpose: Django-based Motel POS application.
  - Build: default development uses local build from `../motel-pos`.
  - Override: push/pull a release image and set `MOTEL_POS_IMAGE` in `.env`.

- `room-pulse` - ${ROOM_PULSE_IMAGE:-room-pulse:latest}
  - Purpose: Garage Door Detection / Room Pulse FastAPI application.
  - Build: default development uses local build from `../Garage_Door_Detection`.
  - Override: set `ROOM_PULSE_IMAGE` in `.env`.

- `caddy` - ${CADDY_IMAGE:-caddy:2-alpine}
  - Purpose: Edge proxy and TLS termination.
  - Override: set `CADDY_IMAGE` in `.env`.

Notes
- Each service has a `motel_stack.component` label (e.g., `motel-pos`, `room-pulse`) for easy filtering:

```bash
docker ps --filter "label=motel_stack.component=motel-pos"
```

- Keep runtime artifacts (media, models, reports) on dedicated volumes; images should be stateless where possible.
