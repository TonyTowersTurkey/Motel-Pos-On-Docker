"""Synchronize Protect cameras and capture one image from each enabled camera."""

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.camera_capture import capture_all_cameras, sync_unifi_cameras
from app.services.runtime_settings import get_unifi_console_id
from app.services.unifi_protect import UnifiProtectClient, UnifiProtectError


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        with UnifiProtectClient(console_id=get_unifi_console_id(db)) as client:
            cameras = sync_unifi_cameras(db, client)
            print(f"Synced {len(cameras)} UniFi Protect camera(s).")
            results = capture_all_cameras(db, client)

        for result in results:
            if result.success:
                print(f"Captured {result.camera_name}: {result.image_path}")
            else:
                print(f"Failed {result.camera_name}: {result.error}")
        return 1 if any(not result.success for result in results) else 0
    except UnifiProtectError as exc:
        print(f"UniFi Protect error: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
