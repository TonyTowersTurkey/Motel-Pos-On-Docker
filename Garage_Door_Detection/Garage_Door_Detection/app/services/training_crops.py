from collections import defaultdict
from pathlib import Path

import cv2
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CameraSnapshot, Room, TrainingCrop
from app.schemas import CropGenerationResult
from app.services.inference import enqueue_crop


def generate_training_crops(
    db: Session,
    *,
    snapshot_ids: list[int] | None = None,
) -> CropGenerationResult:
    """Create one persistent crop for every archived snapshot and valid room ROI."""
    rooms_by_camera: dict[int, list[Room]] = defaultdict(list)
    rooms = db.scalars(
        select(Room)
        .where(
            Room.active.is_(True),
            Room.roi_width > 0,
            Room.roi_height > 0,
        )
        .order_by(Room.camera_id, Room.id)
    )
    for room in rooms:
        rooms_by_camera[room.camera_id].append(room)

    if not rooms_by_camera:
        return CropGenerationResult(
            snapshots_considered=0,
            crops_created=0,
            crops_updated=0,
            crops_skipped=0,
            missing_sources=0,
            failed_sources=0,
            log_entries=[],
        )

    capture_prefix = _media_prefix(settings.camera_capture_dir)
    snapshot_query = (
        select(CameraSnapshot)
        .where(
            CameraSnapshot.camera_id.in_(list(rooms_by_camera)),
            CameraSnapshot.image_path.startswith(capture_prefix),
        )
        .order_by(CameraSnapshot.id)
    )
    if snapshot_ids is not None:
        snapshot_query = snapshot_query.where(CameraSnapshot.id.in_(snapshot_ids))
    snapshots = list(db.scalars(snapshot_query))

    existing: dict[tuple[int, int], TrainingCrop] = {}
    if snapshots:
        existing = {
            (crop.snapshot_id, crop.room_id): crop
            for crop in db.scalars(
                select(TrainingCrop).where(
                    TrainingCrop.snapshot_id.in_([snapshot.id for snapshot in snapshots])
                )
            )
        }

    created = 0
    updated = 0
    skipped = 0
    missing = 0
    failed = 0
    log_entries: list[str] = []
    settings.training_crop_dir.mkdir(parents=True, exist_ok=True)

    for snapshot in snapshots:
        source = _disk_path(snapshot.image_path)
        if not source.is_file():
            missing += 1
            log_entries.append(f"MISSING   {snapshot.image_path}")
            continue
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            failed += 1
            log_entries.append(f"FAILED    {snapshot.image_path} (image could not be decoded)")
            continue

        image_height, image_width = image.shape[:2]
        for room in rooms_by_camera[snapshot.camera_id]:
            coordinates = _clamped_roi(room, image_width, image_height)
            if coordinates is None:
                failed += 1
                log_entries.append(
                    f"FAILED    {snapshot.image_path} (room {room.room_id} ROI is outside image)"
                )
                continue
            x, y, width, height = coordinates
            destination = _crop_destination(snapshot, room, source)
            record = existing.get((snapshot.id, room.id))
            unchanged = (
                record is not None
                and record.roi_x == x
                and record.roi_y == y
                and record.roi_width == width
                and record.roi_height == height
                and destination.is_file()
            )
            if unchanged:
                skipped += 1
                log_entries.append(f"SKIPPED   {_media_url(destination)}")
                continue

            crop_image = image[y : y + height, x : x + width]
            success, encoded = cv2.imencode(
                ".jpg", crop_image, [cv2.IMWRITE_JPEG_QUALITY, 95]
            )
            if not success:
                failed += 1
                log_entries.append(
                    f"FAILED    {snapshot.image_path} (room {room.room_id} crop encoding failed)"
                )
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(destination, encoded.tobytes())
            image_path = _media_url(destination)

            if record is None:
                record = TrainingCrop(
                    snapshot_id=snapshot.id,
                    room_id=room.id,
                    image_path=image_path,
                    roi_x=x,
                    roi_y=y,
                    roi_width=width,
                    roi_height=height,
                )
                db.add(record)
                existing[(snapshot.id, room.id)] = record
                enqueue_crop(db, record)
                created += 1
                log_entries.append(f"GENERATED {image_path}")
            else:
                record.image_path = image_path
                record.roi_x = x
                record.roi_y = y
                record.roi_width = width
                record.roi_height = height
                enqueue_crop(db, record)
                updated += 1
                log_entries.append(f"UPDATED   {image_path}")

    db.commit()
    return CropGenerationResult(
        snapshots_considered=len(snapshots),
        crops_created=created,
        crops_updated=updated,
        crops_skipped=skipped,
        missing_sources=missing,
        failed_sources=failed,
        log_entries=log_entries,
    )


def _clamped_roi(room: Room, image_width: int, image_height: int) -> tuple[int, int, int, int] | None:
    x = min(max(room.roi_x, 0), image_width)
    y = min(max(room.roi_y, 0), image_height)
    right = min(max(room.roi_x + room.roi_width, 0), image_width)
    bottom = min(max(room.roi_y + room.roi_height, 0), image_height)
    if right <= x or bottom <= y:
        return None
    return x, y, right - x, bottom - y


def _crop_destination(snapshot: CameraSnapshot, room: Room, source: Path) -> Path:
    return (
        settings.training_crop_dir
        / f"camera_{snapshot.camera_id:04d}"
        / f"room_{room.room_id:04d}_{room.id:04d}"
        / snapshot.captured_at.strftime("%Y")
        / snapshot.captured_at.strftime("%m")
        / snapshot.captured_at.strftime("%d")
        / f"{source.stem}_room_{room.room_id}.jpg"
    )


def _media_prefix(directory: Path) -> str:
    try:
        relative = directory.resolve().relative_to(settings.media_root.resolve())
    except ValueError as exc:
        raise ValueError("CAMERA_CAPTURE_DIR must be inside MEDIA_ROOT") from exc
    return f"/media/{relative.as_posix().rstrip('/')}/"


def _disk_path(image_path: str) -> Path:
    prefix = "/media/"
    if not image_path.startswith(prefix):
        return Path("/__invalid_media_path__")
    relative = Path(image_path.removeprefix(prefix))
    destination = (settings.media_root / relative).resolve()
    try:
        destination.relative_to(settings.media_root.resolve())
    except ValueError:
        return Path("/__invalid_media_path__")
    return destination


def _media_url(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(settings.media_root.resolve())
    except ValueError as exc:
        raise ValueError("TRAINING_CROP_DIR must be inside MEDIA_ROOT") from exc
    return f"/media/{relative.as_posix()}"


def _atomic_write(destination: Path, content: bytes) -> None:
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_bytes(content)
    temporary.replace(destination)
