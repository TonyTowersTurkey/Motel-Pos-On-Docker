## 2026-06-15 00:00 AST - Bootstrap cashier login

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: it is the highest-priority incomplete item, and the cashier page advertised a default login while `/api/auth/login/` returned 401 before a real cashier user existed.

Change made: added an idempotent `bootstrap_cashier` management command. It creates or activates the cashier user, enforces the cashier role, and only resets an existing password when `--reset-password` is supplied. Ran the command once for the dev app so the advertised cashier account can obtain JWT tokens.

Files touched:
- `apps/users/management/__init__.py`
- `apps/users/management/commands/__init__.py`
- `apps/users/management/commands/bootstrap_cashier.py`
- `apps/users/tests/test_bootstrap_cashier_command.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2` -> 3 tests OK.
- Live in-memory login smoke against `POST /api/auth/login/` -> HTTP 200, access token present, refresh token present, user role `cashier`.

Next recommended action: fix the cashier frontend JWT flow so successful login shows the dashboard immediately and refresh keeps the cashier signed in while the token is valid.

## 2026-06-15 01:00 AST - Cashier JWT frontend session flow

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the backend cashier bootstrap is now present, and the next blocker was the cashier page storing JWT tokens but forcing a reload back into a template-rendered login state.

Change made: updated the cashier template to switch from login to dashboard immediately after JWT login, bootstrap the dashboard from a stored valid token on page load, clear tokens on logout, stop room polling while logged out, and return to the login panel with a clear session-expired message on authenticated 401 responses.

Files touched:
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_returns_200 -v 2` -> 1 test OK.
- Live curl smoke: `POST /api/auth/login/` with the cashier account returned HTTP 200 and the bearer token could read `GET /api/rooms/` with HTTP 200.

Next recommended action: run a browser smoke pass for `/cashier/` to confirm sign in, refresh persistence, logout, and the first core room buttons from the cashier's point of view.

## 2026-06-15 02:00 AST - Cashier room override API

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: cashier login and token persistence were already advanced, and the next user-visible blocker was the room control UI calling `POST /api/rooms/<room_id>/override/` while the rooms API did not expose that action or return all fields the cashier room cards expect.

Change made: added a `RoomViewSet.override` action for cashier manual Occupied/Vacant/Maintenance overrides, returned the updated room payload, and made manual overrides persist an occupancy event. Expanded the room serializer so `/api/rooms/` includes `current_state`, `last_seen_reading`, and `sensor_healthy` for the cashier room cards.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/serializers.py`
- `apps/occupancy/services.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest -v 2` -> 4 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: verify and fix the remaining cashier core button path for `Send Reading`, because the sensor simulation endpoint currently creates a reading but should be checked for whether it updates room state and returns cashier-friendly feedback.

## 2026-06-15 12:42 AST - Cashier sensor simulation uses occupancy service

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: login, token persistence, and manual room overrides were already advanced; the next cashier-blocking button was `Send Reading`, which posted only `distance_mm` to `/api/sensors/<room_id>/simulate/` while the endpoint still expected `room_id` in the JSON body and bypassed the occupancy service.

Change made: updated sensor simulation to accept the route room id, validate the merged payload, process readings through `OccupancyService.process_sensor_reading()`, persist room `current_state` on sensor-driven transitions, hydrate new state machines from saved room state, and return the reading, event, new state, and room payload for cashier feedback.

Files touched:
- `apps/occupancy/views.py`
- `apps/occupancy/services.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.SensorReadingViewSetTest -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run a browser/curl smoke pass against the live cashier `Send Reading` button using the real cashier token, then continue through the remaining cashier buttons: `Generate Cuadre`, revenue summary, pricing tier loading, ledger history, and reports.

## 2026-06-15 13:00 AST - Cashier room selection feeds controls

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the cashier core button flow now has working auth, manual overrides, and sensor simulation, but clicking a room only wrote to the activity log. Cashiers still had to type a room id before using `Send Reading` or `Quick Override`.

Change made: updated the cashier room grid so clicking a room stores it as the selected room, highlights the selected card, fills the Quick Override room field, and makes `Send Reading` and override actions use that selected room.

Files touched:
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_returns_200 -v 2` -> 1 test OK.

Next recommended action: live browser smoke `/cashier/` with the cashier account: sign in, click a room card, confirm the room is highlighted and the Quick Override room field updates, then test `Send Reading` and `Occupied`/`Vacant` on that selected room.

## 2026-06-15 14:00 AST - Cashier report buttons return JSON

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the cashier core workflow already had auth, room selection, overrides, and sensor simulation advanced. The next bounded button failure was the Reports panel: the frontend posts to `/api/reports/generate/<type>/` and expects JSON, while the backend report view did not accept the path type and returned a PDF response by default.

Change made: updated the report generation endpoint to accept the report type from the URL, require authentication, support the cashier `exceptions` button alias, return JSON metadata for normal button clicks, and preserve PDF output when `?download=true` is requested. Added focused tests for auth enforcement and the `exceptions` path returning JSON.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ReportGenerationViewTest -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: verify/fix the remaining cashier revenue tabs: `Generate Cuadre`, `Revenue Summary`, pricing tier loading, and ledger history, starting with a live authenticated curl or browser smoke for the Cuadre tab.

## 2026-06-15 15:00 AST - Cashier revenue summary endpoint

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: cashier auth, room selection, overrides, sensor simulation, report JSON, and Cuadre JSON were already advanced. The next bounded cashier button failure was `Revenue Summary`, whose frontend called `/api/revenue/summary/` while the live app returned 404.

Change made: added an authenticated revenue summary action backed by the existing revenue engine summary service, exposed it at `/api/revenue/summary/`, and added a focused API test proving the cashier-facing route returns grouped daily totals for the selected date range. Restarted the single `django-dev.service` Gunicorn process so the new URL is active.

Files touched:
- `apps/revenue/views.py`
- `config/urls.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ShiftLedgerViewSetTest.test_revenue_summary_endpoint_returns_days -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.
- Live authenticated curl to `GET /api/revenue/summary/?start_date=2026-06-01&end_date=2026-06-15` -> HTTP 200 with `start`, `end`, and `days` JSON.

Next recommended action: fix the cashier frontend list handling for `Pricing Tiers` and `Ledger History`, because those buttons receive DRF paginated responses with `results` but the template currently treats the response as a raw array.

## 2026-06-15 16:00 AST - Cashier pricing and ledger paginated responses

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: cashier auth, room selection, overrides, sensor simulation, report JSON, Cuadre JSON, and revenue summary were already advanced. The next logged blocker was that the `Pricing Tiers` and `Ledger History` tabs receive DRF paginated responses with `results`, while the cashier template treated each response as a raw array.

Change made: added a small frontend list normalizer for API responses, updated pricing and ledger rendering to use it, hardened money formatting and error messages for those tabs, and added a template regression test that checks the cashier page includes the paginated-response handling.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_handles_paginated_table_responses -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.
- Live authenticated curl smoke: `GET /api/pricing-tiers/` and `GET /api/ledgers/` both returned HTTP 200 paginated JSON dictionaries with `results`.

Next recommended action: browser-smoke `/cashier/` with the cashier account and click the `Pricing Tiers` and `Ledger History` tabs to confirm the tables render correctly, then continue remaining core cashier button checks.

## 2026-06-15 17:00 AST - Cashier room grid handles paginated rooms

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the live authenticated cashier API smoke showed `/api/rooms/` returns DRF paginated JSON with `results`, while the cashier room grid still treated the response as a raw array. That would keep the cashier from scanning rooms or selecting a room for `Send Reading` and manual overrides.

Change made: updated the cashier room loader to normalize `/api/rooms/` through the existing `listResults()` helper before rendering cards and stats. Expanded the cashier template regression test so rooms, pricing tiers, and ledgers all prove paginated-response handling is present.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- Live authenticated curl smoke before the fix confirmed `GET /api/rooms/` returns HTTP 200 with paginated JSON containing `results`.
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_handles_paginated_api_responses -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: fix the cashier Exceptions report button path next; the same live smoke showed `POST /api/reports/generate/exceptions/` returns HTTP 500 with `Report file not found for type=exception`.

## 2026-06-15 18:00 AST - Cashier Exceptions report tolerates CSV-only output

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the previous run identified the cashier Exceptions report button as the next broken core button path: `POST /api/reports/generate/exceptions/` returned HTTP 500 when the generator produced the CSV but no usable PDF file.

Change made: changed the cashier report endpoint so normal JSON button clicks return success when at least one generated report file exists, report any missing generated formats in `missing_files`, and keep `?download=true` strict about requiring a PDF. Added a focused regression test proving the Exceptions report JSON response succeeds when only the CSV exists. Restarted `django-dev.service` so the live Gunicorn app picked up the change.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ReportGenerationViewTest -v 2` -> 3 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- Live authenticated smoke: `POST /api/reports/generate/exceptions/` -> HTTP 200, `success=True`, files `[csv]`, missing_files `[pdf]`.

Next recommended action: browser-smoke the cashier Reports panel, then continue with the next Priority 0 work: make car presence operationally clear on room cards and/or add customer vehicle tracking for license plate, make, model, and color.

## 2026-06-15 19:00 AST - Cashier room selection preserves paginated room list

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the cashier core button flow still depends on selecting a room before using `Send Reading` or manual overrides. The room grid loader already handled DRF pagination, but the selected-room refresh path still passed raw paginated JSON directly to `renderRooms()`.

Change made: updated the cashier `selectRoom()` refresh path to normalize the `/api/rooms/` response with `listResults()` before re-rendering cards, and expanded the template regression test to cover that selected-room path.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_handles_paginated_api_responses -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and click a room card, then `Send Reading`, `Occupied`, and `Vacant` to confirm the selected card remains highlighted and controls continue to use the selected room.

## 2026-06-15 20:00 AST - Cashier room cards use car-presence labels

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the core cashier login and button paths have been advanced, and the next Priority 0 product goal is helping the cashier scan rooms by car presence instead of generic room-state text and raw distances.

Change made: updated the cashier room grid to classify each room into cashier-facing signals: `Car Present`, `No Car`, `Maintenance`, `Sensor Offline`, and `Needs Review`. The stats row now uses those same operational buckets, and room cards show the car-presence label first, with raw distance and reading age as secondary details. Added a focused template regression test for the car-presence labels.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_uses_car_presence_labels -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest -v 2` -> 7 tests OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and confirm the room cards are easy to scan after sending occupied/vacant readings; then add a recent activity panel for arrival/departure events.

## 2026-06-15 21:00 AST - Cashier recent car activity panel

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the previous run made room cards easier to scan with car-presence labels, and the remaining bounded acceptance work called for a recent changes/activity panel showing arrival/departure-style events.

Change made: added a `Recent Car Activity` panel to the cashier sidebar that reads the existing authenticated `/api/events/` feed, maps arrival/check-in events to `Car Arrived`, departure/check-out events to `Car Left`, and shows room, timestamp, source, confidence, and notes. The feed refreshes with the room polling cycle and after cashier sensor/override actions.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_recent_car_activity_panel -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account, send occupied/vacant readings, and confirm the new recent activity panel updates with useful arrival/departure entries.

## 2026-06-15 22:00 AST - Restrict user management by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: cashier login, core buttons, and car-presence visibility have been advanced; the next highest Priority 0 gap was making user-management permissions real so cashiers cannot access manager/admin account tools.

Change made: added an admin-role permission class, made `/api/users/create/` admin-only, and limited `/api/users/` listing to manager/admin roles. Added focused tests proving managers can list users, cashiers cannot list users, admins can create users, and cashiers cannot create users. Restarted `django-dev.service` so the live Gunicorn worker loaded the new permission checks.

Files touched:
- `apps/core/permissions.py`
- `apps/users/views.py`
- `apps/users/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_views.UserListViewAPITest apps.users.tests.test_views.UserCreateAPITest -v 2` -> 6 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- Live authenticated cashier curl to `GET /api/users/` -> HTTP 403.

Next recommended action: continue Priority 0 role work by restricting user detail/update behavior so cashiers can only use `/api/users/profile/`, while manager/admin roles keep appropriate user review or account-management access.

## 2026-06-15 23:00 AST - Restrict user detail records by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run restricted user listing and creation, and the next open role gap was that `/api/users/<id>/` still allowed any authenticated user to retrieve or update user records.

Change made: changed `UserDetailView` to require manager/admin role permission, so cashier accounts cannot use the per-user detail/update endpoint and should use `/api/users/profile/` for self-service profile access. Added focused tests proving admins and managers can retrieve user details while cashiers receive 403 for retrieve and update-by-id attempts.

Files touched:
- `apps/users/views.py`
- `apps/users/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_views.UserProfileAPITest -v 2` -> 4 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: add a restricted self-profile serializer so cashier self-service updates cannot change sensitive account fields such as role, staff status, active status, or password through `/api/users/profile/`.

## 2026-06-16 01:00 AST - Restrict self-profile updates

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: user listing, creation, and per-user detail endpoints were already role-restricted, but the self-profile endpoints still used the full user serializer. That left sensitive fields in the serializer surface for cashier self-service profile updates.

Change made: added a dedicated `SelfProfileSerializer` that allows contact/profile fields while making username, role, active/staff/superuser flags, timestamps, and password handling unavailable through self-profile updates. Wired both `/api/users/profile/` and `/api/users/profile/update/` to the restricted serializer and added tests for allowed contact edits plus blocked privilege changes.

Files touched:
- `apps/users/serializers.py`
- `apps/users/views.py`
- `apps/users/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_views.SelfProfileAPITest -v 2` -> 4 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue Priority 0 role work by adding a small repeatable bootstrap path for manager/admin dev accounts, then smoke-test that cashier, manager, and admin roles can each log in and receive the expected endpoint access.

## 2026-06-16 02:00 AST - Bootstrap standard motel role accounts

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: cashier login, cashier button flow, and recent role restrictions were already advanced. The next recommended Priority 0 gap was a repeatable dev/ops path to provision cashier, manager, and admin accounts so each role can be smoke-tested independently.

Change made: added a `bootstrap_motel_users` management command that idempotently ensures standard cashier, manager, and admin accounts exist, keeps existing passwords unless `--reset-password` is requested, enforces unique usernames, activates the accounts, and marks the admin account as Django staff. Added focused tests for idempotency, password-reset behavior, role assignment, and JWT login for all three bootstrapped roles.

Files touched:
- `apps/users/management/commands/bootstrap_motel_users.py`
- `apps/users/tests/test_bootstrap_cashier_command.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2` -> 6 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run the new bootstrap command in the dev environment with the intended credentials, then smoke-test cashier, manager, and admin logins plus expected 403/200 access for role-restricted endpoints.

## 2026-06-16 03:00 AST - Provision live standard role accounts

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run added the repeatable role bootstrap command, and the next safest bounded step was to run it in the dev environment and prove the three standard roles can log in with the expected endpoint access.

Change made: ran the idempotent `bootstrap_motel_users` command in the dev environment. The cashier and manager accounts were already present, and the standard admin account was created. No existing passwords were reset.

Files touched:
- `docs/RANGO_LOG.md`

Runtime state touched:
- Dev database user records for standard motel roles.

Verification:
- `.venv/bin/python manage.py bootstrap_motel_users` -> cashier unchanged, manager unchanged, admin created.
- Live authenticated smoke with no token output: cashier, manager, and admin each logged in through `POST /api/auth/login/` with their expected role.
- Live role access smoke: cashier `GET /api/users/` -> HTTP 403; manager `GET /api/users/` -> HTTP 200; admin `GET /api/users/` -> HTTP 200.

Next recommended action: continue Priority 0 role work by making the GUI reflect the logged-in role, starting with hiding or disabling manager/admin-only navigation and buttons for cashier users.

## 2026-06-16 04:00 AST - Hide manager-only cashier controls by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run provisioned cashier, manager, and admin accounts and recommended making the GUI reflect the logged-in role. A bounded next step was to keep cashier users focused on room and shift work by hiding manager/admin-oriented controls in the cashier UI.

Change made: added role-aware visibility handling to the cashier page. The authenticated user role is now available to the frontend, manager-only Pricing Tiers, Ledger History, and Reports controls are marked with `data-min-role="manager"`, and `applyRoleVisibility()` hides those controls for cashier users while leaving them visible for manager/admin roles. Added a focused template test to guard the role markers and visibility helper.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_marks_manager_only_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` as cashier and manager/admin to confirm cashier sees only operational room/shift controls while manager/admin users still see Pricing Tiers, Ledger History, and Reports.

