# Motel-Pos-On-Docker

Compose stack and scripts to run `motel-pos` and Room Pulse together. Production deployments pull
multi-platform images from GitHub Container Registry (GHCR):

- `ghcr.io/tonytowersturkey/motel-pos:latest`
- `ghcr.io/tonytowersturkey/room-pulse:latest`

## Quickstart (production)

1. Clone the deployment repository:

```bash
git clone https://github.com/TonyTowersTurkey/Motel-Pos-On-Docker.git
cd Motel-Pos-On-Docker
```

2. Copy and edit environment files:

```bash
cp motel-stack/.env.example motel-stack/.env
cp motel-pos/motel-pos/.env.production.example motel-pos/motel-pos/.env.production
cp Garage_Door_Detection/Garage_Door_Detection/.env.example \
  Garage_Door_Detection/Garage_Door_Detection/.env
# Edit values and secrets, then secure permissions.
chmod 600 motel-stack/.env motel-pos/motel-pos/.env.production \
  Garage_Door_Detection/Garage_Door_Detection/.env
```

If either GHCR package is private, authenticate Docker with a classic personal access token that has
`read:packages` permission:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

3. Deploy on the server:

```bash
cd motel-stack
./scripts/deploy.sh
```

4. Smoke test:

```bash
./scripts/smoke_test_webhook.sh
```

The production services are also available directly on the host LAN at:

- Motel POS: `http://SERVER_HOSTNAME:8001`
- Room Pulse: `http://SERVER_HOSTNAME:8002`

These ports avoid a conflict with WebODM when it is already using port 8000.

Set `MOTEL_POS_IMAGE` and `ROOM_PULSE_IMAGE` in `motel-stack/.env` to immutable release tags such
as `:v1.0.0` for repeatable production deployments. Leave them empty to use `:latest`.

## Publishing images

The monorepo workflow `.github/workflows/build-and-publish-images.yaml` builds both applications
from this repository. A push to `main` publishes `latest` and `sha-<commit>` tags for both images.
A Git tag such as `v1.0.0` also publishes matching version tags. The workflow uses the
repository-scoped `GITHUB_TOKEN`; no registry password needs to be stored as an Actions secret.

## Development

Create the local application environment files, then use the dev compose to mount source and test
hot reload:

```bash
cp motel-pos/motel-pos/.env.example motel-pos/motel-pos/.env
cp Garage_Door_Detection/Garage_Door_Detection/.env.example \
  Garage_Door_Detection/Garage_Door_Detection/.env
cd motel-stack
./scripts/up.sh
```

The development endpoints are:

- Combined Caddy endpoint: `http://localhost:8000`
- Motel POS directly: `http://localhost:8001`
- Room Pulse directly: `http://localhost:8002`

## CI

GitHub Actions validate compose files and run `shellcheck` on scripts.
