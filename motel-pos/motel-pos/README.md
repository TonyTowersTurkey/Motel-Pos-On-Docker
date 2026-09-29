# Motel POS

Django ASGI motel operations application with PostgreSQL, Redis-backed live
dashboard events, and an authenticated room-occupancy webhook.

## Production deployment

The supported on-premises deployment is Docker Compose inside a dedicated
Proxmox QEMU VM. The stack includes Caddy, the application, PostgreSQL, Redis,
and an optional camera/TensorFlow detector image.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for VM preparation, production
configuration, deployment, upgrades, backups, restore testing, TLS, and detector
integration.

```bash
cp .env.production.example .env.production
# Replace every CHANGE_ME value, then:
./scripts/deploy.sh
```

Local development continues to use `.env` and `scripts/run_local.sh`.
