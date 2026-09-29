"""Tests for occupancy API view permissions."""

from rest_framework.test import APIClient, APITestCase

from apps.occupancy.models import AuditLog, OccupancyEvent
from apps.users.tests.factories import UserFactory


class LegacyIngestionRemovalTest(APITestCase):
    def test_sensor_ingestion_routes_are_not_registered(self) -> None:
        self.assertEqual(self.client.get("/api/sensors/").status_code, 404)
        self.assertEqual(
            self.client.post(
                "/api/sensors/room_101/simulate/",
                {"distance_mm": 100},
                format="json",
            ).status_code,
            404,
        )


class OccupancyEventViewSetAPITest(APITestCase):
    """Verify cashier event feed access without allowing direct writes."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.cashier = UserFactory(role="cashier", password="cashier123")
        self.manager = UserFactory(role="manager", password="manager123")
        self.event = OccupancyEvent.objects.create(
            room_id="room_101",
            event_type=OccupancyEvent.EventType.ARRIVAL,
            source=OccupancyEvent.Source.SENSOR_AUTO,
        )

    def test_cashier_can_read_occupancy_events_for_recent_activity(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/events/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(results[0]["room_id"], self.event.room_id)

    def test_cashier_can_filter_recent_activity_to_car_events(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        vehicle_event = OccupancyEvent.objects.create(
            room_id="room_102",
            event_type=OccupancyEvent.EventType.VEHICLE_ATTACHED,
            source=OccupancyEvent.Source.MANUAL_INPUT,
            notes="cashier attached vehicle ABC 123 to room.",
        )
        OccupancyEvent.objects.create(
            room_id="room_103",
            event_type=OccupancyEvent.EventType.MAINTENANCE,
            source=OccupancyEvent.Source.MANUAL_INPUT,
        )

        response = self.client.get(
            "/api/events/",
            {
                "event_type": ",".join(
                    [
                        OccupancyEvent.EventType.ARRIVAL,
                        OccupancyEvent.EventType.DEPARTURE,
                        OccupancyEvent.EventType.VEHICLE_ATTACHED,
                        OccupancyEvent.EventType.VEHICLE_CLEARED,
                    ]
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        event_types = {event["event_type"] for event in results}
        self.assertIn(self.event.event_type, event_types)
        self.assertIn(vehicle_event.event_type, event_types)
        self.assertNotIn(OccupancyEvent.EventType.MAINTENANCE, event_types)

    def test_cashier_cannot_create_occupancy_event_directly(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.post(
            "/api/events/",
            {
                "room_id": "room_102",
                "event_type": OccupancyEvent.EventType.MANUAL_OVERRIDE,
                "source": OccupancyEvent.Source.MANUAL_INPUT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_occupancy_event(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            "/api/events/",
            {
                "room_id": "room_102",
                "event_type": OccupancyEvent.EventType.MAINTENANCE,
                "source": OccupancyEvent.Source.MANUAL_INPUT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)


class AuditLogViewSetAPITest(APITestCase):
    """Verify audit log history is manager/admin-only."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.cashier = UserFactory(role="cashier", password="cashier123")
        self.manager = UserFactory(role="manager", password="manager123")
        AuditLog.objects.create(
            user="manager",
            action="updated",
            object_type="Room",
            object_id=101,
        )

    def test_cashier_cannot_read_audit_logs(self) -> None:
        self.client.force_authenticate(user=self.cashier)

        response = self.client.get("/api/audit-log/")

        self.assertEqual(response.status_code, 403)

    def test_manager_can_read_audit_logs(self) -> None:
        self.client.force_authenticate(user=self.manager)

        response = self.client.get("/api/audit-log/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(results[0]["object_type"], "Room")
