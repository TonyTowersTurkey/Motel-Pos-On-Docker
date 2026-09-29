# Rango Action List - Motel POS Django App

Updated: 2026-06-15 00:00 AST

Sync test note: this line exists to verify local edit -> push -> server pull.

## Product Goal

The cashier will use this app during motel operations to track cars coming in, cars staying in rooms, room state, shift revenue, and exceptions. The first usable workflow should be simple: cashier logs in, sees all rooms, immediately knows which rooms have a car present, can manually correct a room state, and can generate the shift/cuadre report.

## GUI Smoke Pass

Pages checked from the live app:

- `/` loads the dashboard shell.
- `/cashier/` loads the cashier login shell.
- `/manager/` loads the manager shell.
- `/api/health/` returns healthy.

Button/API behavior observed:

- Cashier page displays demo credentials `cashier / change_me`, but `/api/auth/login/` returns `401 Invalid credentials`.
- `/api/rooms/` returns `401 Authentication credentials were not provided` without a token.
- The main dashboard and manager pages call authenticated API endpoints but have no login/token flow, so room grids are likely empty or logging errors in the browser.
- Cashier `Send Reading`, `Quick Override`, report, pricing, cuadre, and ledger buttons all depend on authenticated API calls. They cannot be meaningfully exercised until a real cashier login/token flow works.
- `Send Reading` maps to `POST /api/sensors/<room_id>/simulate/`.
- `Quick Override` maps to `POST /api/rooms/<room_id>/override/`.
- `Generate Cuadre` maps to `GET /api/revenue/cuadre/?date=<date>&shift=<shift>` and then tries `POST /api/revenue/generate-shift/`.
- Report buttons map to `POST /api/reports/generate/<type>/`.

## Operating Rules For Hourly Work

- Read this file at the start of every cron run.
- Pick the highest-priority item that is still incomplete and can be advanced safely in one bounded pass.
- Keep each run small: one improvement, focused verification, append a note to `docs/RANGO_LOG.md`.
- Use SSH key-only access. Do not use password SSH.
- Inspect `git status` before editing. Do not revert or overwrite work you did not make.
- Do not expose secret values in docs or reports.

## Priority 0 - Make Cashier Login Real

Problem:

The cashier page advertises `cashier / change_me`, but login currently fails. A cashier cannot reach the actual room control UI.

Actions:

- Add real authentication as a first-class app capability, not just a demo form.
- Create a safe dev/ops path to ensure a cashier user exists, preferably a management command or documented bootstrap command rather than hidden magic in app startup.
- Align displayed demo/default credentials with reality, or remove demo credentials if the system should require explicit provisioning.
- Add a test for successful cashier login using the chosen bootstrap path.

Acceptance Criteria:

- A cashier account can log in through `/cashier/`.
- Login failure shows a clear message.
- The documented bootstrap command can be rerun safely without duplicating users.

Suggested Verification:

- `cd /srv/django/myproject`
- `.venv/bin/python manage.py check`
- Focused auth/cashier tests, if present.
- `curl` login request returns tokens for the provisioned cashier user.

## Priority 0 - Add Multiple Users And Permissions

Problem:

The motel POS will be used by different people. Cashiers, managers, and admins should not all have the same access. The current system has role concepts in the user model, but the GUI and endpoint permissions need to be made real and tested.

Actions:

- Support multiple user accounts with clear roles: cashier, manager, admin.
- Add or verify user creation/editing flows for admins.
- Define permissions by role:
  - Cashier: room status view, vehicle/customer lookup, manual room state correction, current shift/cuadre work.
  - Manager: room setup/editing, pricing, reports, maintenance, user review.
  - Admin: user management, settings, integrations, deployment/ops-only actions.
- Enforce permissions in both API views and GUI navigation.
- Hide or disable buttons a user is not allowed to use.
- Add tests proving restricted users cannot call manager/admin endpoints.

Acceptance Criteria:

- More than one user can exist and log in independently.
- Cashier users cannot access manager/admin-only actions.
- Manager/admin users can access their assigned tools.
- The UI reflects the logged-in user's role.

Suggested Verification:

- Create one cashier, one manager, and one admin in a repeatable bootstrap/dev command.
- Confirm each role can log in.
- Confirm unauthorized API calls return 403 instead of succeeding silently.

## Priority 0 - Fix Cashier Frontend Auth Flow

Problem:

`doLogin()` stores JWT tokens in `localStorage` and then reloads the page. The template still renders the login page unless there is a Django session, so JWT login may never reveal the dashboard. The dashboard also does not clearly bootstrap from an existing token.

Actions:

- On successful JWT login, show the dashboard immediately without a forced reload, or change the backend login to create a Django session intentionally.
- On page load, if a valid access token exists, show dashboard and load rooms.
- Add logout behavior that clears JWT tokens and returns to the login panel.
- Show a clear "session expired, please sign in again" state on 401.

Acceptance Criteria:

- Cashier signs in once and sees room cards without manual reloads.
- Refreshing `/cashier/` keeps the cashier in the dashboard while the token is valid.
- Expired/invalid token returns the cashier to login cleanly.

Suggested Verification:

- Browser smoke test: sign in, refresh, click logout.
- API smoke: `/api/rooms/` returns rooms with the cashier token.

## Priority 0 - Make Core Cashier Buttons Work

Problem:

The cashier's essential buttons are wired to endpoints but are currently blocked by auth and may not all match backend behavior.

Actions:

- Verify `Send Reading`, `Occupied`, `Vacant`, `Maint.`, `Generate Cuadre`, `Revenue Summary`, pricing tier loading, ledger history, and reports after auth is fixed.
- For each broken button, fix either the frontend path/payload or backend endpoint.
- Add minimal tests for the endpoints used by the buttons.

