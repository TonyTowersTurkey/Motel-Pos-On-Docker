"""Tests for room views (ViewSets + template views)."""

import calendar
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.guests.models import Vehicle
from apps.occupancy.models import OccupancyEvent
from apps.rooms.models import (
    Amenity,
    MaintenanceLog,
    PricingTier,
    RentalSession,
    Room,
    RoomAmenity,
)
from apps.users.tests.factories import UserFactory


class DashboardViewTest(TestCase):
    """Tests for the rooms dashboard view."""

    def test_root_redirects_to_manager(self) -> None:
        client = Client()
        response = client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/manager/")


class ManagerViewTest(TestCase):
    """Tests for the manager view."""

    def test_get_returns_200(self) -> None:
        client = Client()
        user = UserFactory(username="manager_page", role="manager")
        client.force_login(user)
        response = client.get("/manager/")
        self.assertEqual(response.status_code, 200)

    def test_manager_formats_display_times_in_puerto_rico(self) -> None:
        client = Client()
        user = UserFactory(username="manager_timezone", role="manager")
        client.force_login(user)

        response = client.get("/manager/")

        self.assertContains(response, "window.MOTEL_TIME_ZONE = 'America/Puerto_Rico'")
        self.assertContains(response, 'return motelFormatDateTime(value, true)')
        self.assertNotContains(response, '.toLocaleString(')
        self.assertNotContains(response, '.toLocaleTimeString(')

    def test_admin_get_returns_200(self) -> None:
        client = Client()
        user = UserFactory(username="admin_page", role="admin")
        client.force_login(user)
        response = client.get("/manager/")
        self.assertEqual(response.status_code, 200)

    def test_manager_requires_login(self) -> None:
        client = Client()
        response = client.get("/manager/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/login/"))

    def test_cashier_cannot_open_manager_page(self) -> None:
        client = Client()
        user = UserFactory(username="cashier_manager_page", role="cashier")
        client.force_login(user)
        response = client.get("/manager/")
        self.assertEqual(response.status_code, 403)

    def test_contains_navigation_links(self) -> None:
        client = Client()
        user = UserFactory(username="manager_nav", role="manager")
        client.force_login(user)
        response = client.get("/manager/")
        content = response.content.decode("utf-8")
        self.assertIn("Dashboard View", content)
        self.assertIn("Room Configuration", content)
        self.assertIn("Create New Vehicle", content)
        self.assertIn("vehicleDialog", content)
        self.assertIn('oninput="this.value=this.value.toUpperCase()"', content)
        self.assertIn(".value.trim().toUpperCase()", content)
        self.assertNotIn('id="roomEditorPanel"', content)

    def test_contains_user_review_panel(self) -> None:
        client = Client()
        user = UserFactory(username="manager_users", role="manager")
        client.force_login(user)
        response = client.get("/manager/")
        content = response.content.decode("utf-8")
        self.assertIn('id="usersPanel"', content)
        self.assertIn("function loadUsers()", content)
        self.assertIn("Read-only review of motel accounts", content)
        self.assertNotIn("Create User", content)
        self.assertNotIn("userDialog", content)
        self.assertIn("usersBody", content)

    def test_admin_user_review_panel_contains_create_edit_controls(self) -> None:
        client = Client()
        user = UserFactory(username="admin_users", role="admin", is_staff=True)
        client.force_login(user)
        response = client.get("/manager/")
        content = response.content.decode("utf-8")
        self.assertIn("Admin account management lives here", content)
        self.assertIn("Create User", content)
        self.assertIn("userDialog", content)
        self.assertIn("function openUserDialog", content)
        self.assertIn('id="editUserUsername"', content)

    def test_room_config_get_returns_200(self) -> None:
        client = Client()
        user = UserFactory(username="manager_config", role="manager")
        client.force_login(user)
        response = client.get("/manager/rooms/")
        self.assertEqual(response.status_code, 200)

    def test_manager_session_can_load_room_configuration_apis(self) -> None:
        client = Client()
        user = UserFactory(username="manager_config_session", role="manager")
        client.force_login(user)

        rooms_response = client.get("/api/rooms/")
        pricing_response = client.get("/api/pricing-tiers/")

        self.assertEqual(rooms_response.status_code, 200)
        self.assertEqual(pricing_response.status_code, 200)

    def test_cashier_cannot_open_room_config_page(self) -> None:
        client = Client()
        user = UserFactory(username="cashier_room_config", role="cashier")
        client.force_login(user)
        response = client.get("/manager/rooms/")
        self.assertEqual(response.status_code, 403)

    def test_room_config_contains_editor_fields(self) -> None:
        client = Client()
        user = UserFactory(username="manager_config_fields", role="manager")
        client.force_login(user)
        response = client.get("/manager/rooms/")
        content = response.content.decode("utf-8")
        self.assertIn("Room Configuration", content)
        self.assertIn("cuentaLuma", content)
        self.assertIn("Current Vehicle", content)
        self.assertIn('id="currentVehicleSummary"', content)
        self.assertIn("vehicleSummary(r.current_vehicle)", content)
        self.assertIn('<select id="pricingTier">', content)
        self.assertIn("fetchAllResults('pricing-tiers/')", content)
        self.assertIn("renderPricingTierOptions", content)
        self.assertIn("function apiErrorDetail(payload)", content)
        self.assertIn("function formatApiError(status, text)", content)
        self.assertIn("id=\"roomEditorError\"", content)
        self.assertIn("function setEditorError(message='')", content)
        self.assertIn("if (res.status === 204) return null;", content)
        self.assertIn("credentials: 'same-origin'", content)
        self.assertIn("Do not let a stale JWT", content)
        self.assertNotIn("headers.Authorization = `Bearer ${token()}`", content)
        self.assertIn("if (res.status === 401)", content)
        self.assertIn("does not have room configuration permission", content)