## 2026-06-16 05:00 AST - Restrict manager pages by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run hid manager-only controls in the cashier UI, but the manager template pages themselves were still only login-protected. A cashier session should not be able to open `/manager/` or `/manager/rooms/` directly.

Change made: added a small manager/admin role guard to the manager dashboard and room configuration template views. Cashier users now receive 403 for those pages, while manager and admin users can still load them. Restarted `django-dev.service` so the live Gunicorn worker picked up the view permission change.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.ManagerViewTest -v 2` -> 8 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- Live session curl smoke: cashier `/manager/` -> HTTP 403; cashier `/manager/rooms/` -> HTTP 403; manager `/manager/` -> HTTP 200; manager `/manager/rooms/` -> HTTP 200.

Next recommended action: continue Priority 0 role work by applying the same role boundary to manager-only configuration APIs that are still merely authenticated, starting with pricing tiers and amenities.

## 2026-06-16 06:00 AST - Preserve cashier login next redirect safely

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: cashier login is now routed through Django session auth, and the legacy `/cashier/login/` URL still feeds into that path. A bounded improvement was to harden that redirect so cashier return URLs with their own query strings survive intact instead of being hand-concatenated into the login query string.

Change made: changed the legacy cashier login redirect to build the login query string with `urlencode`, preserving nested `next` values such as `/cashier/?tab=rooms&room=101`. Added a focused regression test for that redirect behavior.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_legacy_cashier_login_redirect_preserves_next_query` -> 1 test OK; system check reported no issues.

Next recommended action: continue Priority 0 role/API boundary work by applying role permissions to manager-only configuration API endpoints, starting with pricing tiers and amenities, then add focused 403/200 tests for cashier vs manager/admin.

## 2026-06-16 07:00 AST - Restrict configuration APIs by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous role work protected manager pages, but manager-only configuration APIs for pricing tiers, amenities, and room amenities were still available to any authenticated user. This was the next bounded role/API boundary improvement.

Change made: changed `PricingTierViewSet`, `AmenityViewSet`, and `RoomAmenityViewSet` to require manager/admin role permission. Added focused tests proving manager users can list these configuration resources while cashier users receive 403 responses.

Files touched:
- `apps/rooms/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.PricingTierViewSetTest apps.revenue.tests.test_views.AmenityViewSetTest apps.revenue.tests.test_views.RoomAmenityViewSetTest -v 2` -> 6 tests OK.
- `systemctl restart django-dev.service` -> completed.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue Priority 0 role/API boundary work by reviewing remaining authenticated manager/admin configuration endpoints, especially maintenance, rental sessions, and revenue ledger write actions, and add cashier 403 tests for the next smallest unsafe surface.

## 2026-06-16 08:00 AST - Restrict maintenance logs by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run protected pricing and amenity configuration APIs and identified maintenance, rental sessions, and revenue ledger write actions as the next role-boundary surfaces. Maintenance logs were the smallest unsafe surface because `/api/maintenance/` was still available to any authenticated user.

Change made: changed the maintenance log API to require manager/admin role permission and added focused tests proving manager users can list maintenance logs while cashier users receive 403.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.MaintenanceLogViewSetAPITest -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service` -> completed.
- Live authenticated smoke: cashier `GET /api/maintenance/` -> HTTP 403; manager `GET /api/maintenance/` -> HTTP 200.

Next recommended action: continue Priority 0 role/API boundary work by restricting the next smallest unsafe operational surface, starting with rental sessions or revenue ledger write actions, while preserving cashier access to the room controls needed for daily operations.

## 2026-06-16 09:00 AST - Restrict dynamic pricing rules by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: previous role-boundary runs protected manager pages, pricing tiers, amenities, and maintenance logs. Dynamic pricing rules were still only authenticated and the existing app router entry was not mounted in the main API router, so this was the next small manager/admin configuration surface to lock down and expose intentionally.

Change made: registered `/api/pricing-rules/` in the main API router with an explicit DRF basename, updated the existing rooms app router registration the same way, and changed `DynamicPricingRuleViewSet` to require manager/admin role permission. Added focused API tests proving manager users can list dynamic pricing rules while cashier users receive 403.

Files touched:
- `config/urls.py`
- `apps/rooms/urls.py`
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.DynamicPricingRuleViewSetAPITest -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by restricting rental session or revenue ledger write actions, while preserving cashier access to daily room controls and shift/cuadre reads.

## 2026-06-16 10:00 AST - Restrict raw shift ledgers by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: previous role-boundary runs protected manager pages, pricing tiers, amenities, maintenance logs, and dynamic pricing rules. The next smallest unsafe revenue surface was raw `/api/ledgers/` access, which allowed any authenticated cashier to list or create shift ledger rows outside the cashier-facing Cuadre workflow.

Change made: added role-aware permissions to `ShiftLedgerViewSet` so cashier users keep the intended `/api/revenue/cuadre/`, `/api/revenue/summary/`, `/api/revenue/sales-summary/`, and `/api/revenue/generate-shift/` actions, while raw ledger CRUD and ledger history endpoints now require manager/admin role access. Added focused tests for manager list access, cashier 403 on raw ledger list/create, and cashier Cuadre read preservation. Restarted `django-dev.service` so the live Gunicorn app picked up the permission change.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ShiftLedgerViewSetTest -v 2` -> 9 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by restricting rental session endpoints next, while preserving cashier access to room controls and current shift/cuadre workflows.

## 2026-06-16 11:00 AST - Restrict rental sessions by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: previous role-boundary runs protected manager pages, configuration APIs, maintenance logs, dynamic pricing rules, and raw shift ledgers. The next logged unsafe surface was `/api/rental-sessions/`, which was still open to any authenticated user even though rental session CRUD is manager/admin work.

Change made: changed `RentalSessionViewSet` to require manager/admin role permission and added focused API tests proving manager users can list rental sessions while cashier users receive 403 for list and create attempts. Restarted `django-dev.service` so the live Gunicorn app picked up the permission change.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RentalSessionViewSetAPITest -v 2` -> 3 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by reviewing occupancy event and audit-log access next, preserving cashier access to the recent car activity feed while keeping audit/admin history manager-only.

## 2026-06-16 12:00 AST - Restrict occupancy history writes and audit logs by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: previous role-boundary runs protected manager pages, configuration APIs, maintenance logs, dynamic pricing rules, raw shift ledgers, and rental sessions. The next logged unsafe surface was occupancy event and audit-log access: cashiers need to read `/api/events/` for the Recent Car Activity panel, but should not directly write event history or read audit/admin history.

Change made: changed `OccupancyEventViewSet` to allow cashier-or-above read access for list/retrieve while requiring manager/admin role permission for event writes. Changed `AuditLogViewSet` to require manager/admin role permission. Added focused API tests proving cashier users can still read occupancy events, cashier event creation is blocked with 403, managers can create events, cashier audit-log access is blocked, and managers can read audit logs. Restarted `django-dev.service` so the live Gunicorn app picked up the permission change.

Files touched:
- `apps/occupancy/views.py`
- `apps/occupancy/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_views -v 2` -> 5 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by reviewing raw sensor-reading history access next. Preserve cashier access to `POST /api/sensors/<room_id>/simulate/` for the Send Reading button, but consider making raw sensor history list/create/update/delete manager-only.


## 2026-06-16 13:00 AST - Restrict raw sensor history by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: previous role-boundary runs protected manager pages, configuration APIs, maintenance logs, dynamic pricing rules, raw shift ledgers, rental sessions, occupancy event writes, and audit logs. The next logged unsafe surface was raw sensor-reading history access. Cashiers still need `POST /api/sensors/<room_id>/simulate/` for the Send Reading button, but broad sensor history list/create/update/delete belongs to manager/admin users.

Change made: changed `SensorReadingViewSet` to use role-aware permissions: cashier-or-above for the `simulate` action and manager/admin for raw sensor reading history and CRUD actions. Added focused API tests proving cashier users cannot list or directly create raw sensor readings, managers can list sensor history, and cashiers can still simulate a room sensor reading through the cashier flow. Restarted `django-dev.service` so the live Gunicorn app picked up the permission change.

Files touched:
- `apps/occupancy/views.py`
- `apps/occupancy/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_views -v 2` -> 9 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by reviewing user-management API access next, especially whether cashier users can list or mutate users, while preserving their own authenticated cashier session needs.

## 2026-06-16 14:00 AST - Restrict user detail mutations to admins

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: previous role-boundary runs protected operational and history endpoints, and the next logged surface was user-management API access. The user detail endpoint allowed manager/admin review and update; this run kept manager review access but reserved user-account mutations for admins.

Change made: changed `UserDetailView` to allow safe read methods for manager/admin users while requiring the admin role for PUT/PATCH account changes. Added focused tests proving admins can update a user, managers can still retrieve user details, and managers receive 403 when attempting to update users.

Files touched:
- `apps/users/views.py`
- `apps/users/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_views.UserProfileAPITest -v 2` -> 6 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by reviewing report-generation API access next, keeping cashier access to current-shift cuadre workflows while reserving broader daily sales/occupancy/exception report generation for manager/admin users.

## 2026-06-16 15:00 AST - Restrict broad report generation by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run locked user-account mutations to admins and recommended reviewing report-generation API access next. Broad daily occupancy, daily sales, and exception report generation is manager/admin work, while cashier shift/cuadre endpoints should remain available for daily operations.

Change made: changed the standalone `/api/reports/generate/<type>/` endpoint to require both authentication and the manager/admin role permission. Updated focused report endpoint tests so manager users can still generate report metadata, unauthenticated callers keep the existing 401 response, and cashier users now receive 403 for broad report generation.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ReportGenerationViewTest -v 2` -> 4 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role/API boundary work by reviewing cashier-visible manager-only report buttons in the cashier template, hiding broad report generation from cashier users while keeping current-shift Cuadre and cashier summaries visible.

## 2026-06-16 16:00 AST - Guard broad report buttons by role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run made broad report generation manager/admin-only at the API layer and recommended aligning the cashier template. This is the next bounded role/UI boundary improvement while preserving cashier access to current-shift Cuadre and sales summaries.

Change made: added a client-side role guard to the cashier report generation handler so stale or accidentally exposed broad report buttons stop with a clear manager-account message before calling the manager-only API. Expanded the cashier template regression test to cover the report panel and guard text.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_marks_manager_only_controls -v 2 -> 1 test OK.
- .venv/bin/python manage.py check -> OK.

Next recommended action: continue Priority 0 role/UI boundary work with a browser smoke as cashier and manager/admin to confirm broad report controls stay hidden for cashiers and available for manager/admin users, then review any remaining cashier-visible manager-only actions.

## 2026-06-16 17:00 AST - Guard manager-only cashier tabs

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run hid broad report controls for cashier users and recommended continuing the role/UI boundary pass. The remaining bounded UI gap was that manager-only cashier tabs were hidden by role, but the shared tab switcher did not itself reject a protected tab if a stale or programmatic click reached it.

Change made: added a role access helper to the cashier template and made `switchTab()` stop before activating manager-only sections for cashier users, logging a clear manager-account message instead. Expanded the existing cashier template regression test to prove the guard text and role-check hook are present.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_marks_manager_only_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue Priority 0 role/UI boundary work by browser-smoking `/cashier/` as cashier and manager/admin to confirm protected tabs stay blocked for cashiers and available for manager/admin users, then review any remaining cashier-visible manager-only controls.

## 2026-06-16 18:00 AST - Add searchable vehicle records API

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: cashier login, core room buttons, car-presence display, and the role-boundary pass have been advanced. The next highest Priority 0 product gap is vehicle tracking, and a bounded first slice is a backend vehicle record/API that captures make, model, color, license plate, and notes without personal guest identity fields.

Change made: added a new `guests` app with a `Vehicle` model, normalized nonblank license-plate duplicate handling, admin registration, serializer, authenticated searchable `/api/vehicles/` ViewSet, initial migration, and focused API tests for cashier create/search, duplicate rejection, manager read access, and unauthenticated rejection. Applied the new `guests` migration and restarted `django-dev.service` so the live dev API is available.

Files touched:
- `apps/guests/__init__.py`
- `apps/guests/admin.py`
- `apps/guests/apps.py`
- `apps/guests/models.py`
- `apps/guests/serializers.py`
- `apps/guests/views.py`
- `apps/guests/migrations/__init__.py`
- `apps/guests/migrations/0001_initial.py`
- `apps/guests/tests/__init__.py`
- `apps/guests/tests/test_views.py`
- `config/settings.py`
- `config/urls.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views -v 2` -> 5 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py makemigrations --check --dry-run guests` -> no changes detected.
- `.venv/bin/python manage.py migrate guests` -> `guests.0001_initial` applied OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.
- Live authenticated smoke without printing tokens: cashier login returned an access token and `GET /api/vehicles/` returned HTTP 200 paginated JSON.

Next recommended action: link vehicle records to the active room/occupancy workflow, starting with a small room/session attachment API so a cashier can associate a selected vehicle with the currently selected room.

## 2026-06-16 19:00 AST - Attach vehicles to rooms

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the previous run added searchable vehicle records, and the next smallest useful product slice was linking one of those vehicle records to the room the cashier is actively managing.

Change made: added a nullable `current_vehicle` relationship on rooms, exposed the nested vehicle record in room API responses, and added `POST /api/rooms/<room_id>/vehicle/` so cashier-or-above users can attach a vehicle by `vehicle_id` or clear the current room vehicle.

Files touched:
- `apps/rooms/models.py`
- `apps/rooms/serializers.py`
- `apps/rooms/views.py`
- `apps/rooms/migrations/0010_room_current_vehicle.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest -v 2` -> 10 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py makemigrations --check --dry-run rooms` -> no changes detected.
- `.venv/bin/python manage.py migrate rooms` -> `rooms.0010_room_current_vehicle` applied OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.
- Live authenticated smoke without printing tokens: cashier `GET /api/rooms/` returned HTTP 200 and room payloads include `current_vehicle`.

Next recommended action: add the cashier UI controls to create/search/select a vehicle and attach or clear it from the selected room using the new `/api/rooms/<room_id>/vehicle/` endpoint.

## 2026-06-16 20:00 AST - Cashier vehicle lookup and attach UI

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records and the room attach API already existed, and the next recommended Priority 0 slice was giving cashiers a UI to search/create/select a vehicle and attach or clear it from the selected room.

Change made: added a cashier sidebar Vehicle Lookup panel with vehicle search, create-and-attach, attach result, and clear-room-vehicle controls. Room cards now show an attached vehicle label when `current_vehicle` is present, and selecting/loading rooms keeps the selected-room vehicle hint in sync.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account: select a room, search an existing vehicle, attach it, create-and-attach a new vehicle, clear it, and confirm the room card updates after each action.


