"""Comprehensive tests for revenue models using factory-boy fixtures."""

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase

from apps.revenue.models import OccupancySession, ShiftLedger
from apps.revenue.tests.factories import (
    OccupancySessionFactory,
    ShiftLedgerFactory,
)


class OccupancySessionModelTest(TestCase):
    """OccupancySession model tests with factory-boy fixtures."""

    def test_create_session_via_factory(self) -> None:
        session = OccupancySessionFactory()
        self.assertIsInstance(session, OccupancySession)
        self.assertTrue(str(session).startswith("Session #"))

    def test_create_minimal_session(self) -> None:
        session = OccupancySession.objects.create(
            room_id="room_x",
            check_in=datetime.utcnow(),
            source="manual_override",
            status="active",
        )
        self.assertEqual(session.guest_name, "")
        self.assertEqual(float(session.amenities_charges), 0.0)
        self.assertIsNone(session.price_per_night)

    def test_session_status_choices(self) -> None:
        valid = [s[0] for s in OccupancySession.Status.choices]
        self.assertIn("active", valid)
        self.assertIn("checked_out", valid)
        self.assertIn("cancelled", valid)

    def test_session_source_choices(self) -> None:
        valid = [s[0] for s in OccupancySession.Source.choices]
        self.assertIn("sensor_auto", valid)
        self.assertIn("manual_override", valid)
        self.assertIn("front_desk", valid)

    def test_license_plate_is_saved_uppercase(self) -> None:
        session = OccupancySession.objects.create(
            room_id="plate-test",
            license_plate="pr-abc 123",
            check_in=datetime.utcnow(),
            source="front_desk",
            status="active",
        )

        self.assertEqual(session.license_plate, "PR-ABC 123")
        self.assertEqual(
            OccupancySession.objects.get(pk=session.pk).license_plate,
            "PR-ABC 123",
        )

    def test_session_ordering_by_check_in(self) -> None:
        OccupancySession.objects.create(
            room_id="a",
            check_in=datetime(2026, 1, 1),
            source="sensor_auto",
            status="active",
        )
        latest = OccupancySession.objects.create(
            room_id="b",
            check_in=datetime(2026, 6, 1),
            source="sensor_auto",
            status="active",
        )
        ordered = list(OccupancySession.objects.all())
        self.assertEqual(ordered[0].pk, latest.pk)


class ShiftLedgerModelTest(TestCase):
    """ShiftLedger model tests with factory-boy fixtures."""

    def test_create_ledger_via_factory(self) -> None:
        ledger = ShiftLedgerFactory()
        self.assertIsInstance(ledger, ShiftLedger)
        self.assertTrue(str(ledger).startswith("Shift"))

    def test_create_minimal_ledger(self) -> None:
        ledger = ShiftLedger.objects.create(
            date=date.today(),
            shift_number=1,
        )
        # Verify autosave calculates subtotals
        self.assertEqual(float(ledger.subtotal), 0.0)
        self.assertEqual(float(ledger.ath_subtotal), 0.0)

    def test_ledger_save_calculates_totals(self) -> None:
        ledger = ShiftLedger.objects.create(
            date=date.today(),
            shift_number=1,
            tier_1_bgo_revenue=Decimal("80.00"),
            tier_2_y0_dndein_revenue=Decimal("45.00"),
            barra_amount=Decimal("10.00"),
        )
        # Reload from DB to verify save() persisted
        ledger_refreshed = ShiftLedger.objects.get(pk=ledger.pk)
        self.assertEqual(float(ledger_refreshed.subtotal), 125.0)
        self.assertEqual(float(ledger_refreshed.ath_subtotal), 135.0)

    def test_unique_date_shift_constraint(self) -> None:
        ShiftLedger.objects.create(date=date.today(), shift_number=1)
        with self.assertRaises(Exception):
            ShiftLedger.objects.create(date=date.today(), shift_number=1)

    def test_ledger_ordering(self) -> None:
        ShiftLedger.objects.create(date=date(2026, 1, 1), shift_number=1)
        latest = ShiftLedger.objects.create(date=date(2026, 6, 1), shift_number=1)
        ordered = list(ShiftLedger.objects.all())
        self.assertEqual(ordered[0].pk, latest.pk)

    def test_ledger_str(self) -> None:
        ledger = ShiftLedger.objects.create(date=date.today(), shift_number=2)
        self.assertIn("2", str(ledger))
        self.assertIn(str(date.today()), str(ledger))
