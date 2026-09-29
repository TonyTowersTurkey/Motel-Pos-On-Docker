"""Integration tests for the authenticated Room Pulse snapshot receiver."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.core.models import MotelSettings
from apps.guests.models import Vehicle
from apps.occupancy.models import (
    OccupancyEvent,
    RoomPulseDelivery,
    RoomPulseRoomState,
)
from apps.revenue.models import OccupancySession
from apps.rooms.models import RentalSession, Room

TOKEN = "test-room-pulse-token-with-enough-entropy"  # noqa: S105
URL = "/api/webhooks/room-pulse"


def room_payload(room_number: int = 225, state: str = "closed") -> dict:
    """Build one complete room object from the Room Pulse 1.0 contract."""
    observed_at = datetime(2026, 7, 15, 14, 30, tzinfo=UTC).isoformat()
    return {
        "room_record_id": 17,
        "room_number": room_number,
        "room_name": f"Room {room_number}",
        "state": state,
        "confidence": 0.992,
        "state_source": "confirmed",
        "confirmation_streak": 4,
        "state_changed_at": datetime(
            2026, 7, 15, 13, 42, tzinfo=UTC
        ).isoformat(),
        "last_observed_at": observed_at,
        "last_observed_state": state,
        "last_observed_confidence": 0.992,
        "camera_id": 3,
        "camera_name": "Garage North",
        "snapshot_id": 1842,
        "snapshot_captured_at": observed_at,
        "crop_image_path": "/media/training_crops/door.jpg",
        "crop_image_url": "https://garage.example.com/media/door.jpg",
        "model_version": "garage-door-v2",
        "stale": False,
    }


def snapshot(
    *,
    event_id: str | None = None,
    generated_at: datetime | None = None,
    rooms: list[dict] | None = None,
) -> dict:
    """Build one complete Room Pulse snapshot."""
    room_entries = rooms if rooms is not None else [room_payload()]
    return {
        "schema_version": "1.0",
        "event_id": event_id or str(uuid4()),
        "event_type": "room_state_changed",
        "generated_at": (
            generated_at or datetime(2026, 7, 15, 14, 31, tzinfo=UTC)
        ).isoformat(),
        "source": "Garage Door Detection",
        "room_count": len(room_entries),
        "rooms": room_entries,
    }


@override_settings(ROOM_PULSE_WEBHOOK_TOKEN=TOKEN)
class RoomPulseWebhookTest(APITestCase):
    def setUp(self) -> None:
        self.room = Room.objects.create(
            room_id="room_225",
            room_number="225",
            current_state="vacant",
            active=True,
            pricing_tier_code="1 BGO",
        )

    def post_snapshot(
        self,
        payload: dict,
        *,
        token: str = TOKEN,
        header_event_id: str | None = None,
        secure: bool = True,
    ):
        return self.client.post(
            URL,
            payload,
            format="json",
            secure=secure,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_ROOM_PULSE_EVENT=(
                header_event_id
                if header_event_id is not None
                else payload.get("event_id", "")
            ),
        )

    def test_closed_door_marks_room_occupied_and_opens_session(self) -> None:
        payload = snapshot()

        response = self.post_snapshot(payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["accepted"])
        self.assertFalse(response.data["duplicate"])
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "occupied")
        latest = RoomPulseRoomState.objects.get(room=self.room)
        self.assertEqual(latest.state, "closed")
        self.assertFalse(latest.stale)
        self.assertTrue(
            OccupancyEvent.objects.filter(
                room_id=self.room.room_id,
                event_type=OccupancyEvent.EventType.ARRIVAL,
                source=OccupancyEvent.Source.ROOM_PULSE,
            ).exists()
        )
        session = OccupancySession.objects.get(room_id=self.room.room_id)
        self.assertEqual(session.status, OccupancySession.Status.ACTIVE)
        self.assertEqual(session.source, OccupancySession.Source.ROOM_PULSE)
        self.assertFalse(RentalSession.objects.exists())

    def test_audit_mode_creates_and_upgrades_one_sale_then_records_exit(self) -> None:
        settings = MotelSettings.objects.get(pk=1)
        settings.operating_mode = MotelSettings.OperatingMode.AUDIT_MODE
        settings.save(update_fields=["operating_mode"])
        self.room.price = 40
        self.room.save(update_fields=["price"])
        entered_at = datetime(2026, 7, 15, 14, 31, tzinfo=UTC)

        occupied = self.post_snapshot(snapshot(generated_at=entered_at))

        self.assertEqual(occupied.status_code, 200)
        sale = RentalSession.objects.get(room_id=self.room.room_id)
        self.assertEqual(sale.source, "room_pulse_audit")
        self.assertEqual(sale.status, RentalSession.Status.CHECKED_IN)
        self.assertEqual(sale.start_time, entered_at)
        self.assertEqual(sale.end_time, entered_at + timedelta(hours=8))
        self.assertIsNone(sale.exit_time)

        after_nine_hours = entered_at + timedelta(hours=9)
        repeated_closed = self.post_snapshot(snapshot(generated_at=after_nine_hours))

        self.assertEqual(repeated_closed.status_code, 200)
        self.assertEqual(RentalSession.objects.count(), 1)
        sale.refresh_from_db()
        self.assertEqual(sale.end_time, entered_at + timedelta(hours=16))
        self.assertEqual(sale.status, RentalSession.Status.CHECKED_IN)

        after_seventeen_hours = entered_at + timedelta(hours=17)
        departed = self.post_snapshot(
            snapshot(
                generated_at=after_seventeen_hours,
                rooms=[room_payload(state="open")],
            )
        )

        self.assertEqual(departed.status_code, 200)
        self.assertEqual(RentalSession.objects.count(), 1)
        sale.refresh_from_db()
        self.assertEqual(sale.end_time, entered_at + timedelta(hours=24))
        self.assertEqual(sale.exit_time, after_seventeen_hours)
        self.assertEqual(sale.status, RentalSession.Status.CHECKED_OUT)
        occupancy = OccupancySession.objects.get(room_id=self.room.room_id)
        self.assertEqual(occupancy.check_in, entered_at)
        self.assertEqual(occupancy.check_out, after_seventeen_hours)
        self.assertEqual(float(occupancy.actual_revenue), 120.0)

    def test_trailing_slash_alias_is_also_accepted(self) -> None:
        payload = snapshot()

        response = self.client.post(
            f"{URL}/",
            payload,
            format="json",
            secure=True,
            HTTP_AUTHORIZATION=f"Bearer {TOKEN}",
            HTTP_X_ROOM_PULSE_EVENT=payload["event_id"],
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["accepted"])

    def test_open_door_marks_room_vacant_and_closes_session(self) -> None:
        self.post_snapshot(snapshot())
        later = datetime(2026, 7, 15, 14, 40, tzinfo=UTC)
        payload = snapshot(generated_at=later, rooms=[room_payload(state="open")])

        response = self.post_snapshot(payload)

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "vacant")
        session = OccupancySession.objects.get(room_id=self.room.room_id)
        self.assertEqual(session.status, OccupancySession.Status.CHECKED_OUT)
        self.assertTrue(
            OccupancyEvent.objects.filter(
                room_id=self.room.room_id,
                event_type=OccupancyEvent.EventType.DEPARTURE,
            ).exists()
        )

    def test_pos_hands_on_mode_keeps_vehicle_for_cashier_confirmation(self) -> None:
        vehicle = Vehicle.objects.create(license_plate="MANUAL 225")
        self.room.current_vehicle = vehicle
        self.room.save(update_fields=["current_vehicle"])

        response = self.post_snapshot(snapshot(rooms=[room_payload(state="open")]))

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "vacant")
        self.assertEqual(self.room.current_vehicle, vehicle)

    def test_audit_mode_releases_vehicle_and_stays_vacant(self) -> None:
        settings = MotelSettings.objects.get(pk=1)
        settings.operating_mode = MotelSettings.OperatingMode.AUDIT_MODE
        settings.save(update_fields=["operating_mode"])
        vehicle = Vehicle.objects.create(license_plate="AUTO 225")
        self.room.current_state = "dirty"
        self.room.current_vehicle = vehicle
        self.room.save(update_fields=["current_state", "current_vehicle"])

        response = self.post_snapshot(snapshot(rooms=[room_payload(state="open")]))

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "vacant")
        self.assertIsNone(self.room.current_vehicle)
        cleared = OccupancyEvent.objects.get(
            room_id=self.room.room_id,
            event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
        )
        self.assertEqual(cleared.source, OccupancyEvent.Source.ROOM_PULSE)
        self.assertIn("room remains vacant", cleared.notes)

    def test_audit_mode_releases_vehicle_when_room_is_already_vacant(self) -> None:
        settings = MotelSettings.objects.get(pk=1)
        settings.operating_mode = MotelSettings.OperatingMode.AUDIT_MODE
        settings.save(update_fields=["operating_mode"])
        self.room.current_vehicle = Vehicle.objects.create(license_plate="AUTO SAME")
        self.room.save(update_fields=["current_vehicle"])

        response = self.post_snapshot(snapshot(rooms=[room_payload(state="open")]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 1)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "vacant")
        self.assertIsNone(self.room.current_vehicle)

    def test_open_door_does_not_overwrite_confirmed_dirty_state(self) -> None:
        self.room.current_state = "dirty"
        self.room.save(update_fields=["current_state"])
        payload = snapshot(rooms=[room_payload(state="open")])

        response = self.post_snapshot(payload)

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "dirty")
        self.assertFalse(
            OccupancyEvent.objects.filter(
                room_id=self.room.room_id,
                event_type=OccupancyEvent.EventType.DEPARTURE,
            ).exists()
        )

    def test_retry_is_idempotent(self) -> None:
        payload = snapshot()
        first = self.post_snapshot(payload)
        second = self.post_snapshot(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.data["duplicate"])
        self.assertEqual(RoomPulseDelivery.objects.count(), 1)
        self.assertEqual(OccupancyEvent.objects.count(), 1)
        self.assertEqual(OccupancySession.objects.count(), 1)

    def test_older_snapshot_is_recorded_without_overwriting_newer_state(self) -> None:
        newer_at = datetime(2026, 7, 15, 15, 0, tzinfo=UTC)
        older_at = newer_at - timedelta(minutes=10)
        self.post_snapshot(snapshot(generated_at=newer_at))

        response = self.post_snapshot(
            snapshot(generated_at=older_at, rooms=[room_payload(state="open")])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["out_of_order"], 1)
        self.assertEqual(RoomPulseDelivery.objects.count(), 2)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "occupied")
        self.assertEqual(RoomPulseRoomState.objects.get(room=self.room).state, "closed")

    def test_stale_state_becomes_unknown_without_changing_revenue(self) -> None:
        incoming = room_payload(state="closed")
        incoming["stale"] = True
        for nullable_field in (
            "state_changed_at",
            "last_observed_at",
            "last_observed_state",
            "last_observed_confidence",
            "snapshot_id",
            "snapshot_captured_at",
            "crop_image_path",
            "crop_image_url",
            "model_version",
        ):
            incoming[nullable_field] = None

        response = self.post_snapshot(snapshot(rooms=[incoming]))

        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertEqual(self.room.current_state, "unknown")
        self.assertFalse(OccupancyEvent.objects.exists())
        self.assertFalse(OccupancySession.objects.exists())
        latest = RoomPulseRoomState.objects.get(room=self.room)
        self.assertTrue(latest.stale)
        self.assertEqual(latest.crop_image_url, "")

    def test_unmapped_room_is_accepted_and_reported(self) -> None:
        payload = snapshot(rooms=[room_payload(room_number=999)])

        response = self.post_snapshot(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unmapped_room_numbers"], ["999"])
        self.assertEqual(RoomPulseDelivery.objects.count(), 1)

    def test_invalid_or_missing_token_is_rejected(self) -> None:
        payload = snapshot()

        invalid = self.post_snapshot(payload, token="wrong-token")  # noqa: S106
        missing = self.client.post(
            URL,
            payload,
            format="json",
            secure=True,
            HTTP_X_ROOM_PULSE_EVENT=payload["event_id"],
        )

        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(RoomPulseDelivery.objects.count(), 0)

    @override_settings(DEBUG=False, ROOM_PULSE_WEBHOOK_TOKEN="")
    def test_missing_server_token_fails_closed(self) -> None:
        response = self.post_snapshot(snapshot())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(RoomPulseDelivery.objects.count(), 0)

    @override_settings(DEBUG=True, ROOM_PULSE_WEBHOOK_TOKEN="")
    def test_debug_mode_accepts_local_delivery_without_token(self) -> None:
        payload = snapshot()

        response = self.client.post(
            URL,
            payload,
            format="json",
            HTTP_X_ROOM_PULSE_EVENT=payload["event_id"],
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["accepted"])

    @override_settings(DEBUG=False, ROOM_PULSE_REQUIRE_HTTPS=True)
    def test_insecure_production_request_is_rejected(self) -> None:
        response = self.post_snapshot(snapshot(), secure=False)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RoomPulseDelivery.objects.count(), 0)

    def test_header_event_id_must_match_body(self) -> None:
        response = self.post_snapshot(snapshot(), header_event_id=str(uuid4()))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RoomPulseDelivery.objects.count(), 0)

    def test_room_count_and_schema_are_validated(self) -> None:
        bad_count = snapshot()
        bad_count["room_count"] = 2
        unsupported_schema = deepcopy(snapshot())
        unsupported_schema["schema_version"] = "2.0"

        count_response = self.post_snapshot(bad_count)
        schema_response = self.post_snapshot(unsupported_schema)

        self.assertEqual(count_response.status_code, 400)
        self.assertEqual(schema_response.status_code, 400)
        self.assertEqual(RoomPulseDelivery.objects.count(), 0)
