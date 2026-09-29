# Motel POS Development Changelog

Aggressive notes for Rango and future agents. Keep appending dated sections. Include what changed, why, how it was verified, and what still needs attention.

## 2026-06-16

### Cashier Sales Views

- Added authenticated cashier sales summaries for the fixed motel shifts:
  - Shift 1: 23:00 previous day through 06:59 selected day.
  - Shift 2: 07:00 through 14:59 selected day.
  - Shift 3: 15:00 through 22:59 selected day.
- Added backend endpoint: `GET /api/revenue/sales-summary/`.
- Supported summary views:
  - `view=shift&date=YYYY-MM-DD&shift=1|2|3`: all rooms sold in one shift, entry time, exit time, room type, payment label, and sale amount.
  - `view=day&date=YYYY-MM-DD`: all room types sold by shift, day totals, and sales totals.
  - `view=week&date=YYYY-MM-DD`: total sales per day for the ISO Monday-Sunday week and the week total.
- Added a new `Sales` tab to `/cashier/` with Shift, Day, and Week modes.
- Sale totals use checked-out `OccupancySession` rows where `check_out` lands inside the requested window.
- Sale amount fallback order:
  - `actual_revenue`
  - `estimated_revenue`
  - `price_per_night`
  - configured `Room.price`
- Payment is currently displayed as `Unspecified` because the data model does not yet have a payment method field.

Verification:

- Added API tests for:
  - Shift 1 crossing midnight correctly.
  - Day aggregation by room type and shift.
  - Week aggregation from Monday to Sunday.

Follow-up:

- Add real payment fields to `OccupancySession` or a separate `Payment` model.
- Add cashier checkout controls to set payment method and final amount.
- Decide whether week should stay ISO Monday-Sunday or match motel/accounting week.
- Decide whether Shift 1 should be labeled as previous day night shift or selected day early shift in printed reports.
- Add CSV/PDF export for the new sales views.
- Add manager-only correction workflow for editing payment method, amount, check-in, and checkout time.

## 2026-06-15

### Django Authentication

- Switched browser pages to Django built-in session authentication.
- Added `/login/` using Django `LoginView`.
- Added `/logout/` using Django `LogoutView`.
- Protected these pages with `@login_required`:
  - `/manager/`
  - `/manager/rooms/`
  - `/cashier/`
- Kept JWT auth available for API clients, but browser page access no longer depends on localStorage JWT gates.
- Updated page fetch helpers to send CSRF tokens for session-authenticated writes.
- Legacy `/cashier/login/` redirects to `/login/?next=/cashier/`.

Verification:

- Anonymous manager and cashier pages redirect to login.
- Django session login can load manager and cashier pages.
- Session-authenticated API reads and writes work with CSRF.

Follow-up:

- Review roles/permissions. Right now authenticated users can reach protected pages; staff/role-level access should be tightened before production.
- Remove old JWT-only login UI code from cashier template if no longer needed.
- Add password rotation and staff/admin onboarding notes.

### Public URL and Reverse Proxy

- Added `dev.motelpos.puertocerrado.com` to Django allowed hosts.
- Added `https://dev.motelpos.puertocerrado.com` to CSRF trusted origins.
- Enabled reverse-proxy handling for forwarded host/proto.
- Changed root `/` to redirect to `/manager/` instead of serving the older unauthenticated dashboard.

Verification:

- Backend Host-header test with `Host: dev.motelpos.puertocerrado.com` and `X-Forwarded-Proto: https` returned `200 OK` after auth changes.
- External HTTP root now redirects to `/manager/`.

Follow-up:

- Public HTTPS test previously failed at TLS handshake before Django. Check reverse proxy SSL/SNI/certificate listener if external HTTPS still fails.
- Force HTTPS at the reverse proxy once cert/listener is confirmed.

### Tailscale

