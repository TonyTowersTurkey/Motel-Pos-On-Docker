from datetime import datetime, timezone

from app.services.snapshot_scheduler import seconds_until_next_minute


def test_seconds_until_next_minute_aligns_to_minute_boundary() -> None:
    now = datetime(2026, 7, 13, 14, 22, 45, 250000, tzinfo=timezone.utc)
    assert seconds_until_next_minute(now) == 14.75


def test_seconds_until_next_minute_waits_full_minute_at_boundary() -> None:
    now = datetime(2026, 7, 13, 14, 22, 0, tzinfo=timezone.utc)
    assert seconds_until_next_minute(now) == 60
