"""Tests for room serializers."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.occupancy.models import OccupancyEvent
from apps.revenue.models import OccupancySession
from apps.rooms.models import (
    RentalSession,
    Room,
)
from apps.rooms.serializers import (
    AmenitySerializer,
    MaintenanceLogSerializer,
    PricingTierSerializer,
    RentalSessionSerializer,
    RoomAmenitySerializer,
    RoomSerializer,
)
from apps.rooms.tests.factories import (
    AmenityFactory,
    PricingTierFactory,
    RoomAmenityFactory,
    RoomFactory,
)


class RoomSerializerTest(TestCase):
    """Tests for RoomSerializer."""

    def setUp(self) -> None:
        self.factory = APIRequestFactory()

    def test_room_serializer_roundtrip(self) -> None:
        room = Room.objects.create(
            room_id="room_test1",
            room_number="501",
            sensor_id="s1",
            pricing_tier_code="1 BGO",
            max_occupants=3,
        )
        data = RoomSerializer(room).data
        self.assertEqual(data["room_id"], "room_test1")
        self.assertEqual(data["room_number"], "501")
        self.assertEqual(data["pricing_tier_code"], "1 BGO")

    def test_room_serializer_includes_active_occupancy_session(self) -> None:
        room = Room.objects.create(
            room_id="room_session",
            room_number="502",
            sensor_id="s2",
            pricing_tier_code="1 BGO",
            max_occupants=3,
        )
        session = OccupancySession.objects.create(
            room_id=room.room_id,
            check_in=timezone.now(),
            source=OccupancySession.Source.SENSOR_AUTO,
            status=OccupancySession.Status.ACTIVE,
        )

        data = RoomSerializer(room).data
        self.assertIsNotNone(data["active_occupancy_session"])
        self.assertEqual(data["active_occupancy_session"]["session_id"], session.id)
        self.assertEqual(data["active_occupancy_session"]["room_id"], room.room_id)
        self.assertIn("check_in", data["active_occupancy_session"])

    def test_room_serializer_includes_latest_occupancy_event(self) -> None:
        room = Room.objects.create(
            room_id="room_event",
            room_number="503",
            sensor_id="s3",
            pricing_tier_code="1 BGO",
            max_occupants=3,
        )
        event = OccupancyEvent.objects.create(
            room_id=room.room_id,
            event_type=OccupancyEvent.EventType.ARRIVAL,
            confidence=0.87,
            source=OccupancyEvent.Source.SENSOR_AUTO,
            notes="Car presence confirmed.",
        )

        data = RoomSerializer(room).data
        self.assertIsNotNone(data["latest_occupancy_event"])
        self.assertEqual(data["latest_occupancy_event"]["event_id"], event.event_id)
        self.assertEqual(data["latest_occupancy_event"]["room_id"], room.room_id)
        self.assertEqual(data["latest_occupancy_event"]["event_type"], event.event_type)
        self.assertEqual(data["latest_occupancy_event"]["confidence"], 0.87)

    def test_room_stay_window_uses_earliest_entry_and_rental_duration(self) -> None:
        room = Room.objects.create(room_id="504", room_number="504")
        webhook_entry = timezone.now() - timedelta(hours=1)
        rental_entry = timezone.now()
        OccupancySession.objects.create(
            room_id=room.room_id,
            check_in=webhook_entry,
            source=OccupancySession.Source.ROOM_PULSE,
            status=OccupancySession.Status.ACTIVE,
        )
        RentalSession.objects.create(
            room_id=room.room_id,
            start_time=rental_entry,
            end_time=rental_entry + timedelta(hours=16),
            status=RentalSession.Status.CHECKED_IN,
            source="cashier",
        )

        data = RoomSerializer(room).data

        self.assertEqual(data["entered_at"], webhook_entry.isoformat())
        self.assertEqual(
            data["max_stay_at"],
            (webhook_entry + timedelta(hours=16)).isoformat(),
        )

    def test_room_stay_window_defaults_to_eight_hours_for_manual_rental(self) -> None:
        room = Room.objects.create(room_id="505", room_number="505")
        entered = timezone.now()
        RentalSession.objects.create(
            room_id=room.room_id,
            start_time=entered,
            end_time=entered + timedelta(hours=8),
            status=RentalSession.Status.CHECKED_IN,
            source="cashier",
        )

        data = RoomSerializer(room).data

        self.assertEqual(data["entered_at"], entered.isoformat())
        self.assertEqual(
            data["max_stay_at"], (entered + timedelta(hours=8)).isoformat()
        )

    def test_room_serializer_create_valid(self) -> None:
        data = {
            "room_id": "600",
            "room_number": "600",
            "pricing_tier_code": "Y0 Dndein",
            "max_occupants": 4,
        }
        serializer = RoomSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        room = serializer.save()
        self.assertEqual(room.room_id, "600")

    def test_room_serializer_create_invalid_no_room_id(self) -> None:
        data = {"room_number": "601"}
        serializer = RoomSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("room_id", serializer.errors)

    def test_room_serializer_rejects_duplicate_room_id(self) -> None:
        Room.objects.create(
            room_id="603",
            room_number="603",
            sensor_id="sensor_unique_a",
        )
        serializer = RoomSerializer(
            data={
                "room_id": "603",
                "room_number": "604",
                "sensor_id": "sensor_unique_b",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("room_id", serializer.errors)
        self.assertEqual(
            serializer.errors["room_id"][0],
            "room with this room id already exists.",
        )

    def test_room_serializer_rejects_duplicate_room_number(self) -> None:
        Room.objects.create(
            room_id="605",
            room_number="605",
            sensor_id="sensor_unique_c",
        )
        serializer = RoomSerializer(
            data={
                "room_id": "room_number_target",
                "room_number": "605",
                "sensor_id": "sensor_unique_d",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("room_number", serializer.errors)
        self.assertEqual(
            serializer.errors["room_number"][0],
            "Room number is already assigned to another room.",
        )

    def test_room_serializer_update(self) -> None:
        room = RoomFactory()
        data = {"pricing_tier_code": "4 BUYS", "max_occupants": 6}
        serializer = RoomSerializer(room, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        updated = serializer.save()
        self.assertEqual(updated.pricing_tier_code, "4 BUYS")


class PricingTierSerializerTest(TestCase):
    """Tests for PricingTierSerializer."""

    def test_serializer_roundtrip(self) -> None:
        tier = PricingTierFactory()
        data = PricingTierSerializer(tier).data
        self.assertEqual(data["code"], tier.code)
        self.assertEqual(float(data["price_per_night"]), float(tier.price_per_night))

    def test_create_valid_tier(self) -> None:
        data = {"code": "X9", "price_per_night": "99.99", "description": "Premium"}
        serializer = PricingTierSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        tier = serializer.save()
        self.assertEqual(tier.code, "X9")

    def test_create_invalid_no_code(self) -> None:
        data = {"price_per_night": "50.0"}
        serializer = PricingTierSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)


class AmenitySerializerTest(TestCase):
    """Tests for AmenitySerializer."""

    def test_serializer_roundtrip(self) -> None:
        amenity = AmenityFactory()
        data = AmenitySerializer(amenity).data
        self.assertEqual(data["name"], amenity.name)
        self.assertEqual(data["display_name"], amenity.display_name)


class RoomAmenitySerializerTest(TestCase):
    """Tests for RoomAmenitySerializer."""

    def test_serializer_roundtrip(self) -> None:
        ra = RoomAmenityFactory()
        data = RoomAmenitySerializer(ra).data
        self.assertEqual(data["room_id"], ra.room_id)
        self.assertEqual(data["amenity_id"], ra.amenity_id)


class MaintenanceLogSerializerTest(TestCase):
    """Tests for MaintenanceLogSerializer."""

    def test_serializer_roundtrip(self) -> None:
        from apps.rooms.tests.factories import MaintenanceLogFactory

        maint = MaintenanceLogFactory()
        data = MaintenanceLogSerializer(maint).data
        self.assertEqual(data["room_id"], maint.room_id)


class RentalSessionSerializerTest(TestCase):
    """Tests for RentalSessionSerializer."""

    def test_serializer_roundtrip(self) -> None:
        from apps.rooms.tests.factories import RentalSessionFactory

        session = RentalSessionFactory()
        data = RentalSessionSerializer(session).data
        self.assertIn("exit_time", data)
        self.assertIn(data["rental_type"], {"Single", "Double", "Triple"})
        self.assertEqual(data["room_id"], session.room_id)
