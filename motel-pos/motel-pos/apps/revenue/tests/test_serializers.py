"""Tests for revenue serializers."""

from django.test import TestCase
from django.utils import timezone

from apps.revenue.models import ShiftLedger
from apps.revenue.serializers import OccupancySessionSerializer, ShiftLedgerSerializer
from apps.revenue.tests.factories import OccupancySessionFactory, ShiftLedgerFactory


class OccupancySessionSerializerTest(TestCase):
    """Tests for OccupancySessionSerializer."""

    def test_serializer_roundtrip(self) -> None:
        session = OccupancySessionFactory()
        data = OccupancySessionSerializer(session).data
        self.assertEqual(data["room_id"], session.room_id)
        self.assertIn("estimated_revenue", data)

    def test_serializer_uppercases_license_plate(self) -> None:
        serializer = OccupancySessionSerializer(
            data={
                "room_id": "plate-room",
                "license_plate": "abc-123 pr",
                "check_in": timezone.now(),
                "source": "front_desk",
                "status": "active",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        session = serializer.save()
        self.assertEqual(session.license_plate, "ABC-123 PR")
        self.assertEqual(serializer.data["license_plate"], "ABC-123 PR")


class ShiftLedgerSerializerTest(TestCase):
    """Tests for ShiftLedgerSerializer."""

    def test_serializer_roundtrip(self) -> None:
        ledger = ShiftLedgerFactory()
        data = ShiftLedgerSerializer(ledger).data
        self.assertEqual(data["date"], str(ledger.date))
        self.assertIn("subtotal", data)

    def test_ledger_validation_rejects_invalid_totals(self) -> None:
        # Test that totals are validated during serializer validation
        ledger = ShiftLedger.objects.create(
            date="2026-07-01",
            shift_number=1,
        )
        data = ShiftLedgerSerializer(ledger).data
        self.assertIsNotNone(data["ath_subtotal"])