- Installed Tailscale on the motel POS server/container.
- Initial run used userspace networking because `/dev/net/tun` was missing.
- After `/dev/net/tun` was added to the container, rebooted the container and switched Tailscale back to normal TUN mode.
- Confirmed:
  - Backend: `Running`
  - Tailscale IP: `100.87.240.92`
  - MagicDNS: `motelpos-dev.tail7d5444.ts.net`
  - App URL: `http://motelpos-dev.tail7d5444.ts.net:8000/`

Follow-up:

- Keep the external reverse proxy pointed at `http://motelpos-dev.tail7d5444.ts.net:8000`.
- Watch for TUN persistence after future container reboots.

### Room Inventory and Manager UI

- Loaded 87 motel rooms from CSV into the database.
- Added migration `apps/rooms/migrations/0009_seed_room_inventory.py`.
- Fields loaded:
  - `room_number` from `cuarto`
  - `price`
  - `edificio`
  - `room_id` as `room_1`, `room_2`, etc.
  - default `sensor_id` as `sensor_room_1`, etc.
- Verified 87 inventory rooms matched CSV for `cuarto`, `Precio`, and `Edificio`.
- Fixed manager page pagination so it walks all pages of `/api/rooms/` instead of only showing the first 27 records.
- Manager room cards now sort numerically.

Follow-up:

- Older/demo rooms were left in place for safety. Decide whether to archive, hide, or delete them.
- If deleting demo rooms, inspect foreign key or string references first.

### Room Configuration

- Moved room editing out of the operational manager dashboard.
- Added room configuration page: `/manager/rooms/`.
- Manager dashboard now links to Room Configuration.
- Clicking a room card sends the user to the room configuration page for that room.
- Updated Django admin Room section to show and inline-edit:
  - `price`
  - `edificio`
  - `ac`
  - `tv`
  - `cuenta_luma`
  - `active`

Follow-up:

- Decide whether the configuration page or Django admin is the long-term source for room edits.
- Add validation around price and room numbering before production use.

### OpenClaw Dreaming / Heartbeats

- Enabled meaningful heartbeat behavior by replacing comments-only `HEARTBEAT.md` with a small operational checklist.
- Heartbeats should now review memory/project notes, check POS health when relevant, and stay quiet with `HEARTBEAT_OK` when nothing useful changed.

Follow-up:

- Keep heartbeat notes short to avoid token burn.
- Use cron for exact reminders and heartbeats for opportunistic checks.

## Current Operational Pointers

- SSH target: `root@motel-pos.coral`
- SSH key: `/home/openclaw/.ssh/openclaw_motelpos_ed25519`
- App path: `/srv/django/myproject`
- Django service should be restarted after code/config edits.
- Tailnet app URL: `http://motelpos-dev.tail7d5444.ts.net:8000/`
- External reverse proxy URL: `https://dev.motelpos.puertocerrado.com`
- Manager: `/manager/`
- Room config: `/manager/rooms/`
- Cashier: `/cashier/`
- Django admin: `/admin/`

## Rango Backlog

- Audit all uncommitted changes and commit in logical chunks.
- Add real payment tracking:
  - payment method
  - amount received
  - change due if cash is used
  - transaction/reference number for ATH/card
  - cashier user
  - correction/audit trail
- Replace `Unspecified` payment label in the Sales tab once payment data exists.
- Add role-based page access:
  - cashier can use `/cashier/`
  - manager can use `/manager/` and `/manager/rooms/`
  - admin/staff can use `/admin/`
- Hide or remove demo rooms after confirming no live records depend on them.
- Add seeded staff/admin users with secure rotated passwords.
- Add export/download buttons for shift/day/week sales reports.
- Add tests for the browser login flow and CSRF writes.
- Review production settings:
  - `DEBUG`
  - `SECURE_SSL_REDIRECT`
  - proxy headers
  - session cookie secure flags
  - CSRF cookie secure flags
- Check reverse proxy TLS from the public internet.
- Confirm systemd service name and document restart/log commands here.
- Add a daily backup/checkpoint plan for the SQLite/Postgres database before the motel starts relying on this operationally.