Acceptance Criteria:

- A cashier can click a room and see current status.
- A cashier can send/simulate a reading for a room and see visible feedback.
- A cashier can manually override a room state and see the room card update.
- A cashier can generate the current shift cuadre and see totals.
- Broken API responses show readable cashier-facing errors.

Suggested Verification:

- Exercise the buttons in `/cashier/`.
- Use focused endpoint tests for rooms, sensors, revenue, and reports.

## Priority 0 - Add Customer Vehicle Tracking

Problem:

Customers are tracked only by car, not by personal identity. The app needs a customer/vehicle record that lets the cashier associate a room/session with a car make, model, color, and license plate.

Actions:

- Add a customer or vehicle model focused on vehicle identity:
  - make
  - model
  - color
  - license plate
  - optional notes
  - timestamps
- Decide whether the model should be named `Customer`, `Vehicle`, or `CustomerVehicle`; prefer the name that best fits existing app language.
- Link vehicle/customer records to occupancy or rental/revenue sessions.
- Add cashier-facing create/search/select UI so a cashier can quickly attach a car to a room.
- Add duplicate handling for license plates.
- Add API serializers/viewsets and tests.

Acceptance Criteria:

- Cashier can add a car record without collecting personal guest details.
- Cashier can search by license plate, make, model, color, or room/session context.
- A room/session can show the attached car details.
- The data model does not require names, phone numbers, IDs, or other personal customer fields.

Suggested Verification:

- Create a vehicle/customer through the cashier UI or API.
- Attach it to a room/session.
- Confirm the room card or room detail view shows vehicle details.

## Priority 0 - Make Car Presence Operationally Clear

Problem:

The product is for tracking cars coming in and staying in motel rooms. Current labels are generic room states and raw distances.

Actions:

- Design the room card around cashier decisions: room number, car present/not present/uncertain, parked duration or session duration, last sensor time, and confidence.
- Use clear colors and labels for `Car Present`, `No Car`, `Maintenance`, `Sensor Offline`, and `Needs Review`.
- Preserve raw distance as secondary detail, not the primary cashier signal.
- Add a recent changes/activity panel showing car arrival/departure events.

Acceptance Criteria:

- A cashier can scan the screen in under 5 seconds and know which rooms have cars.
- The room card shows when the vehicle was first detected or when the current session started.
- Sensor offline/uncertain states are visually distinct from vacant.

## Priority 1 - Add Room Edit Page

Problem:

Room setup and correction need a proper manager-facing edit page instead of ad hoc API calls or hardcoded defaults.

Actions:

- Add a room edit page for managers/admins.
- Support editing room number, display name/label, active/inactive state, pricing tier, amenities, maintenance status, sensor mapping, and notes as appropriate.
- Keep dangerous actions like delete/deactivate out of the cashier flow.
- Add validation so room IDs/sensor IDs do not collide.
- Link from manager room list to the room edit page.

Acceptance Criteria:

- Manager can open a room, edit allowed fields, save, and see changes reflected in the room grid.
- Cashier cannot access room edit actions.
- Validation errors are visible and understandable.

## Priority 1 - Stop Health Check From Clearing Cache

Problem:

The health endpoint should not mutate runtime state. Clearing cache from a probe can wipe useful operational data.

Actions:

- Replace cache clear behavior with a harmless read/write/delete of a dedicated healthcheck key, or a non-mutating cache ping if available.
- Add or update a test that proves normal cache keys survive `/api/health/`.

Acceptance Criteria:

- `/api/health/` remains green when DB/cache are healthy.
- Calling `/api/health/` does not delete unrelated cache entries.

## Priority 1 - Wire Sensor Input Through Occupancy State Machine

Problem:

Sensor simulation appears to write readings directly and does not consistently drive the occupancy state machine/revenue session flow.

Actions:

- Ensure sensor input goes through `OccupancyService.process_sensor_reading()`.
- Confirm car-present thresholds and state transitions are centralized.
- Ensure room state, occupancy events, and revenue sessions update from the same workflow.

Acceptance Criteria:

- A reading below the car-present threshold can create/update an occupied/car-present state.
- A departure reading can close or mark the session according to business rules.
- Events and audit trail are written for state changes.

## Priority 1 - Make Cuadre Useful For A Cashier Shift

Problem:

Cuadre/revenue exists, but it needs to match the real cashier workflow.

Actions:

- Confirm shift selection, date defaults, tier counts, ATH total, and saved ledger behavior.
- Make "Generate Cuadre" non-destructive or clearly idempotent.
- Add a print/export/download path if not already present.

Acceptance Criteria:

- Cashier can generate shift totals and use them for bookkeeping.
- Re-running the same shift does not duplicate ledgers unexpectedly.

## Priority 2 - Deployment And Ops Cleanup

Actions:

- Normalize WSGI vs ASGI deployment.
- Track the lockfile or explicitly document why it is ignored.
- Remove hardcoded fallback secrets and align `.env.example` with real settings names.
- Add a short runbook for service status, logs, migrations, tests, backups, and restart procedure.
- Consider adding nginx/TLS or documenting that this is private-network only.

## Priority 2 - Manager/Admin Experience

Actions:

- Decide which actions belong to cashier vs manager.
- Move room creation and dangerous maintenance/config actions out of the cashier flow.
- Add manager-only views for room setup, pricing tiers, maintenance schedule, and reports.

## Current Best Next Task

Start with "Make Cashier Login Real", then "Fix Cashier Frontend Auth Flow". Without those, the cashier cannot use the app and GUI button testing will stay blocked.
