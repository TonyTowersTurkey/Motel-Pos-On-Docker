"""Unit tests for the pure planned-maintenance scheduler."""

from __future__ import annotations

from datetime import date
import unittest

from apps.maintenance.planner import (
    RoomTarget,
    add_months,
    advance_date,
    build_preview_slots,
    next_due_date,
)


class PlannerTests(unittest.TestCase):
    def test_add_months_clamps_end_of_month(self) -> None:
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_advance_date_supports_all_expected_units(self) -> None:
        self.assertEqual(advance_date(date(2026, 6, 19), 3, "days"), date(2026, 6, 22))
        self.assertEqual(advance_date(date(2026, 6, 19), 2, "weeks"), date(2026, 7, 3))
        self.assertEqual(advance_date(date(2026, 6, 19), 1, "months"), date(2026, 7, 19))
        self.assertEqual(advance_date(date(2026, 6, 19), 1, "years"), date(2027, 6, 19))

    def test_next_due_date_rolls_forward_until_today(self) -> None:
        self.assertEqual(
            next_due_date(
                date(2026, 1, 1),
                frequency_value=3,
                frequency_unit="months",
                today=date(2026, 6, 19),
            ),
            date(2026, 7, 1),
        )

    def test_build_preview_slots_spreads_rooms_across_multiple_days(self) -> None:
        rooms = [
            RoomTarget(room_id=1, room_number="101"),
            RoomTarget(room_id=2, room_number="102"),
            RoomTarget(room_id=3, room_number="103"),
            RoomTarget(room_id=4, room_number="104"),
            RoomTarget(room_id=5, room_number="105"),
        ]

        preview = build_preview_slots(
            rooms,
            date(2026, 7, 4),
            rooms_per_day=2,
            estimated_minutes=20,
        )

        self.assertEqual([slot.due_date for slot in preview], [
            date(2026, 7, 2),
            date(2026, 7, 2),
            date(2026, 7, 3),
            date(2026, 7, 3),
            date(2026, 7, 4),
        ])
        self.assertEqual(preview[0].estimated_minutes, 20)

    def test_build_preview_slots_rejects_invalid_batch_size(self) -> None:
        with self.assertRaises(ValueError):
            build_preview_slots([], date(2026, 7, 4), rooms_per_day=0)