class RoomViewSetAPITest(TestCase):
    """Tests for room API endpoints."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)
        Room.objects.create(
            room_id="room_api_test",
            room_number="101",
            sensor_id="s_test",
            pricing_tier_code="1 BGO",
        )
        self.manager = UserFactory(username="manager_test", role="manager")

    def test_rooms_list(self) -> None:
        response = self.client.get("/api/rooms/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        if isinstance(data, list):
            self.assertGreater(len(data), 0)

    def test_rooms_list_includes_cashier_card_state(self) -> None:
        response = self.client.get("/api/rooms/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        rooms = data["results"] if isinstance(data, dict) else data
        room = next(r for r in rooms if r["room_id"] == "room_api_test")
        self.assertEqual(room["current_state"], "vacant")
        self.assertNotIn("last_seen_reading", room)
        self.assertNotIn("sensor_healthy", room)

    def test_room_api_exposes_manager_edit_fields(self) -> None:
        room = Room.objects.get(room_id="room_api_test")
        room.price = 55
        room.ac = "split"
        room.tv = "smart"
        room.edificio = "A"
        room.cuenta_luma = 7
        room.save()

        response = self.client.get("/api/rooms/room_api_test/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["price"], 55)
        self.assertEqual(data["ac"], "split")
        self.assertEqual(data["tv"], "smart")
        self.assertEqual(data["edificio"], "A")
        self.assertEqual(data["cuenta_luma"], 7)

    def test_cashier_cannot_create_room_configuration(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])

        response = self.client.post(
            "/api/rooms/",
            {
                "room_id": "room_cashier_create",
                "room_number": "C1",
                "sensor_id": "sensor_c1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_room_configuration(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            "/api/rooms/",
            {
                "room_id": "901",
                "room_number": "M1",
                "sensor_id": "sensor_m1",
                "price": 66,
                "ac": "split",
                "tv": "smart",
                "edificio": "C",
                "cuenta_luma": 11,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["price"], 66)
        self.assertEqual(data["cuenta_luma"], 11)

    def test_cashier_cannot_add_room_amenity_configuration(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])
        amenity = Amenity.objects.create(
            name="mini_fridge",
            display_name="Mini Fridge",
        )

        response = self.client.post(
            "/api/rooms/room_api_test/add_amenity/",
            {"amenity_id": amenity.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            RoomAmenity.objects.filter(
                room_id="room_api_test",
                amenity_id=amenity.pk,
            ).exists()
        )

    def test_manager_can_add_room_amenity_configuration(self) -> None:
        self.client.force_authenticate(user=self.manager)
        amenity = Amenity.objects.create(
            name="coffee_maker",
            display_name="Coffee Maker",
        )

        response = self.client.post(
            "/api/rooms/room_api_test/add_amenity/",
            {"amenity_id": amenity.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            RoomAmenity.objects.filter(
                room_id="room_api_test",
                amenity_id=amenity.pk,
            ).exists()
        )

    def test_cashier_cannot_list_room_amenity_configuration(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])
        amenity = Amenity.objects.create(
            name="cashier_blocked_safe",
            display_name="Cashier Blocked Safe",
        )
        RoomAmenity.objects.create(room_id="room_api_test", amenity_id=amenity.pk)

        response = self.client.get("/api/rooms/room_api_test/amenities/")

        self.assertEqual(response.status_code, 403)

    def test_manager_can_list_room_amenity_configuration(self) -> None:
        self.client.force_authenticate(user=self.manager)
        amenity = Amenity.objects.create(
            name="manager_visible_safe",
            display_name="Manager Visible Safe",
        )
        RoomAmenity.objects.create(room_id="room_api_test", amenity_id=amenity.pk)

        response = self.client.get("/api/rooms/room_api_test/amenities/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[0]["amenity_id"], amenity.pk)

    def test_cashier_cannot_read_room_dashboard_summary(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])

        response = self.client.get("/api/rooms/dashboard/")

        self.assertEqual(response.status_code, 403)

    def test_manager_can_read_room_dashboard_summary(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/rooms/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["total_rooms"], 1)

    def test_override_updates_room_state_and_records_event(self) -> None:
        response = self.client.post(
            "/api/rooms/room_api_test/override/",
            {"action": "occupied", "user": "cashier"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["new_state"], "manual_occupied")
        self.assertEqual(data["room"]["current_state"], "manual_occupied")
        self.assertTrue(
            OccupancyEvent.objects.filter(
                room_id="room_api_test",
                event_type=OccupancyEvent.EventType.MANUAL_OVERRIDE,
            ).exists()
        )
        self.assertEqual(
            Room.objects.get(room_id="room_api_test").current_state,
            "manual_occupied",
        )

    def test_override_rejects_unknown_action(self) -> None:
        response = self.client.post(
            "/api/rooms/room_api_test/override/",
            {"action": "closed"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_cashier_can_attach_vehicle_to_room(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])
        vehicle = Vehicle.objects.create(
            make="Toyota",
            model="Corolla",
            color="Blue",
            license_plate="ABC 123",
        )

        response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"vehicle_id": vehicle.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["current_vehicle"]["id"], vehicle.pk)
        self.assertEqual(data["current_vehicle"]["license_plate"], "ABC 123")
        self.assertNotIn("room_context", data["current_vehicle"])
        self.assertEqual(Room.objects.get(room_id="room_api_test").current_vehicle, vehicle)
        event = OccupancyEvent.objects.get(
            room_id="room_api_test",
            event_type=OccupancyEvent.EventType.VEHICLE_ATTACHED,
        )
        self.assertIn("ABC 123", event.notes)

    def test_reattaching_same_vehicle_does_not_duplicate_attachment_event(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])
        vehicle = Vehicle.objects.create(
            make="Toyota",
            model="Corolla",
            color="Blue",
            license_plate="ABC 123",
        )

        first_response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"vehicle_id": vehicle.pk},
            format="json",
        )
        second_response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"vehicle_id": vehicle.pk},
            format="json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            OccupancyEvent.objects.filter(
                room_id="room_api_test",
                event_type=OccupancyEvent.EventType.VEHICLE_ATTACHED,
            ).count(),
            1,
        )
        self.assertEqual(Room.objects.get(room_id="room_api_test").current_vehicle, vehicle)

    def test_attach_vehicle_carries_to_active_rental_session(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])
        vehicle = Vehicle.objects.create(
            make="Honda",
            model="Civic",
            color="Silver",
            license_plate="SESSION 2",
        )
        session = RentalSession.objects.create(
            room_id="room_api_test",
            start_time=timezone.now(),
            status=RentalSession.Status.CHECKED_IN,
            source="front_desk",
        )

        response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"vehicle_id": vehicle.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.vehicle, vehicle)

    def test_clear_room_vehicle_preserves_active_rental_session_vehicle(self) -> None:
        self.user.role = "cashier"
        self.user.save(update_fields=["role"])
        vehicle = Vehicle.objects.create(license_plate="KEEP HIST")
        room = Room.objects.get(room_id="room_api_test")
        room.current_vehicle = vehicle
        room.save(update_fields=["current_vehicle"])
        session = RentalSession.objects.create(
            room_id="room_api_test",
            start_time=timezone.now(),
            status=RentalSession.Status.CHECKED_IN,
            source="front_desk",
            vehicle=vehicle,
        )

        response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"clear": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        room.refresh_from_db()
        session.refresh_from_db()
        self.assertIsNone(room.current_vehicle)
        self.assertEqual(session.vehicle, vehicle)

    def test_cashier_can_clear_room_vehicle(self) -> None:
        vehicle = Vehicle.objects.create(license_plate="CLEAR 1")
        room = Room.objects.get(room_id="room_api_test")
        room.current_vehicle = vehicle
        room.save(update_fields=["current_vehicle"])

        response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"clear": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["current_vehicle"])
        room.refresh_from_db()
        self.assertIsNone(room.current_vehicle)
        event = OccupancyEvent.objects.get(
            room_id="room_api_test",
            event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
        )
        self.assertIn("CLEAR 1", event.notes)

    def test_cashier_can_confirm_departed_vehicle_and_mark_room_dirty(self) -> None:
        cashier = UserFactory(username="cashier_departure", role="cashier")
        self.client.force_authenticate(user=cashier)
        vehicle = Vehicle.objects.create(license_plate="LEFT 101")
        room = Room.objects.get(room_id="room_api_test")
        room.current_state = "vacant"
        room.current_vehicle = vehicle
        room.save(update_fields=["current_state", "current_vehicle"])

        response = self.client.post(
            "/api/rooms/room_api_test/confirm-departure/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        room.refresh_from_db()
        self.assertEqual(room.current_state, "dirty")
        self.assertIsNone(room.current_vehicle)
        event = OccupancyEvent.objects.get(
            room_id="room_api_test",
            event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
        )
        self.assertIn("will not return", event.notes)
        self.assertIn("marked dirty", event.notes)

    def test_departure_confirmation_rejects_non_vacant_room(self) -> None:
        vehicle = Vehicle.objects.create(license_plate="STILL 101")
        room = Room.objects.get(room_id="room_api_test")
        room.current_state = "occupied"
        room.current_vehicle = vehicle
        room.save(update_fields=["current_state", "current_vehicle"])

        response = self.client.post(
            "/api/rooms/room_api_test/confirm-departure/",
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        room.refresh_from_db()
        self.assertEqual(room.current_state, "occupied")
        self.assertEqual(room.current_vehicle, vehicle)


    def test_cashier_vehicle_smoke_create_attach_clear_and_search(self) -> None:
        cashier = UserFactory(username="cashier_vehicle_smoke", role="cashier")
        self.client.force_authenticate(user=cashier)

        create_response = self.client.post(
            "/api/vehicles/",
            {
                "license_plate": "SMOKE 0200",
                "color": "Smoke",
                "make": "Rango",
                "model": "Flow",
                "notes": "Cashier vehicle flow smoke test.",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        vehicle_id = create_response.json()["id"]

        attach_response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"vehicle_id": vehicle_id},
            format="json",
        )

        self.assertEqual(attach_response.status_code, 200)
        self.assertEqual(attach_response.json()["current_vehicle"]["id"], vehicle_id)

        clear_response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"clear": True},
            format="json",
        )

        self.assertEqual(clear_response.status_code, 200)
        self.assertIsNone(clear_response.json()["current_vehicle"])

        search_response = self.client.get("/api/vehicles/?search=SMOKE%200200")

        self.assertEqual(search_response.status_code, 200)
        results = search_response.json().get("results", search_response.json())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], vehicle_id)
        self.assertTrue(
            OccupancyEvent.objects.filter(
                room_id="room_api_test",
                event_type=OccupancyEvent.EventType.VEHICLE_ATTACHED,
            ).exists()
        )
        self.assertTrue(
            OccupancyEvent.objects.filter(
                room_id="room_api_test",
                event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
            ).exists()
        )

    def test_attach_vehicle_rejects_unknown_vehicle(self) -> None:
        response = self.client.post(
            "/api/rooms/room_api_test/vehicle/",
            {"vehicle_id": 999999},
            format="json",
        )

        self.assertEqual(response.status_code, 404)


class MaintenanceLogViewSetAPITest(TestCase):
    """Tests for maintenance-log API role boundaries."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.manager = UserFactory(username="maintenance_manager", role="manager")
        self.cashier = UserFactory(username="maintenance_cashier", role="cashier")
        MaintenanceLog.objects.create(
            room_id="room_maintenance_test",
            category="ac",
            description="Check AC filter",
        )

    def test_manager_can_list_maintenance_logs(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/maintenance/")

        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_maintenance_logs(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/maintenance/")

        self.assertEqual(response.status_code, 403)


class RentalSessionViewSetAPITest(TestCase):
    """Tests for rental-session API role boundaries."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.manager = UserFactory(username="rental_session_manager", role="manager")
        self.cashier = UserFactory(username="rental_session_cashier", role="cashier")
        RentalSession.objects.create(
            room_id="room_rental_test",
            start_time=timezone.now(),
            status=RentalSession.Status.CHECKED_IN,
            source="front_desk",
        )

    def test_manager_can_list_rental_sessions(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/rental-sessions/")

        self.assertEqual(response.status_code, 200)

    def test_manager_can_create_rental_session_with_vehicle(self) -> None:
        self.client.force_authenticate(user=self.manager)
        vehicle = Vehicle.objects.create(
            license_plate="SESSION 1",
            color="Silver",
            make="Honda",
            model="Civic",
        )

        response = self.client.post(
            "/api/rental-sessions/",
            {
                "room_id": "room_rental_test",
                "start_time": timezone.now().isoformat(),
                "status": RentalSession.Status.CHECKED_IN,
                "source": "front_desk",
                "vehicle_id": vehicle.pk,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["vehicle"]["id"], vehicle.pk)
        self.assertEqual(data["vehicle"]["license_plate"], "SESSION 1")
        session = RentalSession.objects.get(session_id=data["session_id"])
        self.assertEqual(session.vehicle, vehicle)

    def test_cashier_can_list_rental_sessions(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/rental-sessions/")

        self.assertEqual(response.status_code, 200)

    def test_all_shifts_filter_uses_full_motel_day_in_entry_order(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        RentalSession.objects.all().delete()
        for room_id, entry_time in (
            ("before_motel_day", datetime(2026, 6, 15, 22, 59)),
            ("shift_1", datetime(2026, 6, 15, 23, 0)),
            ("shift_2", datetime(2026, 6, 16, 10, 0)),
            ("shift_3", datetime(2026, 6, 16, 22, 59)),
            ("after_motel_day", datetime(2026, 6, 16, 23, 0)),
        ):
            RentalSession.objects.create(
                room_id=room_id,
                start_time=timezone.make_aware(entry_time),
                status=RentalSession.Status.CHECKED_IN,
                source="cashier",
            )

        response = self.client.get(
            "/api/rental-sessions/?date=2026-06-16&shift=all&ordering=start_time"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        self.assertEqual(
            [row["room_id"] for row in rows],
            ["shift_1", "shift_2", "shift_3"],
        )

    def test_rental_counts_reconcile_shift_day_week_month_and_year(self) -> None:
        """Every larger motel period must equal its non-overlapping children."""
        self.client.force_authenticate(user=self.cashier)
        RentalSession.objects.all().delete()
        current_tz = timezone.get_current_timezone()
        rentals = []

        # Three rentals per July motel day, one in each shift.
        for day_number in range(1, 32):
            motel_day = date(2026, 7, day_number)
            for shift_number, entry in (
                (1, datetime.combine(motel_day, datetime.min.time())),
                (2, datetime.combine(motel_day, datetime.min.time()).replace(hour=8)),
                (3, datetime.combine(motel_day, datetime.min.time()).replace(hour=16)),
            ):
                rentals.append(
                    RentalSession(
                        room_id=f"july_{day_number}_{shift_number}",
                        start_time=timezone.make_aware(entry, current_tz),
                        status=RentalSession.Status.CHECKED_IN,
                        source="cashier",
                    )
                )

        # Fractional-second boundary records prove no time can fall between shifts.
        boundary_entries = (
            datetime(2026, 7, 16, 23, 0, 0),
            datetime(2026, 7, 17, 6, 59, 59, 999999),
            datetime(2026, 7, 17, 7, 0, 0),
            datetime(2026, 7, 17, 14, 59, 59, 999999),
            datetime(2026, 7, 17, 15, 0, 0),
            datetime(2026, 7, 17, 22, 59, 59, 999999),
        )
        rentals.extend(
            RentalSession(
                room_id=f"boundary_{index}",
                start_time=timezone.make_aware(entry, current_tz),
                status=RentalSession.Status.CHECKED_IN,
                source="cashier",
            )
            for index, entry in enumerate(boundary_entries, start=1)
        )

        # Every other month contributes one record to the annual reconciliation.
        rentals.extend(
            RentalSession(
                room_id=f"month_{month}",
                start_time=timezone.make_aware(datetime(2026, month, 15, 12), current_tz),
                status=RentalSession.Status.CHECKED_IN,
                source="cashier",
            )
            for month in range(1, 13)
            if month != 7
        )
        RentalSession.objects.bulk_create(rentals)

        def api_count(**params: str | int) -> int:
            response = self.client.get("/api/rental-sessions/", params)
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            return payload["count"] if isinstance(payload, dict) else len(payload)

        # Shifts -> motel day.
        shift_counts = [
            api_count(date="2026-07-17", shift=shift_number)
            for shift_number in (1, 2, 3)
        ]
        day_count = api_count(date="2026-07-17", shift="all")
        self.assertEqual(shift_counts, [3, 3, 3])
        self.assertEqual(sum(shift_counts), day_count)
        self.assertEqual(day_count, 9)

        # Motel days -> Monday-through-Sunday week.
        week_start = date(2026, 7, 13)
        week_end = week_start + timedelta(days=6)
        daily_counts = [
            api_count(date=(week_start + timedelta(days=offset)).isoformat(), shift="all")
            for offset in range(7)
        ]
        week_count = api_count(
            start_date=week_start.isoformat(), end_date=week_end.isoformat()
        )
        self.assertEqual(sum(daily_counts), week_count)

        # Calendar weeks clipped at month edges -> month (no overlapping days).
        july_start = date(2026, 7, 1)
        july_end = date(2026, 7, 31)
        clipped_week_counts = []
        cursor = july_start
        while cursor <= july_end:
            segment_end = min(
                cursor + timedelta(days=6 - cursor.weekday()),
                july_end,
            )
            clipped_week_counts.append(
                api_count(start_date=cursor.isoformat(), end_date=segment_end.isoformat())
            )
            cursor = segment_end + timedelta(days=1)
        july_count = api_count(start_date="2026-07-01", end_date="2026-07-31")
        self.assertEqual(sum(clipped_week_counts), july_count)
        self.assertEqual(july_count, 99)

        # Twelve non-overlapping calendar months -> year.
        monthly_counts = []
        for month in range(1, 13):
            last_day = calendar.monthrange(2026, month)[1]
            monthly_counts.append(
                api_count(
                    start_date=date(2026, month, 1).isoformat(),
                    end_date=date(2026, month, last_day).isoformat(),
                )
            )
        year_count = api_count(start_date="2026-01-01", end_date="2026-12-31")
        self.assertEqual(sum(monthly_counts), year_count)
        self.assertEqual(year_count, 110)

    def test_cashier_can_create_default_eight_hour_rental_session(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            "/api/rental-sessions/",
            {
                "room_id": "room_cashier_rental_create",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], RentalSession.Status.CHECKED_IN)
        self.assertEqual(data["source"], "cashier")
        self.assertEqual(data["duration_hours"], 8)

    def test_cashier_can_create_rental_for_occupied_room(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        Room.objects.create(
            room_id="room_occupied_rental",
            room_number="818",
            current_state="occupied",
        )

        response = self.client.post(
            "/api/rental-sessions/",
            {"room_number": "818"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["room_id"], "room_occupied_rental")

    def test_cashier_can_create_double_duration_rental_session(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            "/api/rental-sessions/",
            {
                "room_id": "room_cashier_rental_create",
                "duration_hours": 16,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["duration_hours"], 16)

    def test_cashier_can_create_rental_session_with_room_number_and_entry_time(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        Room.objects.update_or_create(
            room_id="room_dialog_101",
            defaults={"room_number": "909", "sensor_id": "sensor_dialog_101"},
        )
        entry_time = "2026-06-18T10:30:00-04:00"

        response = self.client.post(
            "/api/rental-sessions/",
            {
                "room_number": "909",
                "entry_time": entry_time,
                "duration_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["room_id"], "room_dialog_101")
        self.assertEqual(data["duration_hours"], 24)
        self.assertEqual(data["start_time"], "2026-06-18T10:30:00-04:00")

    def test_cashier_can_set_rental_session_duration_any_time(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        session = RentalSession.objects.create(
            room_id="room_rental_test",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=8),
            status=RentalSession.Status.CHECKED_IN,
            source="cashier",
        )

        response = self.client.post(
            f"/api/rental-sessions/{session.pk}/set-duration/",
            {"duration_hours": 24},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(response.json()["duration_hours"], 24)
        self.assertEqual(session.end_time, session.start_time + timedelta(hours=24))

    def test_cashier_cannot_delete_rental_session(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        session = RentalSession.objects.create(
            room_id="room_rental_test",
            start_time=timezone.now(),
            status=RentalSession.Status.CHECKED_IN,
            source="cashier",
        )

        response = self.client.delete(f"/api/rental-sessions/{session.pk}/")

        self.assertEqual(response.status_code, 403)


class DynamicPricingRuleViewSetAPITest(TestCase):
    """Tests for dynamic-pricing rule API role boundaries."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.manager = UserFactory(username="pricing_rule_manager", role="manager")
        self.cashier = UserFactory(username="pricing_rule_cashier", role="cashier")

    def test_manager_can_list_dynamic_pricing_rules(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/pricing-rules/")

        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_list_dynamic_pricing_rules(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/pricing-rules/")

        self.assertEqual(response.status_code, 403)


class PricingTierAPIUnitTest(TestCase):
    """Tests for pricing tier API unit level."""

    def test_tier_str_format(self) -> None:
        tier = PricingTier.objects.create(
            code="T99", price_per_night=99.99, description="Test"
        )
        self.assertIn("99.99", str(tier))