## 2026-06-16 21:00 AST - Clearer cashier vehicle attach feedback

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the previous run added vehicle lookup/create/attach controls, and the next safest bounded slice was making the cashier-facing attach/clear result obvious in the same panel instead of leaving stale search results after the room vehicle changes.

Change made: the cashier Vehicle Lookup panel now writes success/error messages directly into the vehicle results area after attach, clear, and create failures; attach now returns the updated room so create-and-attach only clears the form after the room update succeeds.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and exercise search, attach, create-and-attach, and clear against the live app; if that passes, move to showing attached vehicle details in the selected room/activity context.

## 2026-06-16 22:00 AST - Keep selected vehicle hint fresh across paginated room loads

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the previous runs added vehicle attach controls and clearer feedback. While reviewing that flow, the remaining bounded UI risk was that the selected-room vehicle hint only refreshed when the selected room appeared in the current `/api/rooms/` payload, which can be paginated.

Change made: changed the cashier room refresh path to update the selected room's vehicle hint from the room list when available, and otherwise fetch the selected room detail before clearing the hint. Expanded the vehicle UI template regression test to cover the fallback detail refresh.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and exercise search, attach, create-and-attach, clear, refresh, and paginated/selected-room behavior against the live app.

## 2026-06-16 23:00 AST - Selected room vehicle details

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records, room attachment, and the cashier attach UI already exist. The next bounded improvement was making the selected-room context show attached car details clearly instead of only a one-line label on the room card or lookup hint.

Change made: added a selected-room vehicle detail block to the cashier Vehicle Lookup panel. It now shows the attached plate, color/make/model details, and notes when present, and falls back to a clear "no vehicle attached" message when the room has no current vehicle.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and exercise search, attach, create-and-attach, clear, refresh, and selected-room detail rendering against the live app.

## 2026-06-17 00:00 AST - Vehicle attach activity events

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records, room attachment, and cashier UI controls already exist. The next bounded gap was making attach/clear actions visible in the existing occupancy activity history so the selected room context records vehicle changes alongside other cashier-visible room activity.

Change made: added `vehicle_attached` and `vehicle_cleared` occupancy event types, records a manual-input occupancy event whenever a cashier attaches or clears a room vehicle, and maps those event types to readable `Vehicle Attached` / `Vehicle Cleared` labels in the cashier Recent Car Activity panel.

Files touched:
- `apps/occupancy/models.py`
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `apps/revenue/tests/test_views.py`
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_recent_car_activity_panel -v 2` -> 11 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: browser-smoke `/cashier/` with the cashier account and verify that attaching and clearing a vehicle updates both the selected-room vehicle detail block and the Recent Car Activity panel.

## 2026-06-17 01:00 AST - Search vehicles by attached room

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records, room attachment, cashier UI, and vehicle activity events are already in place. The remaining acceptance gap I advanced this run was searching by room/session context, so a cashier can find a vehicle through the room it is currently attached to, not only by plate/make/model/color.

Change made: expanded the vehicle API search fields to include the currently attached room id and room number, and de-duplicated search results when related-room matches are involved. Added a focused regression test proving a cashier can search vehicles by the attached room context.

Files touched:
- `apps/guests/views.py`
- `apps/guests/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views -v 2` -> 6 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: browser-smoke `/cashier/` with the cashier account and verify the Vehicle Lookup panel can find attached cars by plate, make/model/color, and attached room context; then tighten any UI copy or search affordance if the room-context behavior is not obvious.

## 2026-06-17 02:00 AST - Cashier room-context vehicle search button

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records, room attachment, cashier UI, activity events, and backend search by attached room are already in place. The next bounded improvement was making room-context vehicle lookup obvious to the cashier instead of requiring them to know that room ids/numbers work in the generic search field.

Change made: added a `Find Selected Room Vehicle` action to the cashier Vehicle Lookup panel. It fills the vehicle search field with the currently selected room id or override room value and runs the existing vehicle search flow, with a clear error if no room is selected. Updated the search placeholder and template regression test to cover room-context search affordance.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and verify the Vehicle Lookup panel can find attached cars by plate, make/model/color, and the new selected-room search button; then move on to linking vehicles to active occupancy/revenue sessions if that workflow still needs session-level history.

## 2026-06-17 04:00 AST - Rental sessions remember vehicle

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records, room attachment, cashier UI, activity events, and room-context search are already in place. The remaining acceptance gap was linking vehicle/customer records to the actual occupancy or rental workflow, not just the room's current state.

Change made: added an optional vehicle relationship to rental sessions and exposed it through the rental-session API with a write-only `vehicle_id` field and read-only nested vehicle details. Added a focused manager API test proving a rental session can be created with an attached vehicle while existing cashier rental-session restrictions still hold.

Files touched:
- `apps/rooms/models.py`
- `apps/rooms/serializers.py`
- `apps/rooms/migrations/0011_rental_session_vehicle.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RentalSessionViewSetAPITest -v 2` -> 4 tests OK.
- `.venv/bin/python manage.py makemigrations --check --dry-run rooms` -> no changes detected.
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py migrate rooms` -> `rooms.0011_rental_session_vehicle` applied OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: add a small cashier/manager flow that creates or updates an active rental session from the selected room and carries the room's attached vehicle into that session automatically.

## 2026-06-17 05:00 AST - Cashier auth flow regression coverage

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the live cashier account and login path now work, and the next highest safe gap was protecting the fragile cashier JWT/session handoff so future changes do not regress dashboard bootstrap, expired-token recovery, or logout token cleanup.

Change made: added a focused cashier template regression test that asserts the page includes the JWT bootstrap path from an existing access token, profile fetch, dashboard reveal, 401 session-expired handling, localStorage token cleanup, and logout API call.

Operational check: ran the idempotent cashier bootstrap command; the cashier user was unchanged. Verified the API login returns a successful cashier role response without printing token values. Verified the live Django login flow posts through `/login/` and lands on `/cashier/` with the dashboard present.

Files touched:
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account from a real browser: sign in, refresh, click logout, then force an invalid stored access token and verify the page returns to login with the session-expired message.

## 2026-06-17 06:00 AST - Cuadre honors selected shift

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: cashier login and auth flow are now usable, so the next bounded cashier workflow improvement was tightening the Generate Cuadre button path. The UI lets a cashier select shifts 1, 2, or 3, but the backend Cuadre and auto-save endpoints were computing with the revenue engine default shift instead of passing the selected shift through.

Change made: passed the selected `shift_number` into `revenue_engine.compute_shift_for_day()` for both `/api/revenue/cuadre/` and `/api/revenue/generate-shift/`, and updated the endpoint copy to say shifts 1, 2, or 3. Added focused tests proving both endpoints call the engine with the selected shift.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ShiftLedgerViewSetTest.test_cuadre_uses_selected_shift_number apps.revenue.tests.test_views.ShiftLedgerViewSetTest.test_generate_shift_uses_selected_shift_number -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: browser-smoke `/cashier/` with the cashier account and exercise Generate Cuadre for shifts 1, 2, and 3, confirming the displayed shift and saved ledger match the selected shift.

## 2026-06-17 07:00 AST - Room amenity actions require manager role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the cashier role should be able to view room status, correct room state, and work vehicle/cashier flows, but room setup/editing belongs to managers/admins. While checking the room API permissions, the custom `add_amenity` room configuration action was still available through the cashier-or-above fallback.

Change made: moved room amenity custom actions (`amenities` and `add_amenity`) plus the room dashboard summary action into the manager/admin-only action set for `RoomViewSet`. Added focused tests proving a cashier gets 403 and does not create a room amenity, while a manager can still add one.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest.test_cashier_cannot_add_room_amenity_configuration apps.rooms.tests.test_views.RoomViewSetAPITest.test_manager_can_add_room_amenity_configuration -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role-boundary hardening by checking the remaining custom ViewSet actions for manager/admin-only behavior, especially any room setup, pricing, report, or admin-style actions reached outside normal CRUD.

## 2026-06-17 08:00 AST - Room custom-action permission coverage

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the 07:00 run moved room amenity and dashboard custom actions behind manager/admin permissions, but only the `add_amenity` write path had focused coverage. The next bounded hardening step was to protect the remaining custom room setup endpoints from future regression.

Change made: added regression tests proving cashiers cannot list room amenity configuration through `/api/rooms/<room>/amenities/` or read the room dashboard summary through `/api/rooms/dashboard/`, while managers can still use both endpoints.

Files touched:
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest.test_cashier_cannot_list_room_amenity_configuration apps.rooms.tests.test_views.RoomViewSetAPITest.test_manager_can_list_room_amenity_configuration apps.rooms.tests.test_views.RoomViewSetAPITest.test_cashier_cannot_read_room_dashboard_summary apps.rooms.tests.test_views.RoomViewSetAPITest.test_manager_can_read_room_dashboard_summary -v 2` -> 4 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue Priority 0 role-boundary hardening by checking occupancy and revenue custom actions for the same cashier-vs-manager split, especially endpoints that expose raw history, reports, pricing, or ledger data.

## 2026-06-17 09:00 AST - Raw occupancy sessions require manager role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous runs hardened room setup and dashboard custom actions. The next bounded role-boundary gap was the raw `/api/sessions/` occupancy-session API, which exposes guest/contact/revenue session fields and checkout mutation outside the cashier-facing room, vehicle, sales summary, and Cuadre flows.

Change made: restricted `OccupancySessionViewSet` to manager/admin users and added focused regression tests proving managers can list raw occupancy sessions while cashiers cannot list sessions or call the raw checkout action.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.OccupancySessionViewSetTest -v 2` -> 3 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role-boundary hardening by checking occupancy event and sensor history endpoints for expected cashier-vs-manager access, keeping cashier-only access limited to room status, selected-room controls, vehicle lookup/attach, sales summary, and Cuadre.

## 2026-06-17 10:00 AST - Vehicle deletes require manager role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run's recommended occupancy/sensor check was already covered in `apps/occupancy/views.py` and `apps/occupancy/tests/test_views.py`. The next bounded role-boundary gap was the vehicle/customer API: cashiers need create/search access for the front-desk car workflow, but deleting vehicle records is a manager/admin action because it can erase operational history.

Change made: changed `VehicleViewSet` to use action-specific permissions, keeping cashier-or-above access for normal vehicle lookup/create/update while reserving `DELETE /api/vehicles/<id>/` for manager/admin users. Added focused tests proving cashiers cannot delete vehicle records and managers still can.

Files touched:
- `apps/guests/views.py`
- `apps/guests/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views.VehicleViewSetAPITest -v 2` -> 8 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: continue Priority 0 role-boundary hardening by checking vehicle update permissions and cashier UI expectations; decide whether cashiers should edit vehicle details after creation or whether edits should be manager-only with a narrow cashier "attach/select/create" workflow.


## 2026-06-17 11:00 AST - Vehicle edits require manager role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the previous run left vehicle update permissions as the next focused role-boundary decision. Cashiers need vehicle lookup/create for the front-desk car workflow, but broad edits to existing vehicle records can rewrite operational history and should be manager/admin-only.

Change made: changed `VehicleViewSet` permissions so `update`, `partial_update`, and `destroy` require manager/admin access while list/retrieve/search/create remain available to cashier-or-above users. Added regression tests proving cashiers cannot PATCH vehicle records while managers still can.

Files touched:
- `apps/guests/views.py`
- `apps/guests/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views.VehicleViewSetAPITest -v 2` -> 10 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue Priority 0 cashier workflow hardening by smoke-testing the cashier vehicle UI after this permission split: create and attach a vehicle from `/cashier/`, search it, clear/re-attach it, and confirm the UI does not depend on cashier PATCH access.

## 2026-06-17 12:00 AST - Cashier vehicle API errors are readable

Action-list item: Priority 0 - Add Customer Vehicle Tracking / cashier workflow hardening.

Why this item: the previous run made vehicle edits manager-only and recommended smoke-testing the cashier vehicle UI. The UI correctly uses the room vehicle attach endpoint instead of cashier PATCH access, but validation failures such as duplicate license plates were still surfaced as generic create/attach/clear failures.

Change made: added cashier-facing API error formatting in the cashier template so structured DRF errors are reduced to readable messages, and wired vehicle search, attach, clear, and create failures to display the specific backend detail in the vehicle panel.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_formats_vehicle_api_errors apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue the cashier vehicle UI smoke path with an authenticated API/browser check that creates a vehicle, attaches it to a selected room, clears it, and confirms recent activity shows the vehicle attach/clear events.

## 2026-06-17 13:00 AST - Room vehicle attach updates active rental session

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records can already be created, attached to rooms, and stored on rental sessions, but the cashier attach flow still only updated the room. The next bounded session-history gap was carrying the attached car onto any active checked-in rental session for that room.

Change made: updated the room vehicle attach endpoint so attaching a vehicle to a room also updates the latest active checked-in rental session for that room when one exists. Added a focused regression test proving a cashier room attach writes the vehicle onto the active rental session while preserving the existing room attach behavior.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest.test_attach_vehicle_carries_to_active_rental_session apps.rooms.tests.test_views.RoomViewSetAPITest.test_cashier_can_attach_vehicle_to_room -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: run an authenticated live cashier API or browser smoke that creates a vehicle, attaches it to a selected room with an active rental session, clears it from the room, and confirms the rental session keeps the attached vehicle for history.

## 2026-06-17 14:00 AST - Room vehicle clear preserves rental-session history

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the previous run carried cashier vehicle attaches onto active rental sessions. The next bounded gap was preserving that session history when the cashier clears the room current vehicle after the car leaves or the room is corrected.

Change made: added a focused regression test proving the cashier room-vehicle clear action removes the room current vehicle while leaving the active rental session vehicle attached for historical reporting.

Files touched:
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest.test_clear_room_vehicle_preserves_active_rental_session_vehicle -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run an authenticated live cashier API/browser smoke that creates a vehicle, attaches it to a selected room, clears it, and confirms the room card and recent activity panel show the attach/clear flow clearly.

## 2026-06-17 21:32 AST - Recent activity feed filters car events

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the previous run recommended confirming the cashier vehicle attach/clear flow is visible in recent activity. A bounded backend/UI step was to keep the activity panel focused on car and room-state events instead of dumping unrelated occupancy history.

Change made: added comma-separated `event_type` filtering to the occupancy event API, updated the cashier recent activity request to fetch only the car/room events it displays, and added a focused regression test proving cashier users can filter the feed to car events while excluding maintenance noise.

Files touched:
- `apps/occupancy/views.py`
- `apps/occupancy/tests/test_views.py`
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_views.OccupancyEventViewSetAPITest -v 2` -> 4 tests OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: run an authenticated live cashier API/browser smoke that creates a vehicle, attaches it to a selected room, clears it, and confirms the filtered recent activity panel shows the attach/clear entries without unrelated maintenance events.

## 2026-06-17 22:00 AST - Vehicle search includes rental-session history

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: vehicle records can already be created, attached to rooms, and carried onto rental sessions. The remaining acceptance detail I advanced was vehicle search by room/session context, so cashiers and managers can find a car from historical rental-session context even after it is no longer the room's current attached vehicle.

Change made: expanded vehicle API search fields to include related rental-session room ids, statuses, and notes, while preserving the existing distinct search behavior for room joins. Added a focused regression test proving a cashier can search vehicles by a rental-session room context.

Files touched:
- `apps/guests/views.py`
- `apps/guests/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views -v 2` -> 11 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: run an authenticated live cashier API/browser smoke that creates a vehicle, attaches it to a selected room, clears it, and confirms vehicle lookup can find the car by plate, current room context, and rental-session history.

## 2026-06-17 23:00 AST - Vehicle detail edits are manager-only

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the action list prioritizes real role boundaries for cashiers, managers, and admins, and the previous vehicle workflow left a risky mismatch where cashiers could still edit existing vehicle records from the API/UI. Cashiers need create/search/attach for front-desk flow, but broad edits to existing vehicle identity should be manager/admin-only.

Change made: restricted vehicle `update` and `partial_update` actions to manager/admin users while preserving cashier search/create/delete-denial behavior. Updated the cashier vehicle UI so edit controls only render for manager-or-above users and guarded direct edit/save calls with a cashier-facing manager-required message.

Files touched:
- `apps/guests/views.py`
- `apps/guests/tests/test_views.py`
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views.VehicleViewSetAPITest -v 2` -> 11 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: run an authenticated live cashier API/browser smoke that creates a vehicle, attaches it to a selected room, clears it, and confirms vehicle lookup still works by plate, current room context, and rental-session history without exposing edit controls to cashiers.

