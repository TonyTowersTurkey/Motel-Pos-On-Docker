"""Tests for vehicle/customer tracking APIs and manager workspace."""

from django.contrib import admin
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.guests.models import Vehicle, VehicleShape
from apps.rooms.models import RentalSession, Room
from apps.users.tests.factories import UserFactory


class VehicleShapeCatalogTest(TestCase):
    def test_seeded_vehicle_shape_catalog_matches_operational_list(self) -> None:
        self.assertEqual(
            list(
                VehicleShape.objects.order_by("sort_order").values_list(
                    "name", flat=True
                )
            ),
            [
                "Micro",
                "Sedan",
                "Hatchback",
                "Coupe",
                "Station Wagon",
                "Roadster",
                "Cabriolet",
                "Muscle Car",
                "Sport Car",
                "Super Car",
                "Limousine",
                "CUV",
                "Pickup",
                "SUV",
                "Minivan",
                "Van",
                "Campervan",
                "Bus",
                "Monster Truck",
                "Mini Truck",
                "Truck",
                "Big Truck",
            ],
        )


class VehicleManagerPageTest(TestCase):
    def test_manager_can_open_vehicle_workspace(self) -> None:
        manager = UserFactory(username="vehicle_page_manager", role="manager")
        self.client.force_login(manager)

        response = self.client.get("/manager/vehicles/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Manager Workspace")
        self.assertContains(response, "Add Vehicle")
        self.assertContains(response, 'id="vehiclesBody"')
        self.assertContains(response, "async function saveVehicle")
        self.assertContains(response, "Room context")
        self.assertContains(response, 'id="vehicleShape"')
        self.assertContains(
            response,
            'oninput="this.value=this.value.toUpperCase()"',
        )
        self.assertContains(response, ".value.trim().toUpperCase()")
        self.assertContains(response, 'aria-current="page"')

    def test_vehicle_workspace_formats_updated_times_in_puerto_rico(self) -> None:
        manager = UserFactory(username="vehicle_timezone_manager", role="manager")
        self.client.force_login(manager)

        response = self.client.get("/manager/vehicles/")

        self.assertContains(response, "window.MOTEL_TIME_ZONE = 'America/Puerto_Rico'")
        self.assertContains(response, "motelFormat(date, {month:'short'")
        self.assertNotContains(response, '.toLocaleString(')

    def test_cashier_cannot_open_vehicle_workspace(self) -> None:
        cashier = UserFactory(username="vehicle_page_cashier", role="cashier")
        self.client.force_login(cashier)

        self.assertEqual(self.client.get("/manager/vehicles/").status_code, 403)

    def test_vehicle_workspace_requires_login(self) -> None:
        response = self.client.get("/manager/vehicles/")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/login/"))


