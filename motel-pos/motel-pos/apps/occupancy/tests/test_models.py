"""Comprehensive tests for occupancy models using factory-boy fixtures."""

from datetime import datetime

from django.test import TestCase

from apps.occupancy.models import AuditLog, OccupancyEvent, SensorReading
from apps.occupancy.tests.factories import (
    AuditLogFactory,
    OccupancyEventFactory,
    SensorReadingFactory,
)


class SensorReadingModelTest(TestCase):
    """SensorReading model tests with factory-boy fixtures."""

    def test_create_reading_via_factory(self) -> None:
        reading = SensorReadingFactory()
        self.assertIsInstance(reading, SensorReading)
        self.assertTrue(str(reading).startswith("Reading #"))

    def test_create_minimal_reading(self) -> None:
        reading = SensorReading.objects.create(
            room_id="room_x",
            distance_mm=1500,
        )
        self.assertEqual(reading.presence, "")
        self.assertIsNone(reading.illuminance)
        self.assertIsNotNone(reading.timestamp)

    def test_reading_index_ordering(self) -> None:
        SensorReading.objects.create(
            room_id="room_x", distance_mm=100, timestamp=datetime(2026, 6, 1)
        )
        reading_latest = SensorReading.objects.create(
            room_id="room_x", distance_mm=2000, timestamp=datetime(2026, 6, 12)
        )
        ordered = list(SensorReading.objects.filter(room_id="room_x"))
        self.assertEqual(ordered[0].reading_id, reading_latest.pk)

    def test_reading_field_types(self) -> None:
        reading = SensorReadingFactory()
        self.assertIsInstance(reading.distance_mm, int)
        self.assertIsNotNone(reading.room_id)


class OccupancyEventModelTest(TestCase):
    """OccupancyEvent model tests with factory-boy fixtures."""

    def test_create_event_via_factory(self) -> None:
        event = OccupancyEventFactory()
        self.assertIsInstance(event, OccupancyEvent)
        self.assertTrue(str(event).startswith("Event #"))

    def test_create_minimal_event(self) -> None:
        event = OccupancyEvent.objects.create(
            room_id="room_x",
            event_type="arrival",
        )
        self.assertEqual(event.confidence, 1.0)
        self.assertEqual(event.source, "sensor_auto")

    def test_event_type_choices(self) -> None:
        valid = [s[0] for s in OccupancyEvent.EventType.choices]
        self.assertIn("arrival", valid)
        self.assertIn("departure", valid)
        self.assertIn("check_in", valid)
        self.assertIn("check_out", valid)
        self.assertIn("maintenance", valid)
        self.assertIn("manual_override", valid)

    def test_source_choices(self) -> None:
        valid = [s[0] for s in OccupancyEvent.Source.choices]
        self.assertIn("sensor_auto", valid)
        self.assertIn("manual_input", valid)
        self.assertIn("api_call", valid)


class AuditLogModelTest(TestCase):
    """AuditLog model tests with factory-boy fixtures."""

    def test_create_audit_log_via_factory(self) -> None:
        log = AuditLogFactory()
        self.assertIsInstance(log, AuditLog)
        self.assertTrue(str(log).startswith("Audit #"))

    def test_create_minimal_audit_log(self) -> None:
        log = AuditLog.objects.create(
            user="admin",
            action="test",
            object_type="Room",
        )
        self.assertIsNotNone(log.timestamp)
        self.assertEqual(log.previous_value, "")
        self.assertIsNone(log.object_id)

    def test_audit_log_ordering(self) -> None:
        AuditLog.objects.create(
            user="a",
            action="test1",
            object_type="Room",
            timestamp=datetime(2026, 6, 1),
        )
        log_latest = AuditLog.objects.create(
            user="b",
            action="test2",
            object_type="Room",
            timestamp=datetime(2026, 6, 12),
        )
        ordered = list(AuditLog.objects.all())
        self.assertEqual(ordered[0].pk, log_latest.pk)

    def test_object_type_index(self) -> None:
        AuditLog.objects.create(user="u", action="a", object_type="Room", object_id=1)
        filtered = list(AuditLog.objects.filter(object_type="Room", object_id=1))
        self.assertEqual(len(filtered), 1)