## 2026-06-18 00:00 AST - Cashier recent activity fetch is server-filtered

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier screen needs recent car activity to stay focused and fast. The backend already supported filtering by event type, and the previous recommendation/log expected the cashier panel to request only car/room events, but the template still fetched all events and filtered them in the browser.

Change made: updated the cashier recent activity loader to pass the selected car/room event types through the `event_type` API query parameter, keeping the existing client-side filter as a defensive guard. Updated the focused template test to lock in the server-filtered request.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_recent_car_activity_panel -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run the authenticated live cashier API/browser smoke that creates a vehicle, attaches it to a selected room, clears it, and confirms the filtered recent activity panel shows attach/clear entries without unrelated maintenance events.

## 2026-06-18 01:00 AST - Cashier vehicle edit controls respect role

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the backend already rejects cashier vehicle edits, but the cashier vehicle lookup UI still rendered edit controls in dynamic search/detail results. This was a small permissions mismatch in the cashier flow that could confuse cashiers and generate avoidable 403 errors.

Change made: updated the cashier vehicle UI so Edit Details controls only render for manager-or-admin users and added direct JS guards that show a readable manager-required message if an edit path is invoked without the role. Added a focused template regression test for the manager-only vehicle edit guard.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_vehicle_edit_controls_require_manager_role -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run the authenticated live cashier API/browser smoke that creates a vehicle, attaches it to a selected room, clears it, and confirms recent activity plus vehicle lookup behave correctly for cashier users without exposing manager-only edit controls.


## 2026-06-18 02:00 AST - Cashier vehicle flow smoke regression

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the previous runs recommended an authenticated live cashier smoke for the car attach/clear flow. The live API smoke passed, so I locked that operational flow into a focused regression test to keep cashier vehicle tracking from drifting.

Change made: added an end-to-end cashier API regression that creates a vehicle, attaches it to a room, clears the room vehicle, searches the vehicle by plate, and confirms attach/clear occupancy events are written.

Live smoke:
- Idempotently ran the configured motel user bootstrap command.
- Authenticated as the cashier through `/api/auth/login/`.
- Loaded `/api/rooms/`, created a unique smoke vehicle, attached it to `room_1`, cleared it, and confirmed vehicle search returned it.

Files touched:
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest.test_cashier_vehicle_smoke_create_attach_clear_and_search -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run a browser-level cashier smoke for the same create/attach/clear/search path and confirm the recent activity panel visibly shows the attach and clear entries for a cashier user.

## 2026-06-18 03:00 AST - Vehicle attach/clear refreshes activity panel

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the previous run locked in the cashier vehicle create/attach/clear API flow and recommended a browser-level smoke. A small UI gap remained: vehicle attach and clear refreshed room cards, but did not immediately refresh the Recent Car Activity panel, so visible attach/clear confirmation could lag until another room poll.

Change made: updated the cashier vehicle attach and clear handlers to refresh Recent Car Activity immediately after reloading rooms. Added a focused template regression test so the browser flow keeps the same immediate activity refresh behavior as sensor readings and manual overrides.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_vehicle_attach_clear_refreshes_recent_activity -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run a real browser cashier smoke for create/attach/clear/search and confirm the Recent Car Activity panel visibly shows the attach and clear entries for a cashier user.

## 2026-06-18 04:00 AST - Cuadre exposes all three motel shifts

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the backend already supports shifts 1, 2, and 3 for Cuadre and shift ledger generation, while the cashier Cuadre dropdown only exposed Turno 1 and Turno 2. That left the 15:00-22:59 cashier shift unable to generate its own Cuadre from the UI.

Change made: updated the cashier Cuadre shift selector to show all three supported motel shift windows and added a focused template regression test for the options.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_cuadre_selector_exposes_all_supported_shifts -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run a real browser cashier smoke for create/attach/clear/search and confirm the Recent Car Activity panel visibly shows the attach and clear entries for a cashier user.

## 2026-06-18 05:00 AST - Empty vehicle create shows panel error

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the current cashier vehicle flow is usable enough for create/attach/clear smoke testing, but an empty `Create & Attach` click only wrote the validation failure to the event log. The cashier should see the correction in the Vehicle Lookup panel where they are working.

Change made: updated the cashier `Create & Attach` validation so an empty vehicle form shows a readable panel error before returning, and added a template regression assertion for that panel message.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run a real browser cashier smoke for create/attach/clear/search and confirm the Recent Car Activity panel visibly shows the attach and clear entries for a cashier user.

## 2026-06-18 06:00 AST - Duplicate plate create surfaces attach path

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: duplicate license plate handling is part of the customer vehicle tracking acceptance criteria. The API already rejected duplicates safely, but the cashier `Create & Attach` flow only showed a generic create failure instead of helping the cashier use the existing vehicle record.

Change made: updated the cashier vehicle create error handling so a duplicate plate automatically searches that plate and prepends a readable message telling the cashier to attach the matching existing vehicle. Added a focused template regression assertion for the duplicate-plate branch.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_formats_vehicle_api_errors -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: run a real browser cashier smoke for create/attach/clear/search, including attempting to create a duplicate plate and confirming the existing vehicle result can be attached without retyping.

## 2026-06-18 07:00 AST - Health check preserves cache keys

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the Priority 0 cashier login, role, vehicle, and core-button flows have been advanced, and the highest remaining bounded action-list item was the health endpoint clearing the entire cache on every probe.

Change made: replaced the healthcheck cache `clear()` call with a dedicated short-lived cache ping key that is set, read, and deleted without touching unrelated runtime cache data. Added a focused regression test proving `/api/health/` leaves an existing cache key intact.

Files touched:
- `apps/core/healthcheck.py`
- `apps/core/tests/test_healthcheck.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.
- Live local health smoke: `GET http://127.0.0.1:8000/api/health/` -> HTTP 200, and a pre-existing cache key remained `preserved` after the probe.

Next recommended action: continue Priority 1 hardening by reviewing the Cuadre workflow for idempotent saved ledgers and cashier-facing print/export behavior, or run the pending browser smoke for the cashier vehicle create/attach/clear path.

## 2026-06-18 11:00 AST - Cashier Cuadre PDF download

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the Cuadre panel already showed totals and auto-saved shift ledgers, but cashiers still lacked a direct export/download path for bookkeeping. The existing PDF route also needed to respect the selected shift.

Change made: allowed cashier access to the Cuadre PDF endpoint, made it honor the selected shift query param, added a cashier dashboard download button that fetches the PDF with the JWT bearer token, and added focused regression tests for the new button and shift-aware PDF path.

Files touched:
- `apps/revenue/views.py`
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `apps/revenue/tests/test_views_extended.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_exposes_cuadre_pdf_download apps.revenue.tests.test_views_extended.CuadreActionTest.test_cuadre_pdf_download_uses_selected_shift -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- Live authenticated smoke: cashier login to `/api/auth/login/` returned 200, and `GET /api/ledgers/cuadre/2026-06-18/?shift=3` returned HTTP 200 `application/pdf` with `%PDF` magic bytes.

Next recommended action: continue Priority 1 Cuadre hardening by reviewing how shift ledger savings should be surfaced back to the cashier UI, or move on to the remaining shift input/state-machine item if there is a specific gap in current smoke coverage.
## 2026-06-18 12:00 AST - Cashier portal shell served without Django session

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: `/cashier/` was still wrapped in `login_required`, so unauthenticated visitors were bounced to the generic Django login page instead of the cashier portal shell that is supposed to host the JWT login form.

Change made: removed the session-only gate from `cashier_view`, passed `request.user` directly into the template context, and updated the template-view regression test so anonymous `/cashier/` now returns 200 and shows the cashier login shell while still supporting the authenticated dashboard path.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_returns_200 -v 2` -> 1 test OK.

Next recommended action: browser-smoke `/cashier/` with the provisioned cashier account to confirm sign-in, dashboard reveal, refresh persistence, and logout all still behave cleanly now that the portal shell is reachable anonymously.

## 2026-06-18 13:00 AST - Cashier logout returns to portal shell

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the cashier auth flow now lands on the portal shell, but logout still needed to keep the browser on  after JWT cleanup instead of handing control to the generic Django logout page.

Change made: updated the cashier logout handler to call the JWT logout endpoint directly, tolerate the endpoint no-content response, clear local tokens, and redirect back to the cashier portal shell after sign-out. Added a focused template regression assertion covering the new logout path.

Files touched:
-
-
-

Verification:
- Found 1 test(s).
Operations to perform:
  Synchronize unmigrated apps: drf_spectacular, messages, rest_framework, staticfiles
  Apply all migrations: admin, auth, contenttypes, guests, occupancy, revenue, rooms, sessions, users
Synchronizing apps without migrations:
  Creating tables...
    Running deferred SQL...
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying contenttypes.0002_remove_content_type_name... OK
  Applying auth.0001_initial... OK
  Applying auth.0002_alter_permission_name_max_length... OK
  Applying auth.0003_alter_user_email_max_length... OK
  Applying auth.0004_alter_user_username_opts... OK
  Applying auth.0005_alter_user_last_login_null... OK
  Applying auth.0006_require_contenttypes_0002... OK
  Applying auth.0007_alter_validators_add_error_messages... OK
  Applying auth.0008_alter_user_username_max_length... OK
  Applying auth.0009_alter_user_last_name_max_length... OK
  Applying auth.0010_alter_group_name_max_length... OK
  Applying auth.0011_update_proxy_permissions... OK
  Applying auth.0012_alter_user_first_name_max_length... OK
  Applying users.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying admin.0002_logentry_remove_auto_add... OK
  Applying admin.0003_logentry_add_action_flag_choices... OK
  Applying guests.0001_initial... OK
  Applying occupancy.0001_initial... OK
  Applying occupancy.0002_alter_occupancyevent_source... OK
  Applying revenue.0001_initial... OK
  Applying rooms.0001_initial... OK
  Applying rooms.0002_room_current_state... OK
  Applying rooms.0003_seed_data... OK
  Applying rooms.0004_dynamic_pricing_rules... OK
  Applying rooms.0005_fix_dynamic_pricing_unique_constraint... OK
  Applying rooms.0006_fix_dynamic_pricing_unique_constraint_v2... OK
  Applying rooms.0007_expand_room_number... OK
  Applying rooms.0008_room_manager_fields... OK
  Applying rooms.0009_seed_room_inventory... OK
  Applying rooms.0010_room_current_vehicle... OK
  Applying rooms.0011_rental_session_vehicle... OK
  Applying sessions.0001_initial... OK
  Applying users.0002_user_unique_email... OK
System check identified no issues (0 silenced). -> 1 test OK.
- System check identified no issues (0 silenced). -> OK.

Next recommended action: browser-smoke  as the provisioned cashier, sign in, click Logout, and confirm the browser returns to the cashier login shell instead of the generic Django logout page.

## 2026-06-18 13:00 AST - Cashier logout returns to portal shell

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the cashier auth flow now lands on the portal shell, but logout still needed to keep the browser on `/cashier/` after JWT cleanup instead of handing control to the generic Django logout page.

Change made: updated the cashier logout handler to call the JWT logout endpoint directly, tolerate the endpoint no-content response, clear local tokens, and redirect back to the cashier portal shell after sign-out. Added a focused template regression assertion covering the new logout path.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` as the provisioned cashier, sign in, click Logout, and confirm the browser returns to the cashier login shell instead of the generic Django logout page.
## 2026-06-18 14:00 AST - Manager room editor loads pricing tiers

Action-list item: Priority 1 - Add Room Edit Page.

Why this item: the room configuration page already existed, but the pricing tier field was still a free-text input. A bounded manager-side improvement was to make that editor use the live pricing-tier list so room setup is less error-prone.

Change made: replaced the room editor pricing-tier text input with a manager-selectable dropdown, populated it from `/api/pricing-tiers/`, and refreshed the selected value when a room is loaded or the editor is cleared. Added a focused template regression check that the room config page includes the tier select and pricing-tier loader.

Files touched:
- `templates/rooms/room_config.html`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.ManagerViewTest.test_room_config_contains_editor_fields -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/manager/rooms/` as a manager account to confirm the pricing-tier dropdown populates from live tiers and that saving a room preserves the selected tier code.

## 2026-06-18 15:00 AST - Room editor surfaces sensor-ID collisions cleanly

Action-list item: Priority 1 - Add Room Edit Page.

Why this item: the room editor already had a pricing-tier dropdown, but it still needed two small reliability fixes to be manager-friendly: duplicate sensor IDs should be blocked before they hit the database, and validation responses should be readable in the room editor activity log. The editor also needs to tolerate 204 responses from delete/save flows.

Change made: added sensor-ID collision validation to `RoomSerializer`, updated the manager room editor helper to format DRF validation errors into readable field messages, and kept `fetchJSON()` safe for 204 no-content responses. Added focused tests for duplicate sensor-ID rejection on create/update, the manager room-config helper strings, and the room API duplicate-sensor validation response.

Files touched:
- `apps/rooms/serializers.py`
- `apps/rooms/tests/test_serializers.py`
- `apps/rooms/tests/test_views.py`
- `templates/rooms/room_config.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_serializers.RoomSerializerTest apps.rooms.tests.test_views.ManagerViewTest.test_room_config_contains_editor_fields apps.rooms.tests.test_views.RoomViewSetAPITest.test_manager_cannot_create_room_with_duplicate_sensor_id -v 2` -> 8 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: browser-smoke `/manager/rooms/` as a manager account and confirm the pricing-tier dropdown still loads, save/delete flows do not choke on no-content responses, and duplicate sensor IDs show a clear validation error.
## 2026-06-18 16:00 AST - Cashier login page now points at real provisioning

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier portal still hinted at a fake/default credential path. A bounded improvement was to remove the implied prefilled username, add a visible provisioning hint, and point operators at the real bootstrap command instead of leaving the login shell to guess.

Change made: updated the cashier login panel to show a provisioning note for `bootstrap_cashier`, changed the username field to a blank cashier-username prompt with autocomplete, and added a regression test that the cashier page no longer pre-fills the demo username or mentions the old demo password text.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prompts_for_bootstrap_cashier -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: smoke the `/cashier/` page with a freshly bootstrapped cashier account and confirm the login succeeds cleanly, then move to the next cashier button that still needs a live backend check.
## 2026-06-18 17:08 AST - Bootstrap commands now converge email addresses too

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier bootstrap path is already the canonical way to provision the portal login, but rerunning it did not fully converge an existing users email address to the supplied value. That left the ops path a little less repeatable than it should be.