class VehicleViewSetAPITest(APITestCase):
    """Verify cashier vehicle records can be created and searched safely."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.cashier = UserFactory(role="cashier", password="cashier123")
        self.manager = UserFactory(role="manager", password="manager123")

    def test_cashier_can_create_vehicle_without_guest_identity(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        shape, _ = VehicleShape.objects.get_or_create(
            name="4-door car", defaults={"sort_order": 1}
        )

        response = self.client.post(
            "/api/vehicles/",
            {
                "make": "Toyota",
                "model": "Corolla",
                "color": "Blue",
                "license_plate": "abc 123",
                "vehicle_shape": shape.pk,
                "notes": "Prefers room near exit",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        vehicle = Vehicle.objects.get()
        self.assertEqual(vehicle.make, "Toyota")
        self.assertEqual(vehicle.vehicle_shape, shape)
        self.assertEqual(vehicle.license_plate, "ABC 123")
        self.assertEqual(response.data["license_plate"], "ABC 123")
        self.assertEqual(response.data["vehicle_shape_name"], "4-door car")
        self.assertEqual(vehicle.license_plate_normalized, "ABC123")
        self.assertNotIn("guest_name", response.data)
        self.assertNotIn("phone", response.data)

    def test_duplicate_license_plate_is_rejected_case_insensitively(self) -> None:
        Vehicle.objects.create(license_plate="abc 123", make="Toyota")
        self.assertEqual(Vehicle.objects.get().license_plate, "ABC 123")
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            "/api/vehicles/",
            {"license_plate": "ABC123", "make": "Honda"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"][0]["attr"], "license_plate")
        self.assertEqual(Vehicle.objects.count(), 1)

    def test_cashier_can_search_vehicle_records(self) -> None:
        Vehicle.objects.create(
            make="Hyundai",
            model="Accent",
            color="White",
            license_plate="XYZ 789",
        )
        Vehicle.objects.create(make="Ford", model="Focus", color="Red")
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/vehicles/?search=xyz")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["license_plate"], "XYZ 789")

    def test_cashier_can_search_vehicle_by_normalized_plate(self) -> None:
        Vehicle.objects.create(
            make="Toyota",
            model="Corolla",
            color="Blue",
            license_plate="ABC 123",
        )
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/vehicles/?search=abc-123")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["license_plate"], "ABC 123")

    def test_cashier_can_search_vehicle_by_attached_room_context(self) -> None:
        attached_vehicle = Vehicle.objects.create(
            make="Toyota",
            model="Corolla",
            color="Silver",
            license_plate="ROOM 101",
        )
        other_vehicle = Vehicle.objects.create(make="Ford", model="Focus", color="Red")
        Room.objects.create(
            room_id="vehicle_search_101",
            room_number="101",
            sensor_id="sensor_101",
            current_vehicle=attached_vehicle,
        )
        Room.objects.create(
            room_id="vehicle_search_202",
            room_number="202",
            sensor_id="sensor_202",
            current_vehicle=other_vehicle,
        )
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/vehicles/?search=vehicle_search_101")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["license_plate"], "ROOM 101")
        self.assertEqual(
            results[0]["room_context"]["current_rooms"][0]["room_number"],
            "101",
        )

    def test_cashier_can_search_vehicle_by_rental_session_context(self) -> None:
        session_vehicle = Vehicle.objects.create(
            make="Nissan",
            model="Sentra",
            color="Gray",
            license_plate="HIST 303",
        )
        other_vehicle = Vehicle.objects.create(make="Ford", model="Focus", color="Red")
        Room.objects.create(
            room_id="history_room_303",
            room_number="303",
            sensor_id="sensor_303",
        )
        RentalSession.objects.create(
            room_id="history_room_303",
            start_time=timezone.now(),
            status=RentalSession.Status.CHECKED_IN,
            source="cashier",
            vehicle=session_vehicle,
            notes="Front desk note for room 303.",
        )
        RentalSession.objects.create(
            room_id="history_room_404",
            start_time=timezone.now(),
            status=RentalSession.Status.CHECKED_IN,
            source="cashier",
            vehicle=other_vehicle,
        )
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/vehicles/?search=history_room_303")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["license_plate"], "HIST 303")
        self.assertEqual(
            results[0]["room_context"]["active_rental_sessions"][0]["room_id"],
            "history_room_303",
        )
        self.assertEqual(
            results[0]["room_context"]["active_rental_sessions"][0]["room_number"],
            "303",
        )

    def test_unauthenticated_users_cannot_read_vehicles(self) -> None:
        response = self.client.get("/api/vehicles/")

        self.assertEqual(response.status_code, 401)

    def test_manager_can_read_vehicle_records(self) -> None:
        Vehicle.objects.create(make="Kia", model="Rio", color="Gray")
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/vehicles/")

        self.assertEqual(response.status_code, 200)

    def test_cashier_cannot_update_vehicle_records(self) -> None:
        vehicle = Vehicle.objects.create(
            license_plate="EDIT 123",
            make="Kia",
            color="Blue",
        )
        self.client.force_authenticate(user=self.cashier)

        response = self.client.patch(
            f"/api/vehicles/{vehicle.pk}/",
            {"color": "Black"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.color, "Blue")

    def test_manager_can_update_vehicle_records(self) -> None:
        vehicle = Vehicle.objects.create(
            license_plate="MGR EDIT",
            make="Kia",
            color="Blue",
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.patch(
            f"/api/vehicles/{vehicle.pk}/",
            {"color": "Black"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.color, "Black")

    def test_cashier_lists_only_active_vehicle_shapes(self) -> None:
        VehicleShape.objects.create(name="Three-wheel car", active=True, sort_order=50)
        VehicleShape.objects.create(name="Retired shape", active=False, sort_order=2)
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/vehicle-shapes/")

        self.assertEqual(response.status_code, 200)
        names = [shape["name"] for shape in response.data]
        self.assertIn("Three-wheel car", names)
        self.assertNotIn("Retired shape", names)

    def test_vehicle_shapes_are_read_only_through_api(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            "/api/vehicle-shapes/",
            {"name": "Roadster", "active": True, "sort_order": 12},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

    def test_cashier_cannot_modify_vehicle_shape_list(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            "/api/vehicle-shapes/",
            {"name": "Unauthorized shape"},
            format="json",
        )

        self.assertEqual(response.status_code, 405)

    def test_vehicle_shapes_are_editable_in_django_admin(self) -> None:
        admin_user = UserFactory(
            role="admin", is_staff=True, is_superuser=True, username="shape_admin"
        )
        self.client.force_login(admin_user)

        response = self.client.get("/admin/guests/vehicleshape/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vehicle shapes")
        self.assertContains(response, "Logo")
        self.assertTrue(admin.site.is_registered(VehicleShape))
        model_admin = admin.site.get_model_admin(VehicleShape)
        self.assertEqual(model_admin.list_editable, ["active", "sort_order"])

        vehicle_page = self.client.get("/manager/vehicles/")
        self.assertContains(vehicle_page, "Manage Shapes in Admin")
        self.assertContains(vehicle_page, "/admin/guests/vehicleshape/")

        add_page = self.client.get("/admin/guests/vehicleshape/add/")
        self.assertContains(add_page, 'name="icon"')

    def test_cashier_cannot_delete_vehicle_records(self) -> None:
        vehicle = Vehicle.objects.create(license_plate="DEL 123", make="Kia")
        self.client.force_authenticate(user=self.cashier)

        response = self.client.delete(f"/api/vehicles/{vehicle.pk}/")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Vehicle.objects.filter(pk=vehicle.pk).exists())

    def test_manager_can_delete_vehicle_records(self) -> None:
        vehicle = Vehicle.objects.create(license_plate="MGR 123", make="Kia")
        self.client.force_authenticate(user=self.manager)

        response = self.client.delete(f"/api/vehicles/{vehicle.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Vehicle.objects.filter(pk=vehicle.pk).exists())
