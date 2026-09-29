"""Tests for work order API endpoints."""

from __future__ import annotations

from rest_framework.test import APIClient, APITestCase

from apps.rooms.models import Room
from apps.users.tests.factories import UserFactory
from apps.workorders.models import WorkOrder


class WorkOrderAPITests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(role="manager", password="manager123")
        self.client.force_authenticate(user=self.user)
        self.room = Room.objects.create(
            room_id="room-905",
            room_number="905",
            sensor_id="sensor-905",
        )

    def test_create_work_order_persists_to_workorders_table(self) -> None:
        response = self.client.post(
            "/api/work-orders/",
            {
                "room_number": "905",
                "title": "Broken toilet",
                "description": "Base leak and cracked seat.",
                "category": "Plumbing",
                "priority": "high",
                "status": "open",
                "source": "adhoc",
                "assigned_to_name": "Maintenance",
                "due_date": "2026-06-22",
                "estimated_minutes": 45,
                "instructions": "Bring wax ring and supply line.",
                "location_notes": "South hallway, room 905.",
                "safety_notes": "Use wet-floor sign.",
                "checklist": [
                    "Confirm access",
                    "Shut off water",
                    "Replace failed part",
                ],
                "attachments": ["photo_105_before.jpg"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        work_order = WorkOrder.objects.get(pk=response.data["id"])
        self.assertEqual(work_order.room.room_number, "905")
        self.assertEqual(work_order.title, "Broken toilet")
        self.assertEqual(work_order.category, "Plumbing")
        self.assertEqual(work_order.priority, "high")
        self.assertEqual(work_order.source, "adhoc")
        self.assertEqual(work_order.assigned_to_label, "Maintenance")
        self.assertEqual(work_order.estimated_minutes, 45)
        self.assertEqual(work_order.checklist, ["Confirm access", "Shut off water", "Replace failed part"])
        self.assertEqual(work_order.attachments, ["photo_105_before.jpg"])
        self.assertEqual(response.data["room"], "905")
        self.assertEqual(response.data["assigned_to"], "Maintenance")

    def test_list_endpoint_returns_saved_records(self) -> None:
        WorkOrder.objects.create(
            room=self.room,
            title="Smoke detector battery test",
            description="Replace weak battery in room 105.",
            category="Safety",
            priority="normal",
            source="adhoc",
        )

        response = self.client.get("/api/work-orders/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Smoke detector battery test")

    def test_anonymous_user_cannot_list_work_orders(self) -> None:
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/work-orders/")

        self.assertIn(response.status_code, {401, 403})