Change made: updated bootstrap_cashier and bootstrap_motel_users so reruns now also update the existing user email when a non-empty email is supplied and it differs from the current value. Added regression checks that the cashier bootstrap updates email on rerun and that the multi-role bootstrap converges all three emails while still preserving passwords unless --reset-password is used.

Files touched:
- apps/users/management/commands/bootstrap_cashier.py
- apps/users/management/commands/bootstrap_motel_users.py
- apps/users/tests/test_bootstrap_cashier_command.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2 -> 6 tests OK.

Next recommended action: smoke /cashier/ with a freshly bootstrapped cashier account, then move to the next cashier button or revenue flow that still needs a live backend check.
## 2026-06-18 18:00 AST - Preserve exact cashier login passwords

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier login path was already real, but the frontend still trimmed the password field before posting it. That silently breaks any cashier password that intentionally starts or ends with whitespace.

Change made: updated the cashier login script to send the password exactly as typed, while keeping the username trim in place. Added a regression check that the cashier login template posts the untrimmed password value.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prompts_for_bootstrap_cashier -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: smoke the cashier sign-in flow again, then continue the next remaining cashier button or revenue-path check that still needs a live backend pass.
## 2026-06-18 19:00 AST - Cashier login failures now say what went wrong

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier login path was already provisionable, but failed logins still surfaced a generic message. A clearer failure message makes the real cashier login flow easier to use and aligns the portal with the new bootstrap path.

Change made: changed the API login failure response to return Invalid username or password., updated the cashier login panel to show the same message, and tightened the login API test to assert the exact 401 detail.

Files touched:
- apps/users/views.py
- templates/revenue/cashier.html
- apps/users/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.users.tests.test_views.LoginViewAPITest apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prompts_for_bootstrap_cashier -v 2 -> 4 tests OK.
- .venv/bin/python manage.py check -> OK.

Next recommended action: smoke the cashier sign-in flow with a real provisioned cashier account, then continue to the next cashier button or revenue-path check that still needs a live backend pass.

## 2026-06-18 20:00 AST - Cuadre save state is explicit

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the Cuadre button already computes and auto-saves the selected shift, but repeated saves were invisible to the cashier. Making the save response explicit is a small bounded step toward clearly idempotent Cuadre behavior.

Change made: taught `/api/revenue/generate-shift/` to return whether the shift ledger was created or updated, and had the cashier Cuadre flow log that save state after auto-saving the selected shift. Added a regression test that posts the same date/shift twice and confirms only one ledger row exists while the second response reports an update.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.ShiftLedgerViewSetTest.test_generate_shift_updates_existing_ledger_for_same_shift -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier Cuadre tab for shifts 1, 2, and 3, then click Generate Cuadre twice for the same shift and confirm the UI log shows created/updated while the ledger count stays at one row.
## 2026-06-18 21:00 AST - Cashier revenue defaults now use local dates

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the cashier Cuadre and sales tabs were still deriving fallback dates with UTC-based toISOString() calls, which can hand the desk the wrong working date near midnight in Puerto Rico. A bounded fix was to make the cashier portal use the motel's local date everywhere those defaults are generated.

Change made: switched the cashier view to seed the template with timezone.localdate() and updated the cashier template's date helpers to format local dates directly instead of relying on UTC toISOString() conversions. Added a regression test that patches the cashier view's local date and confirms both the Sales and Cuadre inputs render that local date while the template no longer contains the UTC fallback.

Files touched:
- apps/revenue/views.py
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_uses_local_timezone_dates -v 2 -> 1 test OK; system check reported no issues.

Next recommended action: smoke the cashier Cuadre and Sales tabs at night in Puerto Rico time and confirm the default dates match the local working day, then continue with the next cashier button or revenue-path check.

## 2026-06-18 22:00 AST - Vehicle room/session context now comes from the API

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier can already search and attach vehicles, but the vehicle payload did not return the room/session context needed to quickly see where a car is already attached or in use.

Change made: added a room_context field to the vehicle serializer so API responses now include attached room numbers and active rental session room ids, and prefetched related rooms/rental sessions in the vehicle viewset for efficient lookup. Added focused tests proving the vehicle API returns room and rental context when searched by room or session context.

Files touched:
- apps/guests/serializers.py
- apps/guests/views.py
- apps/guests/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.guests.tests.test_views.VehicleViewSetAPITest -v 2 -> 11 tests OK.
- .venv/bin/python manage.py check -> OK.

Next recommended action: wire the new room/session context into the cashier vehicle lookup panel so the desk can see attachment history without opening the raw API.

## 2026-06-18 23:00 AST - Healthcheck cache ping always cleans up

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the health endpoint already stopped clearing the whole cache, and this pass tightened it so the dedicated ping key is removed in a finally block even if the cache probe misbehaves.

Change made: wrapped the cache ping in a nested try/finally so /api/health/ always deletes healthcheck:cache-ping after probing cache connectivity.

Files touched:
- apps/core/healthcheck.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2 -> 1 test OK.
- Django system check passed as part of the test run.

Next recommended action: continue with the next Priority 1 cashier workflow item, ideally wiring sensor input through the occupancy state machine or finishing the Cuadre/revenue usability pass.

## 2026-06-19 00:00 AST - Cashier login now points at the repeatable bootstrap path

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier portal already supports JWT/session bootstrap, but the login panel still nudged operators toward the narrower single-role provisioning path instead of the repeatable multi-role bootstrap command that is already available.

Change made: updated the cashier login note to point at `python manage.py bootstrap_motel_users` so the panel now directs operators to the idempotent provisioning flow that creates cashier, manager, and admin accounts. Aligned the cashier template regression test to assert the new copy.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prompts_for_bootstrap_motel_users -v 2 -> 1 test OK.
- Django system check passed as part of the test run.

Next recommended action: smoke `/cashier/` with a bootstrapped cashier account in-browser and confirm the JWT session still reveals the dashboard without any manual reload.

## 2026-06-19 01:00 AST - Cashier vehicle lookup shows room/session context

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle API already returns attached room numbers and active rental session room ids, and the next useful step was to surface that context in the cashier lookup panel so operators can see where a vehicle is already attached without opening the raw API.

Change made: added a small vehicle context summary helper to the cashier template and rendered attached rooms plus active rental-session room ids in both the selected-vehicle details panel and vehicle search results. Added a focused template regression test proving the cashier page includes the new vehicle context helpers and room/session context strings.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_vehicle_room_context -v 2 -> 1 test OK.
- .venv/bin/python manage.py check -> OK.

Next recommended action: browser-smoke the cashier vehicle lookup panel with a bootstrapped cashier account, search an attached vehicle, and confirm the room/session context is visible in the results and selected-vehicle panel.
## 2026-06-19 02:00 AST - Vehicle lookup shows room numbers for active rentals

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the vehicle context panel already showed attached rooms and active rental sessions, but active rentals still surfaced raw room ids instead of the human room number the cashier scans first.

Change made: updated the vehicle serializer to resolve room numbers for active rental sessions, changed the cashier vehicle context helper to display the room number when available, and added a focused regression test covering the rental-session room-number payload.

Files touched:
- `apps/guests/serializers.py`
- `apps/guests/tests/test_views.py`
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views.VehicleViewSetAPITest apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_vehicle_room_context apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2` -> 13 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: browser-smoke the cashier vehicle lookup panel with a bootstrapped cashier account and confirm attached-room and rental-session context reads naturally, including room-number display for active rentals.

## 2026-06-19 03:00 AST - Cuadre shows ledger save status inline

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the Cuadre backend already saves ledgers idempotently, but the cashier UI only logged the created/updated state in the activity feed. Showing that save result inline makes the shift workflow clearer at the point of use.

Change made: added an inline Cuadre save-status banner to the cashier tab so the desk sees `Saving shift ledger...` immediately and then gets a visible `Ledger saved: created/updated...` or failure message after the auto-save call completes.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_cuadre_save_status_banner -v 2` -> 1 test OK.
- Django system check passed as part of the test run.

Next recommended action: browser-smoke the cashier Cuadre tab and confirm the save banner flips from saving to created/updated when Generate Cuadre runs for the selected shift.
## 2026-06-19 04:00 AST - Cashier login errors now distinguish auth failures from other issues

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the cashier login handler was collapsing every failure into the same generic message, which hid validation and server-side problems from the desk.

Change made: updated `doLogin()` so 401 auth failures still show a clear invalid-credentials message, while non-401 login problems now surface as `Login failed: ...` with the API detail preserved. Added a template regression assertion for the new login-error branch.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prompts_for_bootstrap_motel_users -v 2` -> 1 test OK; Django system check passed.

Next recommended action: browser-smoke the cashier login panel with a bad password and confirm the on-screen error is specific enough for desk use, then continue tightening the cashier button flow.

## 2026-06-19 05:00 AST - Cuadre save banner clarifies repeated updates

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the Cuadre flow already auto-saves the selected shift ledger, but the cashier-facing copy should make it obvious that re-running the same date and shift updates the existing ledger instead of creating a duplicate.

Change made: updated the Cuadre panel copy to say it is saving or updating the shift ledger, and added a short note that re-running the same date and shift updates the existing ledger instead of creating a duplicate.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_cuadre_save_status_banner -v 2` -> 1 test OK.

Next recommended action: browser-smoke the cashier Cuadre tab with the logged-in cashier account and confirm the banner reads clearly on first save and on a repeat save for the same shift.

## 2026-06-19 06:00 AST - Healthcheck now pings cache without touching live keys

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the probe must stay harmless to operational cache data, and this is a small safe fix with a direct reliability payoff.

Change made: updated `/api/health/` to use a unique sentinel cache key for the ping instead of a shared key, and tightened the regression test to prove an existing cache entry survives the probe while the temporary sentinel is cleaned up.

Files touched:
- `apps/core/healthcheck.py`
- `apps/core/tests/test_healthcheck.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2` -> 1 test OK; Django system check passed.

Next recommended action: inspect whether the cashier auth flow still needs a one-pass smoke check from the live browser session, then move on to the next button flow that is still blocked.

## 2026-06-19 07:00 AST - Room cards flag missing vehicle attachment on occupied rooms

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier room cards already show the current room state, but an occupied or review-state room with no attached vehicle was still visually ambiguous at a glance.

Change made: added a small room-card helper so occupied/review rooms now explicitly say `Vehicle: Not attached` when there is no attached vehicle, while rooms with a vehicle keep showing the vehicle label inline. This keeps the car-presence scan faster without changing backend behavior.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_flags_present_rooms_without_vehicle_attachment -v 2` -> OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier room grid and confirm occupied rooms with no vehicle now stand out immediately, then continue refining the vehicle-tracking workflow.

## 2026-06-19 08:00 AST - Cashier logout now stays on the page unless login-only mode is active

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the cashier logout path was still forcing an unconditional page reload, which added friction without improving the desk workflow.

Change made: guarded the logout redirect behind `LOGIN_ONLY`, so the main cashier portal now clears JWT/session state and stays on the login panel in place. A login-only variant can still redirect if that mode is ever used again. Added a template regression assertion that the redirect is now explicitly guarded.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state -v 2` -> 1 test OK; Django system check passed.

Next recommended action: browser-smoke logout on the live cashier page to confirm the login panel stays visible without a reload, then continue with the next cashier button or vehicle-flow polish item.
## 2026-06-19 09:00 AST - Cashier login now warns on empty credentials

Action-list item: Priority 0 - Make Cashier Login Real / Fix Cashier Frontend Auth Flow.

Why this item: the cashier login button could fail silently when either field was blank, which made the first sign-in attempt confusing at the desk.

Change made: added explicit cashier-facing feedback when Sign In is pressed without both a username and password. The login error banner now tells the user to enter both fields instead of doing nothing.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prompts_for_bootstrap_motel_users -v 2` -> OK; Django system check passed.

Next recommended action: browser-smoke the cashier login panel with blank inputs and then with a valid cashier account, then move to the next cashier button flow that still needs polish.

## 2026-06-19 10:00 AST - Cashier room-action buttons now validate a selected room

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the cashiers Send Reading and Quick Override buttons could still fall through with a blank room selection, which would produce a confusing API error instead of a cashier-facing prompt.

## 2026-06-19 10:00 AST - Cashier room-action buttons now validate a selected room

Action-list item: Priority 0 - Make Core Cashier Buttons Work.

Why this item: the cashier's Send Reading and Quick Override buttons could still fall through with a blank room selection, which would produce a confusing API error instead of a cashier-facing prompt.

Change made: added a small `resolveSelectedRoom()` helper in `templates/revenue/cashier.html` so Simulate Reading and Quick Override now stop early and log `Select a room before ...` when no room is selected. Added a template regression check covering the new guard.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_room_actions_validate_selected_room -v 2` -> OK; Django system check passed.

Next recommended action: smoke the cashier buttons in the browser with the selected-room field blank, then continue with the next cashier flow that still needs polish.

## 2026-06-19 11:00 AST - Sensor transitions now open and close occupancy sessions

Action-list item: Priority 1 - Wire Sensor Input Through Occupancy State Machine.

Why this item: the sensor workflow was already updating room state and occupancy events, but it still was not driving the revenue occupancy session lifecycle, so the cashier could not reliably see a car-present session start/end from the same path.

Change made: taught `OccupancyService.process_sensor_reading()` and `manual_override()` to sync the revenue occupancy session table when a room transitions into `occupied` or back to `vacant`. Added a small helper to create a session on arrival and close the active session on departure, and tightened `RevenueEngine.create_occupancy_session()` to use a timezone-aware timestamp. Added a focused regression test that proves a sensor reading can open and close a session.

Files touched:
- `apps/occupancy/services.py`
- `apps/occupancy/tests/test_services.py`
- `apps/revenue/services.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_services.OccupancyServiceTest.test_sensor_state_changes_create_and_close_revenue_sessions -v 2` -> OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: surface the active occupancy-session start time on the cashier room cards so the desk can see not just car present/not present, but how long the current stay has been active.

## 2026-06-19 12:00 AST - Cashier room cards show active stay start times

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the room cards already showed car-present status and the latest sensor reading, but the cashier still could not see when an active stay started without drilling into other panels.

Change made: added an `active_occupancy_session` field to the room serializer and taught the cashier room cards to render `Stay active since ...` for occupied rooms with an active session. Added focused regression checks for the serializer payload and the cashier template copy.

Files touched:
- `apps/rooms/serializers.py`
- `apps/rooms/tests/test_serializers.py`
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_serializers.RoomSerializerTest.test_room_serializer_includes_active_occupancy_session apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_active_occupancy_session_start_time -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier room grid and confirm occupied rooms now show the stay start time alongside the car-presence label and last reading.

## 2026-06-19 13:00 AST - Cashier active stay line is visually prominent

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier room cards already showed car presence and the current stay start time, but the start timestamp was still easy to miss in a busy grid view.

Change made: added a styled `Active stay` line to occupied room cards so the current session start stands out more clearly while preserving the relative age detail. Updated the cashier template regression test to assert the new room-session markup.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_active_occupancy_session_start_time -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier room grid and confirm occupied rooms still scan quickly with the more prominent active-stay line alongside car presence and last reading.
## 2026-06-19 14:00 AST - Active stay line shows elapsed duration

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier room cards already showed when a stay started, but the desk still had to estimate how long the car had been in the room. Showing the elapsed active-stay duration makes the grid faster to scan during busy shifts.

Change made: added a small `stayDuration()` helper in the cashier template and updated the active occupancy-session line to show both the start time and elapsed active duration. Added a focused template regression assertion for the new helper call.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_active_occupancy_session_start_time -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier room grid and confirm occupied rooms still scan quickly with the more prominent active-stay line alongside car presence and last reading.

