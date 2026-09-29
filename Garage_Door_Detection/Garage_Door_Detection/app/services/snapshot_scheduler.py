import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.services.camera_capture import capture_automatic_cameras
from app.services.runtime_settings import get_unifi_console_id
from app.services.unifi_protect import UnifiProtectClient, UnifiProtectError

logger = logging.getLogger(__name__)


def seconds_until_next_minute(now: datetime | None = None) -> float:
    current = now or datetime.now(timezone.utc)
    next_minute = (current + timedelta(minutes=1)).replace(second=0, microsecond=0)
    return max(0.0, (next_minute - current).total_seconds())


def run_automatic_snapshot_pass() -> None:
    db = SessionLocal()
    try:
        with UnifiProtectClient(console_id=get_unifi_console_id(db)) as client:
            results = capture_automatic_cameras(db, client)
        failures = [result for result in results if not result.success]
        if failures:
            logger.warning(
                "Automatic snapshot pass: %d captured, %d failed",
                len(results) - len(failures),
                len(failures),
            )
    except UnifiProtectError as exc:
        logger.warning("Automatic snapshot pass failed: %s", exc)
    except Exception:
        logger.exception("Unexpected automatic snapshot scheduler error")
    finally:
        db.close()


async def automatic_snapshot_scheduler() -> None:
    while True:
        await asyncio.sleep(seconds_until_next_minute())
        await asyncio.to_thread(run_automatic_snapshot_pass)
