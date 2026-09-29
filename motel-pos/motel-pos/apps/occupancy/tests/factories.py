"""Factory-boy factories for occupancy-related models."""

from datetime import datetime, timedelta

import factory.django

from apps.occupancy.models import AuditLog, OccupancyEvent, SensorReading


class SensorReadingFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for SensorReading model."""

    class Meta:
        model = SensorReading

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    distance_mm = factory.Faker("random_int", min=0, max=5000)
    presence = "present"
    illuminance = factory.Faker("random_int", min=0, max=100)
    battery_level = factory.LazyAttribute(lambda o: round(o.distance_mm / 50.0, 1))

    timestamp = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(hours=1))


class OccupancyEventFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for OccupancyEvent model."""

    class Meta:
        model = OccupancyEvent

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    event_type = OccupancyEvent.EventType.ARRIVAL
    confidence = 0.95
    source = OccupancyEvent.Source.SENSOR_AUTO
    notes = "Test event"

    timestamp = factory.LazyFunction(lambda: datetime.utcnow() - timedelta(hours=1))


class AuditLogFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for AuditLog model."""

    class Meta:
        model = AuditLog

    user = "admin"
    action = "create"
    object_type = "Room"
    object_id = factory.Sequence(lambda n: n + 100)
    previous_value = "{}"
    new_value = '{"room_id": "room_101"}'