## 2026-06-19 15:00 AST - Cashier room cards show latest occupancy confidence

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier grid already shows car-present state and active stay timing, but the desk still needs one glance at how confident the latest occupancy decision is.

Change made: added the latest occupancy event to the room serializer and taught the cashier room cards to show a decision-confidence line next to the existing car-presence and stay-duration details.

Files touched:
- `apps/rooms/serializers.py`
- `apps/rooms/tests/test_serializers.py`
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_serializers.RoomSerializerTest.test_room_serializer_includes_latest_occupancy_event apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_latest_occupancy_event_confidence -v 2` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier room grid and confirm occupied and recently transitioned rooms now show a readable decision-confidence line alongside car presence and active stay.

## 2026-06-19 16:00 AST - Sensor-offline room cards now avoid stale presence text

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier grid already showed sensor-offline rooms, but the secondary presence line could still read like a live present/absent reading even when the sensor was unhealthy.

Change made: updated the cashier room-card helper so sensor-offline rooms now show `Sensor data stale` instead of a normal present/absent reading line, which keeps the offline state unambiguous during a quick scan. Added a focused template regression check for the new stale-data copy.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_uses_car_presence_labels -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier room grid and confirm sensor-offline cards read clearly alongside the car-present/no-car/needs-review states.
## 2026-06-19 17:00 AST - Manager user review panel

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: cashier auth and room control are usable, but the manager UI still lacked a quick way to review which accounts exist and what roles they have without opening Django Admin.

Change made: added a Users tab to the manager page that loads `/api/users/` and shows username, role, name, status, staff flag, and last login in a read-only table. Added a refresh button and a direct link to Django Admin for account creation/editing.

Files touched:
- `templates/rooms/manager.html`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.ManagerViewTest.test_contains_user_review_panel -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: add a dedicated in-app user create/edit workflow for admins if the Django Admin shortcut is still too indirect for operations.
## 2026-06-19 18:00 AST - Safe bootstrap reruns preserve existing emails

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier and multi-user bootstrap commands already created the operational login accounts, but rerunning them was still too eager about overwriting an existing account email. A safe provisioning path should be idempotent without clobbering operator-managed contact details.

Change made: updated `bootstrap_cashier` and `bootstrap_motel_users` so reruns now preserve an existing user email unless an explicit email override is supplied. The commands still enforce the cashier/manager/admin roles, activate accounts, and only reset passwords when requested. Added regression checks that reruns keep existing emails by default, explicit email overrides still work, and the bootstrapped accounts can still obtain JWT tokens.

Files touched:
- `apps/users/management/commands/bootstrap_cashier.py`
- `apps/users/management/commands/bootstrap_motel_users.py`
- `apps/users/tests/test_bootstrap_cashier_command.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2` -> 6 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: build the in-app admin user create/edit workflow so account management no longer has to rely on Django Admin for routine operations.

## 2026-06-19 19:00 AST - Health probe no longer clears cache

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the health endpoint should stay harmless, and the probe can still verify Redis without wiping operational cache keys.

Change made: updated  to use a dedicated ephemeral cache key for the connectivity check and remove it after the read/write ping. Added a regression test that seeds a normal cache entry, calls the health endpoint, and confirms the seeded entry survives the probe.

Files touched:
-
-
-

Verification:
- Found 1 test(s).
Operations to perform:
  Synchronize unmigrated apps: drf_spectacular, messages, rest_framework, staticfiles
  Apply all migrations: admin, auth, contenttypes, guests, maintenance, occupancy, revenue, rooms, sessions, users, workorders
Synchronizing apps without migrations:
  Creating tables...
    Running deferred SQL...
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying contenttypes.0002_remove_content_type_name... OK
  Applying auth.0001_initial... OK
  Applying auth.0002_alter_permission_name_max_length... OK
  Applying auth.0003_alter_user_email_max_length... OK
  Applying auth.0004_alter_user_username_opts... OK
  Applying auth.0005_alter_user_last_login_null... OK
  Applying auth.0006_require_contenttypes_0002... OK
  Applying auth.0007_alter_validators_add_error_messages... OK
  Applying auth.0008_alter_user_username_max_length... OK
  Applying auth.0009_alter_user_last_name_max_length... OK
  Applying auth.0010_alter_group_name_max_length... OK
  Applying auth.0011_update_proxy_permissions... OK
  Applying auth.0012_alter_user_first_name_max_length... OK
  Applying users.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying admin.0002_logentry_remove_auto_add... OK
  Applying admin.0003_logentry_add_action_flag_choices... OK
  Applying guests.0001_initial... OK
  Applying rooms.0001_initial... OK
  Applying rooms.0002_room_current_state... OK
  Applying rooms.0003_seed_data... OK
  Applying rooms.0004_dynamic_pricing_rules... OK
  Applying rooms.0005_fix_dynamic_pricing_unique_constraint... OK
  Applying rooms.0006_fix_dynamic_pricing_unique_constraint_v2... OK
  Applying rooms.0007_expand_room_number... OK
  Applying rooms.0008_room_manager_fields... OK
  Applying rooms.0009_seed_room_inventory... OK
  Applying rooms.0010_room_current_vehicle... OK
  Applying rooms.0011_rental_session_vehicle... OK
  Applying rooms.0012_roomgroup... OK
  Applying workorders.0001_initial... OK
  Applying maintenance.0001_initial... OK
  Applying occupancy.0001_initial... OK
  Applying occupancy.0002_alter_occupancyevent_source... OK
  Applying revenue.0001_initial... OK
  Applying sessions.0001_initial... OK
  Applying users.0002_user_unique_email... OK
  Applying workorders.0002_add_planned_fields... OK
System check identified no issues (0 silenced). -> 1 test OK.

Next recommended action: add a second healthcheck test for the unhealthy-path response when cache or database connectivity fails.

## 2026-06-19 19:00 AST - Health probe no longer clears cache

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the health endpoint should stay harmless, and the probe can still verify Redis without wiping operational cache keys.

Change made: updated /api/health/ to use a dedicated ephemeral cache key for the connectivity check and remove it after the read/write ping. Added a regression test that seeds a normal cache entry, calls the health endpoint, and confirms the seeded entry survives the probe.

Files touched:
- apps/core/healthcheck.py
- apps/core/tests/test_healthcheck.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2 -> 1 test OK.

Next recommended action: add a second healthcheck test for the unhealthy-path response when cache or database connectivity fails.


## 2026-06-19 20:00 AST - Healthcheck failure-path coverage

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the probe already uses an ephemeral cache key, and a failure-path test makes sure the endpoint stays predictable when the cache ping itself fails.

Change made: added a regression test that patches the healthcheck cache ping to raise, then confirms `/api/health/` returns 503 with an unhealthy cache status instead of crashing.

Files touched:
- apps/core/tests/test_healthcheck.py
- docs/RANGO_LOG.md

Verification:
- `.venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2` -> 2 tests OK.

Next recommended action: move back to the remaining Priority 0 cashier work, starting with whichever room/vehicle workflow is currently the smallest safe gap.
## 2026-06-19 21:00 AST - Admin user management now lives in the manager app

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the manager page already had a read-only users review panel, and the next bounded gap was giving admins an in-app create/edit workflow so routine account management does not have to bounce out to Django Admin.

Change made: added an admin-only user create/edit dialog to the manager Users tab, including create/update calls against the existing user API, role/active/staff fields, and a per-row Edit button for admin users. Managers keep the read-only roster view and still see the Django Admin shortcut.

Files touched:
- `templates/rooms/manager.html`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.ManagerViewTest -v 2` -> 10 tests OK.
- `.venv/bin/python manage.py check` -> OK.
- `systemctl restart django-dev.service && systemctl is-active django-dev.service` -> active.

Next recommended action: browser-smoke the manager Users tab as an admin account, create or edit a test user, and confirm managers still only see the read-only roster.

## 2026-06-19 22:00 AST - Healthcheck now pings cache without clearing it

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the health endpoint is used by probes and should not mutate unrelated runtime state. The existing implementation had already started to shift away from cache.clear(), and this run finished that bounded fix.

Change made: updated /api/health/ to use a dedicated random cache key for a short-lived set/get/delete ping instead of clearing the default cache. Added a regression test proving a normal cache entry survives the health check and a failure-path test for cache ping errors.

Files touched:
- apps/core/healthcheck.py
- apps/core/tests/test_healthcheck.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2 -> 2 tests OK.
- .venv/bin/python manage.py check -> OK.

Next recommended action: continue with the next Priority 1 gap in the action list, starting with sensor-input/state-machine flow or the smallest remaining cashier-facing revenue edge that is still unblocked.

## 2026-06-19 23:00 AST - Cashier login helper now points to the real bootstrap paths

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier portal already has working auth, but the login screen still needed a clearer, reality-based bootstrap hint for operators provisioning the desk account.

Change made: wired the cashier login input to the existing `default_username` context so the form shows `cashier` by default, and updated the helper copy to point at `bootstrap_cashier` for the desk account plus `bootstrap_motel_users` for the full role set. Updated the cashier template regression test to match the new help text and default username.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: continue with the next Priority 1 gap that is still visibly incomplete, starting with sensor-input/state-machine wiring or the smallest cashier revenue/ledger edge still blocking the core workflow.
## 2026-06-20 00:00 AST - Cashier bootstrap now strips elevated flags on rerun

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier bootstrap command is the safe provisioning path for the desk account, and reruns should not leave staff or superuser privileges behind on a cashier identity.

Change made: updated bootstrap_cashier so reruns clear accidental is_staff and is_superuser flags while keeping the account active, cashier-typed, and idempotent. Added a regression test covering a preexisting cashier with elevated flags.

Files touched:
- apps/users/management/commands/bootstrap_cashier.py
- apps/users/tests/test_bootstrap_cashier_command.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2 -> 7 tests OK.

Next recommended action: browser-smoke the cashier portal with a provisioned cashier account, then move to the remaining cashier frontend auth/button-flow gap if anything still blocks the room grid.

## 2026-06-20 01:00 AST - Centralized occupancy thresholds

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the occupancy state machine still carried the car-present thresholds in more than one place, which made the cashier-facing bucket logic harder to reason about and easier to drift.

Change made: introduced shared occupancy threshold defaults in `apps/occupancy/services.py`, switched the state machine and per-room machine factory to use them, and added a regression test proving Django settings still override the defaults for a room machine.

Files touched:
- `apps/occupancy/services.py`
- `apps/occupancy/tests/test_services.py`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_services -v 2` -> 21 tests OK.

Next recommended action: keep the car-presence workflow moving by browser-smoke testing the cashier room grid, then tackle the next small cashiers-only edge if one still blocks room scanning.


## 2026-06-20 02:00 AST - Cuadre ledger save now upserts

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the cashier revenue view already updates existing ledgers for the same date and shift, but the lower-level revenue helper still used a plain create path that could trip the unique shift constraint if it were called directly.

Change made: updated `apps/revenue/services.py` so `save_shift_ledger()` uses `update_or_create()` for `(date, shift_number)` and added a regression test proving repeated saves update the same row instead of creating a duplicate.

Files touched:
- `apps/revenue/services.py`
- `apps/revenue/tests/test_services.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_services.RevenueEngineSaveShiftLedgerTest -v 2` -> 1 test OK.

Next recommended action: keep pushing on the cashier-facing workflow by browser-smoke testing the Cuadre tab, then move to the next remaining cashiers-only edge that still blocks room-to-revenue bookkeeping.

## 2026-06-20 03:00 AST - Cashier login failure now points to bootstrap path

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier bootstrap path exists, but the login screen still only said the credentials were invalid when a fresh server had not been provisioned yet.

Change made: updated the cashier login failure path so HTTP 401 responses now tell the desk to run `python manage.py bootstrap_cashier` on a fresh server, while keeping the existing generic failure text for non-401 cases.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2` -> 1 test OK.

Next recommended action: browser-smoke the cashier login screen and then continue the remaining cashier auth/role polish if anything still blocks sign-in.
## 2026-06-20 04:00 AST - Cashier manager tabs render hidden by default

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the cashier portal already enforces role checks in JS, but the manager-only tabs and reports panel were still rendered visible until the browser finished applying visibility rules.

Change made: added `role-restricted` to the manager-only Pricing Tiers and Ledger History tabs plus the Reports panel so cashier sessions keep privileged controls hidden from first paint, while preserving the existing JS role checks for managers and admins. Extended the cashier template regression test to assert the hidden role markers are present.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_marks_manager_only_controls -v 2` -> 1 test OK.

Next recommended action: browser-smoke the cashier portal with a cashier login to confirm manager-only controls stay out of view, then continue the next smallest remaining cashier workflow gap.



## 2026-06-20 05:00 AST - Cashier login now has an actual account

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier portal still depended on the advertised `cashier / change_me` credentials, and the live server needed that account provisioned before the cashier flow could be exercised end to end.

Change made: reran `bootstrap_cashier` with `--reset-password` so the live cashier account matches the advertised login and can obtain JWT tokens from `/api/auth/login/`.

Files touched:
- `docs/RANGO_LOG.md`

Verification:
- `POST /api/auth/login/` with `cashier / change_me` -> HTTP 200.
- Payload included `access`, `refresh`, and `user.role == cashier`.

Next recommended action: browser-smoke `/cashier/` with the cashier account to confirm the page signs in cleanly, then move to the next still-incomplete cashier workflow item.
## 2026-06-20 06:00 AST - Bootstrap commands now require explicit passwords

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier provisioning commands still fell back to `change_me` when no password was supplied, which kept the bootstrap path from being explicit and safe.

Change made: removed the implicit password default from `bootstrap_cashier` and `bootstrap_motel_users`, so the cashier/manager/admin passwords must now come from CLI flags or `MOTEL_*` environment variables. Added a regression test that proves the cashier bootstrap command fails cleanly when no password is provided.

Files touched:
- `apps/users/management/commands/bootstrap_cashier.py`
- `apps/users/management/commands/bootstrap_motel_users.py`
- `apps/users/tests/test_bootstrap_cashier_command.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2` -> 8 tests OK.
- Django system check passed in the same run.

Next recommended action: browser-smoke `/cashier/` with a provisioned cashier account to confirm the live login flow still works, then keep chipping away at the remaining cashier workflow gaps.
## 2026-06-20 07:00 AST - Sensor health now respects stale readings

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier cards already showed `Sensor Offline`, but the serializer treated any historical sensor reading as healthy, so a room could stay green long after the sensor stopped reporting. The next safe bounded improvement was to make the offline state follow the existing `OFFLINE_THRESHOLD_SECONDS` setting.

Change made: updated `RoomSerializer.sensor_healthy` to evaluate the latest reading timestamp against `OFFLINE_THRESHOLD_SECONDS` and return offline when the room has no recent reading. Added a regression test proving a stale reading now flips the room list entry to `sensor_healthy = false`.

Files touched:
- `apps/rooms/serializers.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest -v 2` -> 21 tests OK.

Next recommended action: keep the cashier visibility work honest by checking whether any other room status fields still ignore freshness or age, then move to the next remaining cashier-facing gap.
## 2026-06-20 08:00 AST - Room cards now label the last sensor time

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier room cards already showed sensor freshness, but the timestamp line was unlabeled. The next safe bounded improvement was to make that freshness signal explicit so a cashier can scan the card and immediately know it is the last sensor time.

Change made: updated the cashier room card markup to render `Last sensor: ...` instead of a bare age string, making the freshness line self-explanatory without changing any backend behavior.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_uses_car_presence_labels -v 2` -> 1 test OK.
- Django system check reported no issues during the test run.

