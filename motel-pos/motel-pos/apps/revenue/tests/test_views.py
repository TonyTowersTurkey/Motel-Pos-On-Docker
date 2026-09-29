"""Integration tests for DRF ViewSets and API endpoints."""

import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.revenue.models import OccupancySession, ShiftLedger
from apps.rooms.models import Amenity, PricingTier, Room, RoomAmenity
from apps.users.tests.factories import UserFactory


class HealthCheckTest(APITestCase):
    """Tests for the /api/health/ endpoint."""

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    )
    def test_health_check_returns_200(self) -> None:
        # When Redis is unavailable (dummy backend), healthcheck returns 503.
        # Test that the endpoint at least returns a valid response without crashing.
        response = self.client.get("/api/health/")
        self.assertIn(response.status_code, [200, 503])


class TemplateViewTest(APITestCase):
    """Tests for template-based frontend views."""

    def get_authenticated_cashier(self):
        user = UserFactory(username="cashier_view_user", role="cashier")
        self.client.force_login(user)
        return self.client.get("/cashier/")

    def test_dashboard_view_returns_200(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/manager/")

    def test_cashier_view_returns_200(self) -> None:
        response = self.client.get("/cashier/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/login/"))

        response = self.get_authenticated_cashier()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Motel Desk")

    def test_cashier_login_view_renders_cashier_login_shell(self) -> None:
        response = self.client.get(
            "/cashier/login/",
            {"next": "/cashier/?tab=rooms&room=101"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["login_only"], True)
        self.assertEqual(response.context["next_url"], "/cashier/?tab=rooms&room=101")
        self.assertContains(response, "Motel Desk")
        self.assertContains(response, "const LOGIN_ONLY = true;")
        self.assertContains(response, "window.location.href = NEXT_URL || '/cashier/';")

    def test_manager_view_returns_200(self) -> None:
        user = UserFactory(username="manager_template", role="manager")
        self.client.force_login(user)
        response = self.client.get("/manager/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_contains_rooms_html(self) -> None:
        user = UserFactory(username="manager_dashboard", role="manager")
        self.client.force_login(user)
        response = self.client.get("/manager/")
        self.assertContains(response, "Motel Manager")

    def test_cashier_view_contains_login(self) -> None:
        response = self.client.get("/login/?next=/cashier/")
        self.assertContains(response, "Motel POS")
        self.assertNotContains(response, "Motel Desk — Cashier View")

    def test_cashier_view_shows_bootstrap_help_and_blank_default_username(self) -> None:
        response = self.client.get("/cashier/login/")
        self.assertContains(response, "Need the cashier login? Run")
        self.assertContains(response, "bootstrap_cashier")
        self.assertContains(response, "bootstrap_motel_users")
        self.assertContains(response, "--reset-password")
        self.assertContains(response, 'value=""')
        self.assertContains(response, 'placeholder="Cashier username"')
        self.assertNotContains(response, "change_me")
        self.assertContains(response, "Enter both username and password.")
        self.assertContains(response, "const apiMessage = friendlyError(e, 'Unable to sign in.');")
        self.assertContains(
            response,
            "const loginMessage = String(e?.message || '').startsWith('HTTP 401:')",
        )
        self.assertContains(
            response,
            "const isPublicAuthRequest = p === 'auth/login/' || p === 'auth/token/obtain/' || p === 'auth/token/refresh/';",
        )
        self.assertContains(response, "bootstrap_cashier")
        self.assertContains(response, "Login failed: ${apiMessage}")
        self.assertContains(response, "onsubmit=\"doLogin();return false;\"")
        self.assertContains(response, "autocomplete=\"current-password\"")
        self.assertContains(response, 'autofocus')
        self.assertContains(response, 'function focusLoginUsername()')
        self.assertContains(response, 'focusLoginUsername();')
        self.assertContains(response, "const p = document.getElementById('loginPass').value;")
        self.assertContains(response, 'function clearLoginPassword()')
        self.assertContains(
            response,
            "clearLoginPassword();\n        document.getElementById('loginErr').textContent = 'Invalid credentials. Try again.'",
        )
        self.assertNotContains(response, "loginPass').value.trim()")

    @patch.dict(os.environ, {"MOTEL_CASHIER_USERNAME": "desk_cashier"}, clear=False)
    def test_cashier_view_prefills_username_from_env(self) -> None:
        response = self.client.get("/cashier/login/")
        self.assertContains(response, 'value="desk_cashier"')

    def test_cashier_view_handles_paginated_api_responses(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function listResults(payload)")
        self.assertContains(response, "async function fetchAllPages(path)")
        self.assertContains(response, "function sortRoomsForCashier(rooms)")
        self.assertContains(
            response,
            "const rooms = sortRoomsForCashier(await fetchAllPages('rooms/?page_size=100'));",
        )
        self.assertContains(response, "const tiers = listResults(tiersData);")
        self.assertContains(response, "const ledgers = listResults(ledgerData);")

    def test_cashier_view_exposes_clear_room_status_board(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, 'function roomStatusInfo(room)')
        self.assertContains(response, 'Room Status')
        self.assertContains(response, 'data-room-filter="clear"')
        self.assertContains(response, 'data-room-filter="present"')
        self.assertContains(response, 'id="roomSearch"')
        self.assertContains(response, 'id="selectedRoomBar"')
        self.assertContains(response, 'function renderRoomBoard()')
        self.assertContains(response, 'function roomMatchesCurrentView(room)')
        self.assertContains(response, 'Occupied')
        self.assertContains(response, 'Vacant')
        self.assertContains(response, 'function sortRoomsForCashier(rooms)')
        self.assertContains(response, "const canRent = ['clear', 'present'].includes(status.bucket) && !status.requiresDepartureConfirmation;")
        self.assertContains(response, "if (!['clear', 'present'].includes(selectedStatus.bucket) || selectedStatus.requiresDepartureConfirmation)")
        self.assertNotContains(response, "Only vacant rooms can start a rental")

    def test_cashier_tabs_are_nested_under_cashier_sidebar_navigation(self) -> None:
        response = self.get_authenticated_cashier()
        content = response.content.decode()
        self.assertContains(response, 'class="pos-cashier-tabs" id="dashTabs"')
        self.assertContains(response, 'class="tab pos-cashier-tab active"')
        self.assertLess(content.index("Cashier POS"), content.index('id="dashTabs"'))
        self.assertContains(response, "if (window.innerWidth <= 1024) document.querySelector('[data-pos-nav-close]')?.click();")
        self.assertContains(response, 'id="selectedRoomDetails"')
        self.assertContains(response, "Assign Vehicle")
        self.assertContains(response, "function openVehicleAssignment()")
        self.assertContains(response, "function assignVehicleToSelectedRoom(vehicleId)")
        self.assertContains(response, "['Entered', room.entered_at ? eventWhen(room.entered_at) : 'Not entered']")
        self.assertContains(response, "['Max Stay', room.max_stay_at ? eventWhen(room.max_stay_at) : '—']")
        self.assertContains(response, "function selectedRoomPlateLabel(plate)")
        self.assertContains(response, "/^[A-Za-z]{3}[0-9]{3}$/")
        self.assertContains(response, "`${value.slice(0, 3)}-${value.slice(3)}`")
        self.assertContains(response, "const plate = selectedRoomPlateLabel(room.current_vehicle?.license_plate || 'NO PLATE');")
        self.assertContains(response, 'class="selected-room-plate"')
        self.assertContains(response, 'id="selectedRoomDepartureButton"')
        self.assertContains(response, "Vehicle Won't Return")
        self.assertContains(response, "requiresDepartureConfirmation")
        self.assertContains(response, "function confirmVehicleDeparture()")
        self.assertContains(response, "room marked dirty")
        self.assertContains(response, 'class="plate-number"')
        self.assertContains(response, "Puerto Rico")
        self.assertContains(response, "Isla del Encanto")
        self.assertNotContains(response, "['Building', room.edificio")
        self.assertNotContains(response, "['Pricing Tier', room.pricing_tier_code")
        self.assertNotContains(response, "['Max Guests', room.max_occupants")
        self.assertNotContains(response, "['A/C', room.ac")
        self.assertNotContains(response, "['TV', room.tv")
        self.assertContains(response, "Create &amp; Assign to Room")
        self.assertContains(response, "function createAndAssignVehicle()")
        self.assertContains(response, "Entry Time (24-hour)")
        self.assertContains(response, 'placeholder="YYYY-MM-DD HH:mm"')
        self.assertNotContains(response, 'type="datetime-local"')
        self.assertContains(response, 'oninput="this.value=this.value.toUpperCase()"')
        self.assertContains(response, ".value.trim().toUpperCase()")
        self.assertContains(response, "const vehicle = await fetchJSON('vehicles/', {method: 'POST', body: payload});")
        self.assertContains(response, "await assignVehicleToSelectedRoom(vehicle.id);")

    def test_cashier_view_flags_present_rooms_without_vehicle_attachment(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function roomVehicleLine(room, status)")
        self.assertContains(response, "Vehicle: Not attached")
        self.assertContains(response, "const vehicleLine = roomVehicleLine(r, status);")

    def test_cashier_view_shows_active_occupancy_session_start_time(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function occupancySessionLine(room, status)")
        self.assertContains(response, "function stayDuration(timestamp)")
        self.assertContains(response, "Car present since")
        self.assertContains(response, "Active stay")
        self.assertContains(response, "First detected:")
        self.assertContains(response, 'class="room-session"')
        self.assertContains(response, "const occupancyLine = occupancySessionLine(r, status);")
        self.assertContains(response, "stayDuration(session.check_in)")
        self.assertContains(response, "room?.active_occupancy_session")

    def test_cashier_view_shows_latest_occupancy_event_confidence(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function occupancyConfidenceLine(room)")
        self.assertContains(response, "Decision confidence:")
        self.assertContains(response, "latest_occupancy_event")

    def test_cashier_view_shows_recent_car_activity_panel(self) -> None:
        response = self.get_authenticated_cashier()
        content = response.content.decode()
        self.assertContains(response, "Recent Car Activity")
        self.assertContains(response, 'class="panel room-status-panel"')
        self.assertContains(response, 'class="compact-room-stats"')
        self.assertLess(content.index("Room Status"), content.index("Recent Car Activity"))

    def test_cashier_places_selected_room_in_sticky_status_sidebar(self) -> None:
        response = self.get_authenticated_cashier()
        content = response.content.decode()
        self.assertContains(response, ".content{flex:1;padding:20px 24px")
        self.assertContains(response, ".selected-room-bar{display:none;padding:12px")
        self.assertContains(response, ".side{position:sticky;top:0;align-self:flex-start;width:260px;max-height:100%;overflow-y:auto")
        self.assertLess(content.index("Room Status"), content.index('id="selectedRoomBar"'))
        self.assertLess(content.index('id="selectedRoomBar"'), content.index("Recent Car Activity"))
        self.assertContains(response, "function loadRecentEvents()")
        self.assertContains(
            response,
            "const recentEventQuery = eventTypes.map(eventType => encodeURIComponent(eventType)).join(',');",
        )
        self.assertContains(response, "fetchJSON(`events/?event_type=${recentEventQuery}`)")
        self.assertContains(response, "Car Arrived")
        self.assertContains(response, "Car Left")
        self.assertContains(response, "Vehicle Attached")
        self.assertContains(response, "Vehicle Cleared")

    def test_cashier_cuadre_selector_exposes_all_supported_shifts(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, 'id="cuadreShift"')
        self.assertContains(response, 'value="1">Shift 1 - 23:00-06:59')
        self.assertContains(response, 'value="2">Shift 2 - 07:00-14:59')
        self.assertContains(response, 'value="3">Shift 3 - 15:00-22:59')

    def test_cashier_sales_shift_selection_refreshes_sales_list(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertContains(
            response,
            'id="salesShift" onchange="loadSalesSummary()"',
        )
        self.assertContains(
            response,
            '<option value="all" selected>All 3 shifts · 23:00 previous day-22:59</option>',
            html=True,
        )
        self.assertContains(response, "let shiftRentalSort = {key: 'start_time', dir: 'asc'}")
        self.assertContains(
            response,
            'await fetchAllPages(`rental-sessions/?date=${dateVal}&shift=${shift}&ordering=start_time`)',
        )

    def test_cashier_sales_view_is_report_only(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertNotContains(response, 'id="shiftRentalActions"')
        self.assertNotContains(response, 'id="rentalRoomLabel"')
        self.assertNotContains(response, 'function setRentalDurationChoice(')
        self.assertContains(response, 'id="rentalDialog"')
        self.assertContains(response, 'id="selectedRoomRentalButton"')

    def test_cashier_rental_table_uses_live_actual_duration(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertContains(response, "if (key === 'duration_hours') return rentalElapsedSeconds(row)")
        self.assertContains(response, "function rentalElapsedSeconds(row, now=Date.now())")
        self.assertContains(response, "window.setInterval(updateShiftRentalClocks, 1000)")
        self.assertContains(response, "rentalSortLabel('duration_hours', 'Actual Time')")
        self.assertContains(response, 'data-rental-elapsed="${Number(sale.session_id)}"')

    def test_cashier_rental_table_shows_only_current_billing_duration(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertContains(response, "if (elapsedHours > 16) return 24")
        self.assertContains(response, "if (elapsedHours > 8) return 16")
        self.assertContains(response, 'data-rental-duration="${Number(sale.session_id)}"')
        self.assertNotContains(response, "function applyCurrentRentalDuration(")
        self.assertNotContains(response, "function setRentalSessionDuration(")
        self.assertNotContains(response, "setRentalSessionDuration(${sale.session_id},8)")
        self.assertNotContains(response, "setRentalSessionDuration(${sale.session_id},16)")
        self.assertNotContains(response, "setRentalSessionDuration(${sale.session_id},24)")

    def test_cashier_rental_table_omits_redundant_type_column(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertNotContains(response, "<th>Type</th>")
        self.assertNotContains(response, "sale.rental_type || 'Single'")
        self.assertContains(response, '<tr><td colspan="10"')

    def test_cashier_header_shows_live_puerto_rico_time(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertContains(response, 'aria-label="Current Puerto Rico time"')
        self.assertContains(response, 'id="puertoRicoClock"')
        self.assertContains(response, "timeZone: 'America/Puerto_Rico'")
        self.assertContains(response, 'hour12: false')
        self.assertContains(response, 'window.setInterval(updatePuertoRicoClock, 1000)')

    def test_cashier_formats_all_display_times_in_puerto_rico(self) -> None:
        response = self.get_authenticated_cashier()

        self.assertContains(response, "window.MOTEL_TIME_ZONE = 'America/Puerto_Rico'")
        self.assertContains(response, 'return motelFormatDateTime(eventDate)')
        self.assertContains(response, 'return motelFormatShortDateTime(d)')
        self.assertContains(response, 'return motelDateTimeInputValue(date)')
        self.assertNotContains(response, '.toLocaleString(')
        self.assertNotContains(response, '.toLocaleDateString(')
        self.assertNotContains(response, '.toLocaleTimeString(')

    @patch('apps.revenue.views.timezone.localdate', return_value=date(2026, 6, 18))
    def test_cashier_view_uses_local_timezone_dates(self, _mock_localdate) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, 'salesDate')
        self.assertContains(response, 'cuadreDate')
        self.assertContains(response, '2026-06-18')
        self.assertNotContains(response, "toISOString().split('T')[0]")

    def test_cashier_view_shows_cuadre_save_status_banner(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "id='cuadreSaveStatus'")
        self.assertContains(response, "role='status'")
        self.assertContains(response, 'Saving or updating shift ledger...')
        self.assertContains(response, 'id="generateCuadreBtn"')
        self.assertContains(response, 'let cuadreBusy = false;')
        self.assertContains(response, 'generateBtn.disabled = true;')
        self.assertContains(response, 'Ledger saved:')
        self.assertContains(response, "shiftLabel = document.getElementById('cuadreShift')?.selectedOptions?.[0]?.textContent")
        self.assertContains(response, 'Saved subtotal $')
        self.assertContains(response, 'ATH total $')
        self.assertContains(response, 'Ledger save failed:')
        self.assertContains(response, 'Re-running the same date and shift updates the existing ledger instead of creating a duplicate.')

    def test_cashier_view_exposes_cuadre_pdf_download(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, 'Download PDF')
        self.assertContains(response, 'function downloadCuadrePdf()')
        self.assertContains(response, 'ledgers/cuadre/${encodeURIComponent(dateVal)}/?shift=${shift}')

    def test_cashier_view_removes_sidebar_vehicle_lookup_but_keeps_rental_vehicle_fields(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertNotContains(response, "<h3>Vehicle Lookup</h3>", html=True)
        self.assertNotContains(response, 'id="vehicleSearch"')
        self.assertNotContains(response, "Find Selected Room Vehicle")
        self.assertNotContains(response, 'id="vehicleShapePicker"')
        self.assertContains(response, 'id="rentalDialogPlateSearch"')
        self.assertContains(response, 'id="rentalDialogShapePicker"')
        self.assertContains(response, "function searchRentalDialogVehicle()")

    def test_cashier_room_selection_does_not_depend_on_removed_sidebar_controls(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertNotContains(response, "document.getElementById('overRoom').value = id;")
        self.assertNotContains(response, "document.getElementById('vehicleSearch').value = selectedRoomLabel;")

    def test_cashier_activity_log_is_collapsed_at_page_bottom(self) -> None:
        response = self.get_authenticated_cashier()
        content = response.content.decode()
        self.assertContains(response, '<details class="panel activity-drawer">')
        self.assertContains(response, '<summary>Activity Log</summary>')
        self.assertContains(response, 'id="eventLog"')
        self.assertNotContains(response, '<h3>Activity Log</h3>', html=True)
        self.assertLess(content.index("Recent Car Activity"), content.index('<details class="panel activity-drawer">'))

    def test_cashier_view_removes_quick_override_panel(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertNotContains(response, '<h3>Quick Override</h3>', html=True)
        self.assertNotContains(response, 'id="overRoom"')

    def test_cashier_room_actions_validate_selected_room(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertNotContains(response, "Simulate Reading")
        self.assertNotContains(response, "simSensor()")
        self.assertContains(response, "function resolveSelectedRoom(purpose)")
        self.assertContains(response, "const message = `Select a room before ${purpose}.`;")
        self.assertContains(response, "const room = resolveSelectedRoom(`overriding to ${action}`);")
        self.assertContains(response, "if (!room) return;")

    def test_cashier_view_shows_vehicle_room_context(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function vehicleContextSummary(vehicle)")
        self.assertContains(response, "function vehicleContextHtml(vehicle)")
        self.assertContains(response, "Attached rooms:")
        self.assertContains(response, "Active rentals:")
        self.assertContains(response, "room_context.current_rooms")
        self.assertContains(response, "room_context.active_rental_sessions")
        self.assertContains(response, "session.room_number || session.room_id")
        self.assertContains(response, "vehicle-context")

    def test_cashier_vehicle_attach_clear_refreshes_recent_activity(self) -> None:
        response = self.get_authenticated_cashier()
        content = response.content.decode()
        self.assertIn(
            "log(`Vehicle attached to ${room}`, 'ok');\n    loadRooms();\n    loadRecentEvents();",
            content,
        )
        self.assertIn(
            "log(`Vehicle cleared from ${room}`, 'ok');\n    loadRooms();\n    loadRecentEvents();",
            content,
        )
        self.assertIn(
            "const roomLabel = event.room_number ? `Room ${event.room_number}` : event.room_id;",
            content,
        )

    def test_cashier_view_formats_vehicle_api_errors(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function formatApiError(status, text)")
        self.assertContains(response, "function apiErrorDetail(payload)")
        self.assertContains(
            response,
            "function friendlyError(error, fallback='Request failed.')",
        )
        self.assertContains(response, "Create vehicle failed: ${message}")
        self.assertContains(response, "Attach vehicle failed: ${friendlyError(e)}")
        self.assertContains(response, "Clear vehicle failed: ${friendlyError(e)}")

    def test_cashier_view_marks_manager_only_controls(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "function applyRoleVisibility()")
        self.assertContains(response, "function roleCanAccess(minRole)")
        self.assertContains(response, 'data-min-role="manager"')
        self.assertContains(response, "currentUser?.capabilities?.manager_access")
        self.assertContains(response, "!roleCanAccess(el?.dataset?.minRole)")
        self.assertContains(response, "This section requires a manager account.")
        self.assertContains(response, "class=\"tab pos-cashier-tab role-restricted\"")
        self.assertContains(response, "class=\"panel role-restricted\"")
        self.assertContains(response, "Pricing Tiers")
        self.assertContains(response, "Ledger History")
        self.assertContains(response, "Reports")
        self.assertContains(response, "Reports require a manager account.")

    def test_cashier_vehicle_edit_controls_require_manager_role(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "const editAction = roleCanAccess('manager') ?")
        self.assertContains(response, "async function startVehicleEdit(vehicleId)")
        self.assertContains(response, "async function saveVehicleDetails()")
        self.assertContains(response, "Vehicle edits require a manager account.")

    def test_cashier_view_bootstraps_jwt_session_state(self) -> None:
        response = self.get_authenticated_cashier()
        self.assertContains(response, "async function bootstrapSession()")
        self.assertContains(response, "if (!token())")
        self.assertContains(response, "fetchJSON('users/profile/')")
        self.assertContains(response, "async function refreshAccessToken()")
        self.assertContains(response, "const refresh = localStorage.getItem('refresh_token');")
        self.assertContains(response, "localStorage.setItem('access_token', data.access);")
        self.assertContains(response, "if (p !== 'auth/token/refresh/' && await refreshAccessToken()) {")
        self.assertContains(response, "showDashboard();")
        self.assertContains(response, "clearSession('Session expired. Please sign in again.')")
        self.assertContains(response, "if (res.status === 401 && p !== 'auth/login/')")
        self.assertContains(response, "localStorage.removeItem('access_token')")
        self.assertContains(response, "localStorage.removeItem('refresh_token')")
        self.assertContains(response, "function doLogout()")
        self.assertContains(response, "fetch(API + 'auth/logout/'")
        self.assertContains(response, "const logoutPayload = { refresh: refresh || '' };")
        self.assertContains(response, "body: JSON.stringify(logoutPayload)")
        self.assertNotContains(response, "if (refresh && accessToken)")
        self.assertContains(response, 'clearLoginPassword();')
        self.assertContains(response, "if (LOGIN_ONLY) {")
        self.assertContains(response, "window.location.replace(NEXT_URL || '/cashier/')")
        self.assertNotContains(response, "form.action = '/logout/'")


class RoomViewSetTest(APITestCase):
    """Tests for /api/rooms/ endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_list_rooms_empty(self) -> None:
        response = self.client.get("/api/rooms/")
        self.assertEqual(response.status_code, 200)


class PricingTierViewSetTest(APITestCase):
    """Tests for /api/pricing-tiers/ endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(role="manager", password="admin123")
        self.client.force_authenticate(user=self.user)
        PricingTier.objects.create(
            code="TEST", price_per_night=50.0, description="Test"
        )

    def test_manager_can_list_tiers(self) -> None:
        response = self.client.get("/api/pricing-tiers/")
        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_tiers(self) -> None:
        cashier = UserFactory(username="cashier_pricing", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.get("/api/pricing-tiers/")

        self.assertEqual(response.status_code, 403)


class AmenityViewSetTest(APITestCase):
    """Tests for /api/amenities/ endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(role="manager", password="admin123")
        self.client.force_authenticate(user=self.user)
        Amenity.objects.create(name="test_amen", display_name="Test Amenity")

    def test_manager_can_list_amenities(self) -> None:
        response = self.client.get("/api/amenities/")
        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_amenities(self) -> None:
        cashier = UserFactory(username="cashier_amenities", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.get("/api/amenities/")

        self.assertEqual(response.status_code, 403)


class RoomAmenityViewSetTest(APITestCase):
    """Tests for /api/room-amenities/ endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(role="manager", password="admin123")
        self.client.force_authenticate(user=self.user)
        Room.objects.create(
            room_id="room_config_api",
            room_number="201",
            sensor_id="sensor_config_api",
        )
        amenity = Amenity.objects.create(
            name="mini_fridge",
            display_name="Mini Fridge",
        )
        RoomAmenity.objects.create(
            room_id="room_config_api",
            amenity_id=amenity.id,
        )

    def test_manager_can_list_room_amenities(self) -> None:
        response = self.client.get("/api/room-amenities/")
        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_room_amenities(self) -> None:
        cashier = UserFactory(username="cashier_room_amenities", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.get("/api/room-amenities/")

        self.assertEqual(response.status_code, 403)


class OccupancySessionViewSetTest(APITestCase):
    """Tests for raw occupancy session API permissions."""

    def setUp(self) -> None:
        self.manager = UserFactory(username="manager_session_api", role="manager")
        self.cashier = UserFactory(username="cashier_session_api", role="cashier")
        self.session = OccupancySession.objects.create(
            room_id="room_session_api",
            check_in=timezone.now(),
            source=OccupancySession.Source.FRONT_DESK,
            status=OccupancySession.Status.ACTIVE,
        )

    def test_manager_can_list_occupancy_sessions(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/sessions/")

        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_raw_occupancy_sessions(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/sessions/")

        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_checkout_raw_occupancy_session(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(f"/api/sessions/{self.session.pk}/checkout/")

        self.assertEqual(response.status_code, 403)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, OccupancySession.Status.ACTIVE)


class ShiftLedgerViewSetTest(APITestCase):
    """Tests for /api/ledgers/ endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(role="manager", password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_manager_can_list_ledgers(self) -> None:
        response = self.client.get("/api/ledgers/")
        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_ledgers(self) -> None:
        cashier = UserFactory(username="cashier_ledger_list", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.get("/api/ledgers/")

        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_create_raw_ledger(self) -> None:
        cashier = UserFactory(username="cashier_ledger_create", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.post(
            "/api/ledgers/",
            {
                "date": "2026-06-16",
                "shift_number": 1,
                "barra_amount": "5.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_cashier_can_still_read_cuadre(self) -> None:
        cashier = UserFactory(username="cashier_cuadre_read", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.get("/api/revenue/cuadre/?date=2026-06-16&shift=1")

        self.assertEqual(response.status_code, 200)

    @patch("apps.revenue.services.revenue_engine.compute_shift_for_day")
    def test_cuadre_uses_selected_shift_number(self, mock_compute) -> None:
        cashier = UserFactory(username="cashier_cuadre_shift", role="cashier")
        self.client.force_authenticate(user=cashier)
        mock_compute.return_value = {
            "date": "2026-06-16",
            "shift_number": 3,
            "tier_counts": {},
            "tier_revenues": {},
            "subtotal": 0,
            "ath_subtotal": 0,
            "active_rooms_count": 0,
        }

        response = self.client.get("/api/revenue/cuadre/?date=2026-06-16&shift=3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shift_number"], 3)
        mock_compute.assert_called_once_with(date(2026, 6, 16), shift_number=3)

    @patch("apps.revenue.services.revenue_engine.generate_cuadre_text_pdf")
    @patch("apps.revenue.services.revenue_engine.compute_shift_for_day")
    def test_cuadre_maps_human_tier_counts_into_pdf_payload(self, mock_compute, mock_pdf) -> None:
        cashier = UserFactory(username="cashier_cuadre_pdf", role="cashier")
        self.client.force_authenticate(user=cashier)
        mock_compute.return_value = {
            "date": "2026-06-16",
            "shift_number": 1,
            "tier_counts": {
                "1 BGO": 2,
                "2 Y0 Dndein": 1,
                "3 BOO": 0,
                "4 BUYS": 0,
                "9.S0": 0,
            },
            "tier_revenues": {
                "1 BGO": 80.0,
                "2 Y0 Dndein": 45.0,
                "3 BOO": 0.0,
                "4 BUYS": 0.0,
                "9.S0": 0.0,
            },
            "subtotal": 125,
            "ath_subtotal": 125,
            "active_rooms_count": 4,
        }
        mock_pdf.return_value = BytesIO(b"mock-cuadre")

        response = self.client.get("/api/revenue/cuadre/?date=2026-06-16&shift=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shift_number"], 1)
        tiers = mock_pdf.call_args.kwargs["tiers"]
        self.assertEqual(tiers["tier_1_bgo"]["count"], 2)
        self.assertEqual(tiers["tier_1_bgo"]["revenue"], 80.0)
        self.assertEqual(tiers["tier_2_y0_dndein"]["count"], 1)
        self.assertEqual(tiers["tier_2_y0_dndein"]["revenue"], 45.0)

    @patch("apps.revenue.services.revenue_engine.compute_shift_for_day")
    def test_generate_shift_uses_selected_shift_number(self, mock_compute) -> None:
        mock_compute.return_value = {
            "date": "2026-06-16",
            "shift_number": 3,
            "tier_counts": {},
            "tier_revenues": {},
            "subtotal": 0,
            "ath_subtotal": 0,
        }

        response = self.client.post(
            "/api/revenue/generate-shift/",
            {"date": "2026-06-16", "shift": 3},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shift_number"], 3)
        mock_compute.assert_called_once_with(date(2026, 6, 16), shift_number=3)

    @patch("apps.revenue.services.revenue_engine.compute_shift_for_day")
    def test_generate_shift_updates_existing_ledger_for_same_shift(self, mock_compute) -> None:
        cashier = UserFactory(username="cashier_cuadre_idempotent", role="cashier")
        self.client.force_authenticate(user=cashier)
        mock_compute.return_value = {
            "date": "2026-06-16",
            "shift_number": 2,
            "tier_counts": {
                "1 BGO": 1,
                "2 Y0 Dndein": 1,
                "3 BOO": 0,
                "4 BUYS": 0,
                "9.S0": 0,
            },
            "tier_revenues": {
                "1 BGO": 40.0,
                "2 Y0 Dndein": 45.0,
                "3 BOO": 0.0,
                "4 BUYS": 0.0,
                "9.S0": 0.0,
            },
            "subtotal": 85,
            "ath_subtotal": 85,
        }

        first = self.client.post(
            "/api/revenue/generate-shift/",
            {"date": "2026-06-16", "shift": 2},
            format="json",
        )
        second = self.client.post(
            "/api/revenue/generate-shift/",
            {"date": "2026-06-16", "shift": 2},
            format="json",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["saved_state"], "created")
        self.assertEqual(second.json()["saved_state"], "updated")
        self.assertEqual(first.json()["subtotal"], 85.0)
        self.assertEqual(first.json()["ath_subtotal"], 85.0)
        self.assertEqual(
            ShiftLedger.objects.filter(date=date(2026, 6, 16), shift_number=2).count(),
            1,
        )

        ledger = ShiftLedger.objects.get(date=date(2026, 6, 16), shift_number=2)
        self.assertEqual(ledger.tier_1_bgo_count, 1)
        self.assertEqual(ledger.tier_2_y0_dndein_count, 1)
        self.assertEqual(float(ledger.tier_1_bgo_revenue), 40.0)
        self.assertEqual(float(ledger.tier_2_y0_dndein_revenue), 45.0)
        self.assertEqual(float(ledger.subtotal), 85.0)
        self.assertEqual(float(ledger.ath_subtotal), 85.0)

    def test_daily_summary_endpoint(self) -> None:
        response = self.client.get("/api/ledgers/daily_summary/?date=2026-06-12")
        # Should not crash
        self.assertIn(response.status_code, [200])

    def test_revenue_summary_endpoint_returns_days(self) -> None:
        ShiftLedger.objects.create(
            date=date(2026, 6, 15),
            shift_number=1,
            tier_1_bgo_revenue=Decimal("40.00"),
            barra_amount=Decimal("5.00"),
        )

        response = self.client.get(
            "/api/revenue/summary/?start_date=2026-06-01&end_date=2026-06-30"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["start"], "2026-06-01")
        self.assertEqual(data["end"], "2026-06-30")
        self.assertEqual(len(data["days"]), 1)
        self.assertEqual(data["days"][0]["date"], "2026-06-15")
        self.assertEqual(data["days"][0]["daily_subtotal"], 40.0)
        self.assertEqual(data["days"][0]["daily_total"], 45.0)

    def test_sales_summary_shift_one_uses_previous_day_start(self) -> None:
        Room.objects.update_or_create(
            room_id="room_1",
            defaults={
                "room_number": "1",
                "sensor_id": "sensor_1",
                "price": 60,
            },
        )
        self._sale(
            "room_1",
            datetime(2026, 6, 15, 22, 50),
            datetime(2026, 6, 15, 23, 30),
            Decimal("60.00"),
        )
        self._sale(
            "room_1",
            datetime(2026, 6, 16, 7, 0),
            datetime(2026, 6, 16, 7, 10),
            Decimal("60.00"),
        )

        response = self.client.get(
            "/api/revenue/sales-summary/?view=shift&date=2026-06-16&shift=1"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["rooms_sold"], 1)
        self.assertEqual(data["sales_total"], 60.0)
        self.assertEqual(data["sales"][0]["room_id"], "room_1")

    def test_sales_summary_shift_boundaries_have_no_fractional_second_gaps(self) -> None:
        for index, closed_at in enumerate(
            (
                datetime(2026, 6, 16, 6, 59, 59, 999999),
                datetime(2026, 6, 16, 7, 0, 0),
                datetime(2026, 6, 16, 14, 59, 59, 999999),
                datetime(2026, 6, 16, 15, 0, 0),
                datetime(2026, 6, 16, 22, 59, 59, 999999),
            ),
            start=1,
        ):
            self._sale(
                f"boundary_room_{index}",
                closed_at - timedelta(minutes=30),
                closed_at,
                Decimal("10.00"),
            )

        counts = []
        for shift_number in (1, 2, 3):
            response = self.client.get(
                f"/api/revenue/sales-summary/?view=shift&date=2026-06-16&shift={shift_number}"
            )
            self.assertEqual(response.status_code, 200)
            counts.append(response.json()["rooms_sold"])

        self.assertEqual(counts, [1, 2, 2])
        self.assertEqual(sum(counts), 5)

    def test_sales_summary_day_groups_room_types_by_shift(self) -> None:
        self._sale(
            "room_60",
            datetime(2026, 6, 16, 7, 0),
            datetime(2026, 6, 16, 7, 30),
            Decimal("60.00"),
            room_type_code="STANDARD",
        )
        self._sale(
            "room_100",
            datetime(2026, 6, 16, 15, 0),
            datetime(2026, 6, 16, 15, 30),
            Decimal("100.00"),
            room_type_code="DELUXE",
        )

        response = self.client.get(
            "/api/revenue/sales-summary/?view=day&date=2026-06-16"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["rooms_sold"], 2)
        self.assertEqual(data["sales_total"], 160.0)
        rows = {row["room_type"]: row for row in data["room_types"]}
        self.assertEqual(rows["STANDARD"]["shift_2_count"], 1)
        self.assertEqual(rows["DELUXE"]["shift_3_total"], 100.0)

    def test_sales_summary_week_totals_days(self) -> None:
        self._sale(
            "room_week",
            datetime(2026, 6, 16, 10, 0),
            datetime(2026, 6, 16, 10, 30),
            Decimal("70.00"),
        )

        response = self.client.get(
            "/api/revenue/sales-summary/?view=week&date=2026-06-16"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["week_start"], "2026-06-15")
        self.assertEqual(data["week_end"], "2026-06-21")
        self.assertEqual(data["rooms_sold"], 1)
        self.assertEqual(data["sales_total"], 70.0)

    def _sale(
        self,
        room_id: str,
        check_in: datetime,
        check_out: datetime,
        amount: Decimal,
        room_type_code: str = "",
    ) -> OccupancySession:
        current_tz = timezone.get_current_timezone()
        return OccupancySession.objects.create(
            room_id=room_id,
            check_in=timezone.make_aware(check_in, current_tz),
            check_out=timezone.make_aware(check_out, current_tz),
            room_type_code=room_type_code,
            price_per_night=amount,
            estimated_revenue=amount,
            actual_revenue=amount,
            source=OccupancySession.Source.FRONT_DESK,
            status=OccupancySession.Status.CHECKED_OUT,
        )


class OpenAPIDocsTest(APITestCase):
    """Tests for API documentation."""

    def test_schema_available(self) -> None:
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)

    def test_swagger_ui_available(self) -> None:
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, 200)


class AdminPanelTest(APITestCase):
    """Tests for Django admin interface."""

    def setUp(self) -> None:
        self.admin = UserFactory(is_staff=True, is_superuser=True, password="admin123")

    def test_admin_login_required(self) -> None:
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)


class ModelFieldConstraintsTest(TestCase):
    """Tests for model-level constraints and field validation."""

    def test_shift_ledger_autosave_subtotal(self) -> None:
        ledger = ShiftLedger.objects.create(
            date=date.today(),
            shift_number=1,
            barra_amount=Decimal("50.00"),
        )
        ledger.refresh_from_db()
        self.assertEqual(float(ledger.subtotal), 0.0)  # no tier revenues yet
        self.assertEqual(float(ledger.ath_subtotal), 50.0)

    def test_shift_ledger_unique_constraint(self) -> None:
        ShiftLedger.objects.create(date=date.today(), shift_number=1)
        with self.assertRaises(Exception):
            ShiftLedger.objects.create(date=date.today(), shift_number=1)

    def test_room_amenity_unique_constraint(self) -> None:
        RoomAmenity.objects.create(room_id="test", amenity_id=1)
        with self.assertRaises(Exception):
            RoomAmenity.objects.create(room_id="test", amenity_id=1)


class ReportGenerationViewTest(APITestCase):
    """Tests for broad report generation endpoint permissions."""

    def setUp(self) -> None:
        self.user = UserFactory(role="manager", password="admin123")

    def test_report_endpoint_requires_authentication(self) -> None:
        response = self.client.post("/api/reports/generate/daily_occupancy/", {})
        self.assertEqual(response.status_code, 401)

    @patch("apps.revenue.views.os.path.isfile", return_value=True)
    @patch("apps.revenue.reports.report_generator.generate_exception_report")
    def test_manager_report_endpoint_returns_json_for_path_type(
        self,
        mock_generate,
        mock_isfile,
    ) -> None:
        self.client.force_authenticate(user=self.user)
        mock_generate.return_value = {
            "pdf": "/tmp/2026-06-15_exceptions.pdf",
            "csv": "/tmp/2026-06-15_exceptions.csv",
        }

        response = self.client.post(
            "/api/reports/generate/exceptions/",
            {"date": "2026-06-15"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["report_type"], "exception")
        self.assertEqual(data["files"]["pdf"], "2026-06-15_exceptions.pdf")
        mock_generate.assert_called_once_with(date(2026, 6, 15))
        self.assertEqual(mock_isfile.call_count, 2)

    @patch("apps.revenue.views.os.path.isfile")
    @patch("apps.revenue.reports.report_generator.generate_exception_report")
    def test_manager_report_json_succeeds_when_only_csv_exists(
        self,
        mock_generate,
        mock_isfile,
    ) -> None:
        self.client.force_authenticate(user=self.user)
        mock_generate.return_value = {
            "pdf": "/tmp/2026-06-15_exceptions.pdf",
            "csv": "/tmp/2026-06-15_exceptions.csv",
        }
        mock_isfile.side_effect = lambda path: path.endswith(".csv")

        response = self.client.post(
            "/api/reports/generate/exceptions/",
            {"date": "2026-06-15"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["files"], {"csv": "2026-06-15_exceptions.csv"})
        self.assertEqual(data["missing_files"], ["pdf"])

    def test_cashier_cannot_generate_broad_reports(self) -> None:
        cashier = UserFactory(username="cashier_report_generate", role="cashier")
        self.client.force_authenticate(user=cashier)

        response = self.client.post(
            "/api/reports/generate/daily_sales/",
            {"date": "2026-06-15"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class AuthenticationEndpointTest(APITestCase):
    """Tests for auth endpoints."""

    def test_login_endpoint_exists(self) -> None:
        response = self.client.post("/api/auth/login/", {})
        # May return 400/401 but should not 404
        self.assertNotEqual(response.status_code, 404)

    def test_logout_endpoint_exists(self) -> None:
        response = self.client.get("/api/auth/logout/")
        self.assertNotEqual(response.status_code, 404)
