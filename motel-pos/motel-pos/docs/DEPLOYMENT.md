# Docker deployment on Proxmox

This deployment runs the POS, PostgreSQL, Redis, Caddy, and optionally the room
detector as separate containers in one Compose project. Run Docker inside a
dedicated Proxmox QEMU VM, not directly on the Proxmox host.

## 1. Prepare the VM

Recommended starting size:

- Ubuntu 24.04 or Debian 13
- 8 to 16 vCPU and 16 to 32 GB RAM when the detector runs in the same VM
- SSD-backed VirtIO SCSI disk
- VirtIO network adapter, static address, and QEMU guest agent
- Ports 80 and 443 allowed from the staff/camera networks
- SSH restricted to an administration network

Install Docker Engine and the Compose plugin from Docker's official repository.
Do not expose PostgreSQL, Redis, Django port 8000, or the detector on the VM.

## 2. Configure production

Clone this repository on the VM and create the production environment file:

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

Generate independent secrets rather than reusing passwords:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Replace every `CHANGE_ME` value. `SITE_ADDRESS`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, and `DETECTOR_WEBHOOK_URL` must describe the same address.
Do not add quotes around values in `.env.production` unless the quotes are meant
to be part of the value.

Caddy obtains a publicly trusted certificate when the hostname and network allow
ACME validation. For an IP address or internal-only name, Caddy uses its local CA.
The CA certificate is stored in the `caddy-data` volume and must be installed as a
trusted root on staff devices and on the detector host/container.

## 3. Deploy

```bash
./scripts/deploy.sh
```

The deployment validates Compose configuration, builds the application image,
waits for PostgreSQL and Redis, applies migrations, collects static assets, runs
Django's deployment checks, starts the application and proxy, and waits for the
health endpoint.

Create the initial cashier account after the first deployment:

```bash
docker compose --env-file .env.production run --rm --no-deps motel-pos \
  python manage.py bootstrap_cashier
```

The command reads `MOTEL_CASHIER_USERNAME` and `MOTEL_CASHIER_PASSWORD` from the
production environment. Remove the password from the environment file after the
account has been created if unattended account recreation is not required.

Useful checks:

```bash
docker compose --env-file .env.production ps
docker compose --env-file .env.production logs --tail=200 motel-pos proxy
curl --fail https://motel-pos.example.internal/api/health/
```

## 4. Add the room detector

Set the detector variables in `.env.production`, confirm the sister image accepts
the four environment variables documented in `compose.yaml`, and deploy it:

```bash
mkdir -p detector-models
./scripts/deploy.sh --detector
```

The detector receives only its camera URL, model path, webhook URL, and webhook
token. It does not receive database credentials. The webhook URL should use the
same HTTPS address staff devices use, because the POS rejects insecure production
webhooks.

For an RTSP/HTTP camera, normal bridged networking is sufficient. For an NVIDIA
GPU, pass the GPU through to the VM, install the matching NVIDIA driver and
NVIDIA Container Toolkit in the VM, then add the detector image's GPU reservation
in a local Compose override. Start with CPU inference and add passthrough only when
measurements show it is necessary.

## 5. Upgrade and roll back

Before upgrading, take a backup. Deploy only reviewed commits or immutable image
tags:

```bash
./scripts/backup.sh
git pull --ff-only
./scripts/deploy.sh --detector
```

To roll back application code, check out the previously deployed tag or commit and
run the deployment script again. Database migrations must be backward compatible;
if they are not, restore the pre-deployment backup.

## 6. Back up and restore

Create a database plus media/report backup:

```bash
./scripts/backup.sh
```

The result is written under `backups/<UTC timestamp>/`. Copy that directory to a
NAS, Proxmox Backup Server, or another machine. A backup left only inside the VM
does not protect against VM storage or Proxmox host failure.

Also schedule Proxmox Backup Server backups of the VM. VM snapshots complement,
but do not replace, the PostgreSQL logical dump.

Restore only during a maintenance window:

```bash
./scripts/restore.sh --backup /absolute/path/to/backups/20260820T120000Z
```

The restore script stops the application, verifies checksums when present,
replaces database objects, restores media/reports, reapplies migrations, and
starts the health-checked services. Test this procedure on a separate VM before
the application holds production data.

## 7. Routine operations

- Apply OS and Docker security updates on a scheduled maintenance day.
- Monitor disk space, container restarts, `/api/health/`, and PostgreSQL backups.
- Keep camera frames out of PostgreSQL; enforce retention in the detector.
- Test a complete restore at least quarterly.
- A single Proxmox host is a single failure domain even when every service is in a
  separate container.
