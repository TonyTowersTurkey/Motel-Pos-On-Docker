"""Tests for transport-independent occupancy operations."""

from datetime import date, datetime, timedelta

from django.test import TransactionTestCase

from apps.occupancy.models import OccupancyEvent
from apps.occupancy.services import OccupancyService
from apps.revenue.models import OccupancySession
from apps.rooms.models import Room


class OccupancyServiceTest(TransactionTestCase):
    def setUp(self) -> None:
        self.service = OccupancyService()
        self.room = Room.objects.create(room_id="room_test", room_number="900")

    def test_manual_occupied_override_updates_room_and_opens_session(self) -> None:
        result = self.service.manual_override(
            room_id=self.room.room_id,
            action="occupied",
            user="admin",
        )

        self.room.refresh_from_db()
        self.assertEqual(result["new_state"], "manual_occupied")
        self.assertEqual(self.room.current_state, "manual_occupied")
        self.assertTrue(
            OccupancySession.objects.filter(
                room_id=self.room.room_id,
                status=OccupancySession.Status.ACTIVE,
            ).exists()
        )
        self.assertTrue(
            OccupancyEvent.objects.filter(
                room_id=self.room.room_id,
                event_type=OccupancyEvent.EventType.MANUAL_OVERRIDE,
            ).exists()
        )

    def test_manual_vacant_override_closes_active_session(self) -> None:
        self.service.manual_override(self.room.room_id, "occupied", "admin")
        self.service.manual_override(self.room.room_id, "vacant", "admin")

        session = OccupancySession.objects.get(room_id=self.room.room_id)
        self.assertEqual(session.status, OccupancySession.Status.CHECKED_OUT)
        self.assertIsNotNone(session.check_out)

    def test_unknown_override_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.service.manual_override(self.room.room_id, "unknown", "admin")


class RevenueEngineServiceTest(TransactionTestCase):
    """Existing revenue integration coverage independent of status ingestion."""

    def setUp(self) -> None:
        Room.objects.create(
            room_id="room_rev_test",
            room_number="700",
            pricing_tier_code="1 BGO",
            active=True,
        )
        from apps.revenue.services import revenue_engine

        self.engine = revenue_engine

    def test_create_occupancy_session(self) -> None:
        result = self.engine.create_occupancy_session(
            room_id="room_rev_test", event_type="occupied"
        )
        self.assertEqual(result["room_id"], "room_rev_test")
        self.assertGreaterEqual(float(result["estimated_revenue"]), 40.0)

    def test_close_occupancy_session(self) -> None:
        opened = self.engine.create_occupancy_session(
            room_id="room_rev_test", event_type="occupied"
        )
        closed = self.engine.close_occupancy_session(opened["session_id"])
        self.assertIsNotNone(closed)

    def test_detect_sessions_for_day(self) -> None:
        self.engine.create_occupancy_session(
            room_id="room_rev_test", event_type="occupied"
        )
        self.assertIsInstance(self.engine.detect_sessions_for_day(date.today()), list)

    def test_compute_shift_for_day(self) -> None:
        self.engine.create_occupancy_session(
            room_id="room_rev_test", event_type="occupied"
        )
        self.assertIsNotNone(self.engine.compute_shift_for_day(date.today(), 1))

    def test_get_revenue_summary(self) -> None:
        today = date.today()
        summary = self.engine.get_revenue_summary(
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=1),
        )
        self.assertIsNotNone(summary)

    def test_format_cuadre_date(self) -> None:
        from apps.revenue.services import format_cuadre_date

        self.assertIn("junio", format_cuadre_date(datetime(2026, 6, 12)).lower())

    def test_format_shift_date(self) -> None:
        from apps.revenue.services import format_shift_date

        self.assertIn("ENERO", format_shift_date(datetime(2026, 1, 5)))
