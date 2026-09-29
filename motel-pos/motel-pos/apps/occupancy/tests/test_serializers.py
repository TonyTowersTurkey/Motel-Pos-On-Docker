"""Tests for occupancy serializers."""

from django.test import TestCase

from apps.occupancy.serializers import (
    AuditLogSerializer,
    OccupancyEventSerializer,
)
from apps.occupancy.tests.factories import (
    AuditLogFactory,
    OccupancyEventFactory,
)
from apps.rooms.models import Room


class OccupancyEventSerializerTest(TestCase):
    """Tests for OccupancyEventSerializer."""

    def test_serializer_roundtrip(self) -> None:
        event = OccupancyEventFactory()
        Room.objects.update_or_create(
            room_id=event.room_id,
            defaults={"room_number": "101"},
        )
        data = OccupancyEventSerializer(event).data
        self.assertEqual(data["room_id"], event.room_id)
        self.assertEqual(data["room_number"], "101")
        self.assertEqual(data["event_type"], event.event_type)


class AuditLogSerializerTest(TestCase):
    """Tests for AuditLogSerializer."""

    def test_serializer_roundtrip(self) -> None:
        log = AuditLogFactory()
        data = AuditLogSerializer(log).data
        self.assertEqual(data["user"], log.user)
        self.assertEqual(data["action"], log.action)
