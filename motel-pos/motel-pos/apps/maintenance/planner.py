"""Pure scheduling helpers for planned maintenance.

This module keeps the date math and batching logic separate from Django so it
can be unit tested without a project settings bootstrap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil


@dataclass(frozen=True)
class RoomTarget:
    """Minimal room data needed to build a PM preview."""

    room_id: str
    room_number: str


@dataclass(frozen=True)
class PreviewSlot:
    """One room scheduled onto one preview day."""

    room_id: str
    room_number: str
    due_date: date
    estimated_minutes: int


def add_months(value: date, months: int) -> date:
    """Return a copy of `value` advanced by `months` calendar months."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(
        value.day,
        [
            31,
            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
            31,
            30,
            31,
            30,
            31,
            31,
            30,
            31,
            30,
            31,
        ][month - 1],
    )
    return date(year, month, day)


def advance_date(value: date, frequency_value: int, frequency_unit: str) -> date:
    """Advance a date by one recurrence interval."""
    if frequency_unit == "days":
        return value + timedelta(days=frequency_value)
    if frequency_unit == "weeks":
        return value + timedelta(weeks=frequency_value)
    if frequency_unit == "months":
        return add_months(value, frequency_value)
    if frequency_unit == "years":
        return add_months(value, frequency_value * 12)
    raise ValueError(f"Unsupported frequency unit: {frequency_unit}")


def next_due_date(
    start_date: date,
    frequency_value: int,
    frequency_unit: str,
    today: date | None = None,
) -> date:
    """Return the first recurrence date on or after `today`."""
    current = start_date
    today = today or date.today()
    while current < today:
        current = advance_date(current, frequency_value, frequency_unit)
    return current


def build_preview_slots(
    rooms: Sequence[RoomTarget],
    cycle_due_date: date,
    *,
    rooms_per_day: int = 15,
    estimated_minutes: int = 20,
) -> list[PreviewSlot]:
    """Spread one cycle across a limited number of rooms per day."""
    if rooms_per_day <= 0:
        raise ValueError("rooms_per_day must be greater than zero")
    if not rooms:
        return []

    batches = ceil(len(rooms) / rooms_per_day)
    start_day = cycle_due_date - timedelta(days=batches - 1)
    preview: list[PreviewSlot] = []

    for index, room in enumerate(rooms):
        day_offset = index // rooms_per_day
        preview.append(
            PreviewSlot(
                room_id=room.room_id,
                room_number=room.room_number,
                due_date=start_day + timedelta(days=day_offset),
                estimated_minutes=estimated_minutes,
            )
        )

    return preview