Next recommended action: keep refining the cashier's at-a-glance room state, either by surfacing the sensor age more visually or by tightening the vehicle/context details on the room cards.

## 2026-06-20 09:00 AST - Room cards now show sensor freshness as a pill

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the room cards already label the last sensor time, but the freshness signal was still plain text. A small visual cue makes stale or fresh readings easier for the cashier to scan at a glance.

Change made: updated the cashier room cards to render the last sensor time as a colored freshness pill with fresh/warm/stale/unknown states, while keeping the existing car-presence labels and room context intact.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_marks_sensor_age_badge -v 2` -> 1 test OK.

Next recommended action: browser-smoke `/cashier/` with the cashier account and confirm the new freshness pill makes stale readings easier to spot, then keep refining the room card context if anything still feels too buried.

## 2026-06-20 10:00 AST - User list is now stable for manager review

Action-list item: Priority 0 - Add Multiple Users And Permissions.

Why this item: the user-management API was already enforcing cashier vs manager/admin access, but the manager review list was still returned from an unordered queryset, which produced a pagination warning and made the list order unstable.

Change made: sorted the `/api/users/` queryset by username so manager/admin review gets a stable order. Tightened the user-list test to assert the returned usernames are sorted, which also removed the pagination warning during the test run.

Files touched:
- `apps/users/views.py`
- `apps/users/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_views -v 2` -> 24 tests OK.
- Django system check reported no issues during the run.

Next recommended action: keep advancing the cashier-facing workflow, with the next best bounded pass being one of the remaining room-control button flows or the vehicle attachment experience.
## 2026-06-20 11:00 AST - Room editor now rejects duplicate room numbers

Action-list item: Priority 1 - Add Room Edit Page.

Why this item: the room editor already existed, but it still allowed duplicate room numbers through the serializer, which made the manager edit page ambiguous even when the UI itself looked fine.

Change made: added explicit room-number duplicate validation to RoomSerializer so the manager room editor now returns a clear validation error before save, and added serializer tests covering duplicate room IDs, duplicate room numbers, and duplicate sensor IDs.

Files touched:
- apps/rooms/serializers.py
- apps/rooms/tests/test_serializers.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.rooms.tests.test_serializers -v 2 -> 17 tests OK.

Next recommended action: surface the serializer validation message more prominently in the room editor UI, then smoke-test duplicate room-number and sensor-ID edits from /manager/rooms/.
## 2026-06-20 12:00 AST - Room editor now surfaces validation errors clearly

Action-list item: Priority 1 - Add Room Edit Page.

Why this item: the room editor already rejected duplicate room numbers and sensor IDs, but the save failure only went to the activity log. A dedicated banner makes the validation failure obvious while the manager is editing.

Change made: added a prominent `roomEditorError` banner to the room configuration page, wired save/load/clear flows to populate it, and kept the activity log entry for context.

Files touched:
- `templates/rooms/room_config.html`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.ManagerViewTest.test_room_config_contains_editor_fields -v 2` -> 1 test OK.
- Django system check reported no issues during the test run.

Next recommended action: smoke-test the room editor with a duplicate room number or sensor ID from `/manager/rooms/`, then move on to the next cashier-facing gap.
## 2026-06-20 13:00 AST - Cashier login guidance now shows the exact rerunnable bootstrap command

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier portal already worked, but the bootstrap hint was still too vague for a fresh server. The login page now tells operators the exact rerunnable provisioning command and mentions the password reset path.

Change made: updated the cashier login note and the 401 login failure message to point at python manage.py bootstrap_cashier --password <new-password> and --reset-password, with bootstrap_motel_users as the multi-role bootstrap path. Added a template test assertion so the reset hint stays visible.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username --keepdb -> 1 test OK.
- Django system check reported no issues during the test run.

Next recommended action: smoke-test the live cashier page once more, then keep moving through the remaining cashier button flows or the vehicle-attachment workflow.

## 2026-06-20 14:00 AST - Vehicle search now matches normalized plate input

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the vehicle records and room context already exist, but cashier lookup still needs to work smoothly when the plate is entered with or without spaces or punctuation. This is a small cashier-facing usability win that keeps plate search aligned with the normalized duplicate-check logic.

Change made: updated the vehicle API search path so cashier lookups also match `license_plate_normalized` using a normalized search term, then added a regression test proving `abc-123` finds a saved `ABC 123` record.

Files touched:
- `apps/guests/views.py`
- `apps/guests/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.guests.tests.test_views.VehicleViewSetAPITest -v 2 --keepdb` -> 12 tests OK.
- Django system check reported no issues during the test run.

Next recommended action: smoke-test vehicle lookup from the cashier UI with both spaced and unspaced plate input, then keep tightening the vehicle attachment workflow and room-context display.

## 2026-06-20 15:00 AST - Vehicle attach flow now re-centers on the room

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle lookup already supports normalized plate search, but after attaching or clearing a vehicle the lookup pane could still be left showing the old search terms. Re-centering the lookup on the selected room keeps the room hint and search results aligned with the room-first workflow.

Change made: added a small frontend helper that refreshes the vehicle lookup by room, then called it after attach/clear actions and from the selected-room search path so the results pane now follows the room context. Removed the old post-attach plate rewrite so the cashier stays on the room-focused view after confirming the vehicle.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2 --keepdb` -> 1 test OK.

Next recommended action: smoke-test the live cashier vehicle lookup with a room attach and clear.

## 2026-06-20 16:00 AST - Cashier login clears password on reuse

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the cashier sign-in flow is already token-backed and dashboard-capable, but the password field could linger after a successful sign-in or when the login panel is shown again. Clearing it is a small, safe auth UX/privacy improvement that keeps the cashier login panel tidy.

Change made: updated the cashier template so the password field is cleared whenever the login panel is shown and after a successful sign-in. Added a regression assertion in the cashier template test to lock in that behavior.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test --keepdb apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state` -> 1 test OK.
- Django system check reported no issues during the test run.

Next recommended action: browser-smoke the cashier sign-in/sign-out panel to confirm the password clears visually, then keep advancing the vehicle tracking workflow.

## 2026-06-20 17:09 AST - Generate shift now rejects unsupported shift numbers

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the cashier shift-save endpoint already handled bad dates and non-integer shifts, but it still accepted out-of-range shift numbers. Matching the read-only cuadre validation keeps the cashier workflow consistent and prevents accidental saves for invalid shifts.

Change made: added a  guard to  and a regression test that rejects .

Files touched:
-
-
-

Verification:
-  -> 5 tests OK.
- Django system check reported no issues during the test run.

Next recommended action: smoke-test the cashier cuadre flow in the browser, then keep tightening the shift and vehicle workflows.

## 2026-06-20 17:09 AST - Generate shift now rejects unsupported shift numbers

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the cashier shift-save endpoint already handled bad dates and non-integer shifts, but it still accepted out-of-range shift numbers. Matching the read-only cuadre validation keeps the cashier workflow consistent and prevents accidental saves for invalid shifts.

Change made: added a `1, 2, 3` guard to `POST /api/ledgers/generate_shift/` and a regression test that rejects `shift=4`.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views_extended.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views_extended.GenerateShiftActionTest -v 2 --keepdb` -> 5 tests OK.
- Django system check reported no issues during the test run.

Next recommended action: smoke-test the cashier cuadre flow in the browser, then keep tightening the shift and vehicle workflows.
## 2026-06-20 18:15 AST - Cashier recent activity shows room numbers

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier recent activity panel already tracked car attach/clear events, but it still showed raw room IDs. Surfacing room numbers makes the feed faster to scan during live desk work.

Change made: added `room_number` to `OccupancyEventSerializer` and updated the cashier recent-activity renderer to show `Room <number>` when available, falling back to the internal room id when needed.

Files touched:
- `apps/occupancy/serializers.py`
- `apps/occupancy/tests/test_serializers.py`
- `apps/revenue/tests/test_views.py`
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_serializers.OccupancyEventSerializerTest apps.revenue.tests.test_views.TemplateViewTest.test_cashier_vehicle_attach_clear_refreshes_recent_activity -v 2 --keepdb` -> 2 tests OK.
- Django system check reported no issues during the test run.

Next recommended action: live-smoke the cashier room attach/clear flow so the recent activity panel can be confirmed with real room numbers, then keep advancing the vehicle tracking workflow.

## 2026-06-20 19:00 AST - Vehicle search autofills public room numbers

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle lookup already supports attach/clear flows, but selecting a room still left the vehicle search box showing the internal room id. Autofilling the public room number is a small usability win that makes the selected-room vehicle lookup easier to read and verify at the desk.

Change made: updated the cashier room-selection handler so the vehicle search field now autofills the room number when available, falling back to the room id only if needed. Added a regression assertion to the cashier template test to lock in the new autofill behavior.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls -v 2 --keepdb` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: live-smoke the cashier room selection plus `Find Selected Room Vehicle` flow to confirm the autofilled room number makes the lookup easier without changing the attach/clear behavior.
## 2026-06-20 20:00 AST - Cashier login now clears the password after any attempt

Action-list item: Priority 0 - Make Cashier Login Real / Fix Cashier Frontend Auth Flow.

Why this item: the cashier login path is already wired up, but leaving the password in the field after a failed attempt makes repeated sign-ins clunkier and leaks the typed password on-screen longer than needed.

Change made: added a small `clearLoginPassword()` helper in the cashier template and now clear the password field after successful login, failed login, and login exceptions. Updated the cashier view regression tests to cover the new helper and keep the bootstrap/login guidance intact.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state -v 2 --keepdb` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the cashier sign-in/sign-out panel to confirm the password clears visually, then keep advancing the vehicle tracking workflow.

## 2026-06-20 21:00 AST - Cashier login username now follows the bootstrap env

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier login page was still hardcoding the prefilled username, even though the bootstrap command already supports `MOTEL_CASHIER_USERNAME`. Using the same env on the page keeps the rendered hint aligned with the actual provisioned account.

Change made: updated the cashier portal view to populate `default_username` from `MOTEL_CASHIER_USERNAME` with a safe `cashier` fallback, and added a regression test that proves the login page preloads a custom env username.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prefills_username_from_env apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2 --keepdb` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: finish one more cashier-first login polish item, ideally the final login/auth flow edge case that still shows up in browser smoke testing.

## 2026-06-20 22:00 AST - Cashier logout now clears the Django session without a refresh token

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow / Make Cashier Login Real.

Why this item: the cashier login flow already stores JWTs and also creates a Django session, but logout previously depended on the refresh token being present. That left a small edge case where the session could survive if refresh storage was missing or stale.

Change made: updated the logout API to always clear the Django session and to blacklist the refresh token only when one is supplied. Updated the cashier logout button to call the logout endpoint even when the refresh token is missing, and added a regression test proving the session clears on logout without a refresh token.

Files touched:
- `apps/users/views.py`
- `apps/users/tests/test_views.py`
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_views.LogoutViewAPITest apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state -v 2 --keepdb` -> 2 tests OK.
- Django system check reported no issues during the test run.

Next recommended action: browser-smoke `/cashier/` sign-in and sign-out once to confirm the password clears, the logout button returns to the login panel, and the session no longer keeps the cashier signed in.

## 2026-06-20 23:00 AST - Cuadre generation now blocks double-submits while saving

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the cashier Cuadre flow is already idempotent, but the UI still let the cashier re-trigger generation while a save was in flight. A small busy guard makes the button feel safer and prevents accidental duplicate requests during desk work.

Change made: added a `cuadreBusy` guard around `loadCuadre()`, disabled the `Generate Cuadre` button while the ledger fetch/save is running, and restored the button label when the flow finishes. Added a regression assertion so the template keeps the new button id and busy-state strings.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_cuadre_save_status_banner -v 2 --keepdb` -> 1 test OK.
- Django system check reported no issues during the test run.

Next recommended action: smoke-test the live Cuadre button once, then move to the next remaining cashier-facing button flow or room-status polish item.
## 2026-06-21 00:00 AST - Healthcheck now proves cache ping cleanup

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the health endpoint should stay non-mutating, and the next safe step was to make sure the regression test actually proves the temporary cache ping is removed while unrelated cache entries survive.

Change made: tightened the healthcheck regression test to pin the generated cache key, confirm the probe still returns healthy, and verify the temporary cache key is deleted without disturbing an existing cashier cache entry.

Files touched:
- `apps/core/tests/test_healthcheck.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.core.tests.test_healthcheck -v 2 --keepdb --noinput` -> 2 tests OK.

Next recommended action: return to the highest-priority cashier-facing blocker, starting with the remaining login/auth flow or the next core cashier button path that still needs live smoke testing.

## 2026-06-21 01:00 AST - Cashier login ignores stale bearer tokens

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: a stale access token in localStorage could still be attached to the cashier login request and poison a fresh sign-in after token expiry.

Change made: updated the cashier API helper to skip the Authorization header for public auth requests (`/api/auth/login/`, token obtain, and token refresh) so a saved bearer token cannot block a new login. Added a template test assertion to pin the public-auth exception in the cashier page source.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py check` -> OK.
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2 --keepdb` -> OK.

Next recommended action: live-smoke `/cashier/` with a stale localStorage token present, then confirm a fresh login still succeeds and loads the dashboard without manual token cleanup.
## 2026-06-21 02:00 AST - Cashier auth now retries once through refresh tokens

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: a valid refresh token should keep the cashier moving when the short-lived access token expires during desk work.

Change made: added a small `refreshAccessToken()` helper in the cashier template, taught the shared API wrapper to retry one time after a 401 by refreshing the access token, and kept the existing stale-token guard for public login requests. Extended the cashier template regression test to pin the refresh helper and retry branch.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_bootstraps_jwt_session_state -v 2 --keepdb --noinput` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: live-smoke `/cashier/` with an expired access token but valid refresh token, then move to the next cashier-facing button flow that still needs polish.

## 2026-06-21 03:00 AST - Cashier room cards sort by operational urgency

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier room grid already shows car presence labels, but the fastest way to scan the floor is to put the most urgent rooms first instead of leaving them in raw room-number order.

Change made: added a small cashier-only room sorter that bubbles `Car Present` rooms to the top, followed by `Needs Review`, `Maintenance`, `Sensor Offline`, and then `No Car`. The sorter is used both on initial room load and after selecting a room so the card order stays operationally focused after refreshes.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_handles_paginated_api_responses apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_uses_car_presence_labels -v 2 --keepdb --noinput` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: live-smoke `/cashier/` once and confirm the new room ordering makes active car rooms surface first without breaking room selection or the recent-activity panel.
## 2026-06-21 04:00 AST - Healthcheck cache cleanup stays non-destructive

Action-list item: Priority 1 - Stop Health Check From Clearing Cache.

Why this item: the health probe should prove cache connectivity without risking unrelated runtime keys, and the existing implementation now pings a dedicated key instead of clearing the cache.

Change made: added a regression test proving /api/health/ still returns healthy even if the temporary cache-key cleanup fails, while preserving unrelated cache data.

Files touched:
- apps/core/tests/test_healthcheck.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.core.tests.test_healthcheck --keepdb --noinput -v 2 -> 3 tests OK.

Next recommended action: move back to the highest-priority remaining cashier workflow item and keep advancing the core room/vehicle flow in one bounded pass.


## 2026-06-21 05:00 AST - Cashier room cards show car-present timing

Action-list item: Priority 0 - Make Car Presence Operationally Clear.

Why this item: the cashier room cards already showed occupancy state and duration, but the operator still needed a clearer "since when" marker for active cars.

Change made: updated the cashier room-card timeline line so occupied rooms now say "Car present since" instead of the more generic stay label, and added a fallback "First detected" line when a room has a present-state reading but no active session record yet.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_uses_car_presence_labels apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_active_occupancy_session_start_time -v 2 --keepdb --noinput` -> 2 tests OK.

