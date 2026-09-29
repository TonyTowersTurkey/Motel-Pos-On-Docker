import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Camera, CameraSnapshot
from app.schemas import CaptureResult
from app.services.camera_images import normalize_camera_image
from app.services.training_crops import generate_training_crops
from app.services.unifi_protect import UnifiProtectClient

logger = logging.getLogger(__name__)


def sync_unifi_cameras(
    db: Session,
    client: UnifiProtectClient,
) -> list[Camera]:
    """Import new Protect cameras and refresh names/status for existing imports."""
    protect_cameras = client.list_cameras()
    existing = {
        camera.unifi_camera_id: camera
        for camera in db.scalars(select(Camera).where(Camera.unifi_camera_id.is_not(None)))
    }

    synced = []
    for protect_camera in protect_cameras:
        camera = existing.get(protect_camera.id)
        if camera is None:
            camera = Camera(
                name=protect_camera.name,
                unifi_camera_id=protect_camera.id,
                enabled=True,
            )
            db.add(camera)
        else:
            camera.name = protect_camera.name

        camera.last_error = (
            None
            if protect_camera.state == "CONNECTED"
            else f"Protect reports camera state {protect_camera.state}"
        )
        synced.append(camera)

    db.commit()
    for camera in synced:
        db.refresh(camera)
    return synced


def capture_camera(
    db: Session,
    camera: Camera,
    client: UnifiProtectClient,
) -> CaptureResult:
    captured_at = datetime.now(timezone.utc)
    try:
        if not camera.unifi_camera_id:
            raise ValueError("Camera does not have a UniFi Protect camera ID")

        image = normalize_camera_image(client.get_snapshot(camera.unifi_camera_id))
        destination = _snapshot_destination(camera, captured_at)
        _atomic_write(destination, image)
        _write_training_metadata(destination, camera, captured_at)
        image_path = _media_url(destination)

        snapshot = CameraSnapshot(
            camera_id=camera.id,
            image_path=image_path,
            captured_at=captured_at,
        )
        camera.snapshot_image_path = image_path
        camera.last_snapshot_at = captured_at
        camera.last_error = None
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        try:
            generate_training_crops(db, snapshot_ids=[snapshot.id])
        except Exception:
            db.rollback()
            logger.exception("Could not generate training crops for snapshot %s", snapshot.id)
        return CaptureResult(
            camera_id=camera.id,
            camera_name=camera.name,
            success=True,
            image_path=image_path,
            captured_at=captured_at,
        )
    except Exception as exc:
        db.rollback()
        camera.last_error = str(exc)
        db.add(camera)
        db.commit()
        return CaptureResult(
            camera_id=camera.id,
            camera_name=camera.name,
            success=False,
            error=str(exc),
        )


def capture_all_cameras(
    db: Session,
    client: UnifiProtectClient,
) -> list[CaptureResult]:
    cameras = list(
        db.scalars(
            select(Camera)
            .where(Camera.enabled.is_(True), Camera.unifi_camera_id.is_not(None))
            .order_by(Camera.id)
        )
    )
    return [capture_camera(db, camera, client) for camera in cameras]


def capture_automatic_cameras(
    db: Session,
    client: UnifiProtectClient,
) -> list[CaptureResult]:
    cameras = list(
        db.scalars(
            select(Camera)
            .where(
                Camera.enabled.is_(True),
                Camera.automatic_snapshots.is_(True),
                Camera.unifi_camera_id.is_not(None),
            )
            .order_by(Camera.id)
        )
    )
    return [capture_camera(db, camera, client) for camera in cameras]


def _snapshot_destination(camera: Camera, captured_at: datetime) -> Path:
    archive_dir = (
        settings.camera_capture_dir
        / f"camera_{camera.id:04d}"
        / captured_at.strftime("%Y")
        / captured_at.strftime("%m")
        / captured_at.strftime("%d")
    )
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = captured_at.strftime("%Y%m%dT%H%M%S%fZ")
    return archive_dir / f"camera_{camera.id}_{timestamp}.jpg"


def _write_training_metadata(
    image_path: Path,
    camera: Camera,
    captured_at: datetime,
) -> None:
    metadata = {
        "schema_version": 1,
        "image": image_path.name,
        "image_width": 1920,
        "image_height": 1080,
        "captured_at": captured_at.isoformat(),
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "unifi_camera_id": camera.unifi_camera_id,
            "location": camera.location,
        },
        "rooms": [
            {
                "id": room.id,
                "room_id": room.room_id,
                "name": room.name,
                "roi_x": room.roi_x,
                "roi_y": room.roi_y,
                "roi_width": room.roi_width,
                "roi_height": room.roi_height,
                "active": room.active,
            }
            for room in sorted(camera.rooms, key=lambda room: room.id)
        ],
    }
    content = json.dumps(metadata, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    _atomic_write(image_path.with_suffix(".json"), content)


def _atomic_write(destination: Path, content: bytes) -> None:
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_bytes(content)
    temporary.replace(destination)


def _media_url(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(settings.media_root.resolve())
    except ValueError as exc:
        raise ValueError("CAMERA_CAPTURE_DIR must be inside MEDIA_ROOT") from exc
    return f"/media/{relative.as_posix()}"
