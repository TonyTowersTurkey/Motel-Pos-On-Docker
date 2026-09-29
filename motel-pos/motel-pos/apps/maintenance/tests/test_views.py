"""Tests for planned maintenance template APIs."""

from __future__ import annotations

from datetime import date

from rest_framework.test import APIClient, APITestCase

from apps.maintenance.models import PlannedMaintenanceTemplate
from apps.maintenance.serializers import PlannedMaintenanceTemplateSerializer
from apps.rooms.models import Room, RoomGroup
from apps.users.tests.factories import UserFactory


def make_room(room_id: str, room_number: str, sensor_id: str) -> Room:
    return Room.objects.create(
        room_id=room_id,
        room_number=room_number,
        sensor_id=sensor_id,
    )


class PlannedMaintenanceTemplateAPITests(APITestCase):
    """Verify template CRUD and preview responses."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.manager = UserFactory(role="manager", password="manager123")
        self.client.force_authenticate(user=self.manager)

    def test_template_serializer_persists_room_assignments(self) -> None:
        """Rooms and room groups should round-trip through the serializer."""
        rooms = [
            make_room("room-101", "101", "sensor-101"),
            make_room("room-102", "102", "sensor-102"),
        ]
        room_group = RoomGroup.objects.create(name="North Wing")
        room_group.rooms.add(rooms[0])

        serializer = PlannedMaintenanceTemplateSerializer(
            data={
                "name": "Clean Air Filters",
                "description": "Filter cleaning for guest comfort.",
                "category": "HVAC",
                "default_priority": "normal",
                "frequency_value": 6,
                "frequency_unit": "months",
                "start_date": "2026-01-01",
                "is_active": True,
                "auto_create_work_orders": True,
                "create_days_before_due": 7,
                "estimated_minutes_per_room": 20,
                "all_rooms": False,
                "rooms": [room.pk for room in rooms],
                "room_groups": [room_group.pk],
                "target_building": "",
                "target_floor": "",
                "target_room_type": "",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        template = serializer.save()

        self.assertEqual(template.rooms.count(), 2)
        self.assertEqual(template.room_groups.count(), 1)
        self.assertEqual(template.rooms.order_by("room_number").first().room_number, "101")

    def test_template_list_endpoint_is_wired(self) -> None:
        PlannedMaintenanceTemplate.objects.create(
            name="Clean AC Filters",
            description="Quarterly filter cleaning.",
            category="HVAC",
            default_priority="normal",
            frequency_value=6,
            frequency_unit="months",
            start_date=date(2026, 1, 1),
            is_active=True,
            auto_create_work_orders=True,
            create_days_before_due=7,
            estimated_minutes_per_room=20,
            all_rooms=True,
        )

        response = self.client.get("/api/planned-maintenance-templates/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Clean AC Filters")

    def test_cashier_cannot_list_planned_maintenance_templates(self) -> None:
        cashier = UserFactory(role="cashier", password="cashier123")
        self.client.force_authenticate(user=cashier)

        response = self.client.get("/api/planned-maintenance-templates/")

        self.assertEqual(response.status_code, 403)

    def test_preview_endpoint_returns_spread_slots(self) -> None:
        """The preview endpoint should expose the computed room batches."""
        rooms = [
            make_room("room-201", "101", "sensor-201"),
            make_room("room-202", "102", "sensor-202"),
            make_room("room-203", "103", "sensor-203"),
        ]
        template = PlannedMaintenanceTemplate.objects.create(
            name="Clean Air Filters",
            description="Filter cleaning for guest comfort.",
            category="HVAC",
            default_priority="normal",
            frequency_value=6,
            frequency_unit="months",
            start_date=date(2026, 1, 1),
            is_active=True,
            auto_create_work_orders=True,
            create_days_before_due=7,
            estimated_minutes_per_room=20,
            all_rooms=False,
        )
        template.rooms.set(rooms)

        response = self.client.get(
            f"/api/planned-maintenance-templates/{template.pk}/preview/?rooms_per_day=2&today=2026-06-19"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["template_name"], "Clean Air Filters")
        self.assertEqual(response.data["total_rooms"], 3)
        self.assertEqual(response.data["rooms_per_day"], 2)
        self.assertEqual(
            [slot["due_date"] for slot in response.data["slots"]],
            ["2026-06-30", "2026-06-30", "2026-07-01"],
        )
        self.assertEqual(response.data["estimated_total_minutes"], 60)