Next recommended action: live-smoke `/cashier/` once and confirm the room cards now surface the car-present timing line cleanly while preserving room selection and recent-activity behavior.


## 2026-06-21 06:00 AST - Cashier bootstrap login smoke is clearer and stricter

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: cashier login is the first operator gate, and the bootstrap path needed a clearer operator hint plus a stronger proof that the login endpoint actually issues tokens for the provisioned cashier account.

Change made: clarified the cashier login helper text to prefer the rerunnable  command, kept  as the single-account fallback, and tightened the login smoke tests so they assert token issuance plus the authenticated cashier username/role.

Files touched:
-
-
-
-

Verification:
-  -> OK.
-  -> 2 tests OK.

Next recommended action: live-smoke  once on the server and confirm the updated provisioning hint still matches the actual cashier login flow.


## 2026-06-21 06:00 AST - Cashier bootstrap login smoke is clearer and stricter

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: cashier login is the first operator gate, and the bootstrap path needed a clearer operator hint plus a stronger proof that the login endpoint actually issues tokens for the provisioned cashier account.

Change made: clarified the cashier login helper text to prefer the rerunnable bootstrap_motel_users command, kept bootstrap_cashier as the single-account fallback, and tightened the login smoke tests so they assert token issuance plus the authenticated cashier username and role.

Files touched:
- templates/revenue/cashier.html
- apps/users/tests/test_views.py
- apps/users/tests/test_bootstrap_cashier_command.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python -m py_compile apps/users/tests/test_views.py apps/users/tests/test_bootstrap_cashier_command.py -> OK.
- .venv/bin/python manage.py test apps.users.tests.test_views.LoginViewAPITest.test_login_with_valid_credentials apps.users.tests.test_bootstrap_cashier_command.BootstrapCashierCommandTest.test_bootstrapped_cashier_can_get_jwt_tokens -v 2 --keepdb --noinput -> 2 tests OK.

Next recommended action: live-smoke /cashier/ once on the server and confirm the updated provisioning hint still matches the actual cashier login flow.

## 2026-06-21 07:00 AST - Cashier bootstrap guidance now matches the smoke test

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier portal is still the first operator gate, and the bootstrap hint should match the live guidance expected by the cashier smoke test.

Change made: changed the cashier login helper copy from “Prefer” to “Run” so the on-screen provisioning instructions match the documented bootstrap path and the existing smoke assertion.

Files touched:
- templates/revenue/cashier.html
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username --keepdb --noinput --verbosity 2 -> OK.

Next recommended action: live-smoke /cashier/ once on the server and confirm the provisioning hint still matches the cashier login flow.

## 2026-06-21 08:00 AST - Cashier login form submits on Enter

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier page already had real bootstrap guidance and JWT handling, but the login box still required a mouse click instead of a normal form submit.

Change made: wrapped the cashier login inputs in a real form, added Enter-key submit support, and set the password input to current-password autocomplete. Added a regression assertion for the rendered submit handler.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2 --keepdb --noinput -> OK.

Next recommended action: confirm the cashier login flow end to end on the live app and then continue tightening the remaining cashier button paths.


## 2026-06-21 09:00 AST - Cashier login now auto-focuses username

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier login flow is already real, but it still required a click before typing could start after loading the portal or returning from logout/session reset.

Change made: added autofocus to the cashier username field and refocused that field when the login panel is shown again, so the desk can start typing immediately after the portal loads or returns to login.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2 --keepdb --noinput -> 1 test OK.

Next recommended action: live-smoke /cashier/ in a browser and confirm the username field receives focus on load and after logout/session expiration.

## 2026-06-21 10:00 AST - Cashier login now refocuses the username field

Action-list item: Priority 0 - Fix Cashier Frontend Auth Flow.

Why this item: the cashier portal already had real bootstrap guidance, Enter-submit support, and session cleanup, but after logout or session-expiry the login form still benefited from explicitly putting the cursor back in the username field.

Change made: added autofocus to the cashier username input and a small focus helper that re-centers the cursor on the username field whenever the login panel is shown again.

Files touched:
- templates/revenue/cashier.html
- apps/revenue/tests/test_views.py
- docs/RANGO_LOG.md

Verification:
- .venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_default_username -v 2 --keepdb --noinput -> 1 test OK.

Next recommended action: browser-smoke /cashier/ and confirm the username field receives focus on initial load and after logout/session expiration.

## 2026-06-21 11:00 AST - Lean room vehicle payload for cashier polling

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: customer vehicle tracking is already wired into the cashier flow, but the room polling path was still serializing the full nested vehicle payload for every room, which includes extra room-context lookups that the cashier room grid does not need.

Change made: added a lightweight room vehicle serializer for `RoomSerializer.current_vehicle`, kept the full vehicle serializer for vehicle search and rental-session payloads, and added `select_related("current_vehicle")` to the room queryset so the cashier room grid can poll attached vehicles more efficiently. Added a regression assertion that the room attach response does not leak the heavier vehicle room-context payload.

Files touched:
- `apps/rooms/serializers.py`
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest -v 2 --keepdb --noinput` -> 21 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` and confirm the room grid, selected-room vehicle hint, and vehicle lookup still work cleanly; if more vehicle work is needed, surface the attached vehicle summary on the manager room editor.
## 2026-06-21 12:00 AST - Manager room editor shows attached vehicle summary

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle workflow already surfaces room and session context, and the manager room editor should show the attached vehicle too so room setup and corrections stay in sync with the front desk.

Change made: added a current vehicle summary block to the manager room editor, added a vehicle column to the room table, and made room search match attached vehicle plate, make, model, and color. The editor now shows the selected room's attached vehicle or a clear no-vehicle state.

Files touched:
- `templates/rooms/room_config.html`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.ManagerViewTest.test_room_config_contains_editor_fields -v 2 --keepdb --noinput` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/manager/rooms/` as a manager account and confirm the vehicle summary, room table column, and vehicle search all read cleanly with a room that already has an attached car.

## 2026-06-21 13:00 AST - Fix Cuadre tier mapping and shift ledger save path

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the cashier Cuadre flow was still translating ledger tier names inconsistently, which could zero out paper-format Cuadre counts and save an incomplete shift ledger.

Change made: added shared tier-mapping helpers in the revenue view, fixed the Cuadre PDF payload to use human-readable tier counts and revenues, and fixed `generate_shift` to persist the real per-tier counts, revenues, subtotal, and ATH subtotal when saving a shift ledger. Added regression coverage for both the Cuadre PDF payload mapping and the saved shift ledger values.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python -m pytest --no-cov apps/revenue/tests/test_views.py -k "generate_shift_updates_existing_ledger_for_same_shift or cuadre_maps_human_tier_counts_into_pdf_payload or cuadre_uses_selected_shift_number"` -> 3 tests passed.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/`, open Cuadre, and confirm the paper-format output and saved ledger totals match a real shift.

## 2026-06-21 14:00 AST - Cuadre save banner shows persisted totals

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the Cuadre screen already showed the paper-format output and auto-saved the shift ledger, but the cashier still had to cross-check the saved values elsewhere. Showing the saved subtotal and ATH total in the save banner makes the persisted result immediately visible during a shift.

Change made: updated the cashier Cuadre autosave banner to include the saved subtotal and ATH total from `/api/revenue/generate-shift/`, so the cashier can compare the persisted ledger against the paper-format output at a glance. Added regression coverage for the new banner text.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_cuadre_save_status_banner -v 2` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.
- Live smoke: `GET http://127.0.0.1:8000/cashier/` -> HTTP 200, and the rendered page source includes the new `Saved subtotal $... ATH total $...` banner text.

Next recommended action: browser-smoke `/cashier/`, open Cuadre, and confirm the paper-format output and saved ledger totals match a real shift.

## 2026-06-21 15:00 AST - Cuadre save banner names the selected shift window

Action-list item: Priority 1 - Make Cuadre Useful For A Cashier Shift.

Why this item: the Cuadre save banner already showed the persisted totals, but it only named the numeric shift. Showing the selected shift label makes the saved ledger easier to cross-check at a glance.

Change made: updated the cashier Cuadre autosave banner to use the selected shift option text when reporting the saved ledger, so the cashier sees the actual shift window label alongside subtotal and ATH total. Added a regression assertion for the shift-label lookup in the template.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_cuadre_save_status_banner -v 2 --keepdb --noinput` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` and confirm the Cuadre save banner shows the selected shift window label clearly during a live save.

## 2026-06-21 16:00 AST - Cashier sensor simulate returns a helpful hint for tentative readings

Action-list item: Priority 1 - Wire Sensor Input Through Occupancy State Machine.

Why this item: a single simulated reading can legitimately stay in the tentative state while the arrival timer runs, but the cashier still needs immediate feedback instead of a bare "vacant" response.

Change made: updated the sensor simulate response to include a cashier-facing `status_hint` for tentative arrival/departure readings, and updated the cashier Send Reading log line to show that hint alongside the current state. Added a regression assertion that the cashier simulate endpoint returns the hint when the first low-distance reading does not yet confirm occupancy.

Files touched:
- `apps/occupancy/views.py`
- `apps/occupancy/tests/test_views.py`
- `templates/revenue/cashier.html`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.occupancy.tests.test_views.SensorReadingViewSetAPITest.test_cashier_can_still_simulate_sensor_reading -v 2 --keepdb --noinput` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/`, click Send Reading for a room, and confirm the log line now reads like a useful sensor hint instead of just the raw state.
## 2026-06-21 17:00 AST - Remove implicit cashier default username

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier login form still auto-filled `cashier` when no environment override was set, which kept a demo-like default around even though the app now expects explicit provisioning via bootstrap commands.

Change made: removed the hardcoded cashier fallback from the cashier portal context so the username field is blank unless `MOTEL_CASHIER_USERNAME` is set. Updated the cashier login regression to expect the blank default while still allowing an environment override.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_bootstrap_help_and_blank_default_username apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_prefills_username_from_env -v 2 --keepdb --noinput` -> 2 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/` to confirm the login field is blank by default, then continue the remaining cashier-visible operational polish.

## 2026-06-21 18:00 AST - Cashier legacy login route uses the cashier shell

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: `/cashier/login/` still redirected to the generic Django login page even though the cashier portal already has a dedicated login-only shell and JWT/session handoff. Rendering the cashier shell keeps the login flow in one place and preserves the return URL.

Change made: updated the legacy cashier login route to render `templates/revenue/cashier.html` with `login_only=True` and the preserved `next` URL, while still redirecting authenticated users straight to their target page. Added a focused regression test that checks the login-only shell context and markup instead of the old redirect.

Files touched:
- `apps/revenue/views.py`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test --keepdb apps.revenue.tests.test_views.TemplateViewTest.test_cashier_login_view_renders_cashier_login_shell && .venv/bin/python manage.py check` -> focused test OK, system check OK.

Next recommended action: browser-smoke `/cashier/login/` and `/cashier/` with the cashier account to confirm the login-only shell and the post-login redirect both behave as expected.

## 2026-06-21 19:00 AST - Vehicle reattach is now idempotent

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle flow is now live, but reattaching the same vehicle could still spam duplicate `Vehicle Attached` events and clutter the recent-activity feed.

Change made: updated the room vehicle attach endpoint to skip creating a new attachment event when the selected vehicle is already attached to the room, while still keeping the room and active rental session in sync. Added a regression test proving repeated attach clicks keep only one attachment event.

Files touched:
- `apps/rooms/views.py`
- `apps/rooms/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.rooms.tests.test_views.RoomViewSetAPITest.test_cashier_can_attach_vehicle_to_room apps.rooms.tests.test_views.RoomViewSetAPITest.test_reattaching_same_vehicle_does_not_duplicate_attachment_event apps.rooms.tests.test_views.RoomViewSetAPITest.test_attach_vehicle_carries_to_active_rental_session -v 2 --keepdb --noinput` -> 3 tests OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke the vehicle lookup panel in `/cashier/` and confirm repeated attach clicks no longer add duplicate car-activity entries.

## 2026-06-21 20:00 AST - Cashier room selection auto-loads vehicle matches

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle lookup panel already exists, but selecting a room still left the search results stale until the cashier clicked another button. Auto-refreshing the lookup on room selection makes the room/vehicle attach flow faster and less error-prone.

Change made: updated the cashier `selectRoom()` flow to prefill the room label and automatically refresh vehicle search results for the selected room. Added a focused regression test proving the cashier template includes the new auto-refresh behavior.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_auto_loads_vehicle_search_for_selected_room -v 2 --keepdb --noinput` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/`, click a room, and confirm the vehicle lookup panel immediately refreshes with matches for that room.

## 2026-06-21 20:00 AST - Cashier room selection auto-loads vehicle matches

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier vehicle lookup panel already exists, but selecting a room still left the search results stale until the cashier clicked another button. Auto-refreshing the lookup on room selection makes the room/vehicle attach flow faster and less error-prone.

Change made: updated the cashier `selectRoom()` flow to prefill the room label and automatically refresh vehicle search results for the selected room. Added a focused regression test proving the cashier template includes the new auto-refresh behavior.

Files touched:
- `templates/revenue/cashier.html`
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_auto_loads_vehicle_search_for_selected_room -v 2 --keepdb --noinput` -> 1 test OK.
- `.venv/bin/python manage.py check` -> OK.

Next recommended action: browser-smoke `/cashier/`, click a room, and confirm the vehicle lookup panel immediately refreshes with matches for that room.

## 2026-06-21 21:00 AST - Cashier vehicle room-selection regression test now matches the current flow

Action-list item: Priority 0 - Add Customer Vehicle Tracking.

Why this item: the cashier room-selection flow now uses a `selectedRoomLabel` helper to prefill the vehicle search and auto-refresh results, but the regression test was still asserting the older inline expression.

Change made: updated the vehicle-attach template assertion in `apps/revenue/tests/test_views.py` so the test tracks the current room-selection behavior and keeps the vehicle lookup auto-refresh path covered.

Files touched:
- `apps/revenue/tests/test_views.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_shows_cuadre_save_status_banner apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_exposes_cuadre_pdf_download apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_contains_vehicle_attach_controls apps.revenue.tests.test_views.TemplateViewTest.test_cashier_view_auto_loads_vehicle_search_for_selected_room -v 2 --keepdb --noinput` -> 4 tests OK.

Next recommended action: browser-smoke `/cashier/`, select a room, and confirm the vehicle search field and results refresh immediately.
## 2026-06-21 22:00 AST - Cashier bootstrap reruns no longer need a password for existing users

Action-list item: Priority 0 - Make Cashier Login Real.

Why this item: the cashier bootstrap path should be safe to rerun in ops without forcing the operator to remember a password when the cashier account already exists.

Change made: updated `bootstrap_cashier` so an existing cashier can be re-provisioned without supplying `--password`; password changes still require `--reset-password`, and the command still enforces a password when creating a brand-new cashier. Added a regression test that covers rerunning the command without a password, rerunning it with a password but no reset, and resetting the password explicitly.

Files touched:
- `apps/users/management/commands/bootstrap_cashier.py`
- `apps/users/tests/test_bootstrap_cashier_command.py`
- `docs/RANGO_LOG.md`

Verification:
- `.venv/bin/python manage.py test apps.users.tests.test_bootstrap_cashier_command -v 2 --keepdb --noinput` -> 8 tests OK.

Next recommended action: do the same rerunnable-password treatment for `bootstrap_motel_users` so the multi-role bootstrap path matches the cashier-only command.
