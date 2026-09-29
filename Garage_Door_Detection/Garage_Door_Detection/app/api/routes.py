import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import (
    Camera,
    CameraSnapshot,
    DetectionEvent,
    Room,
    RoomPulseDelivery,
    TrainingCrop,
    TrainingLabelBatch,
)
from app.schemas import (
    CaptureResult,
    BatchApprovalPreview,
    BatchApprovalRequest,
    BatchApprovalResult,
    BatchUndoResult,
    CameraRead,
    CameraSnapshotCreate,
    CameraSnapshotRead,
    CameraUpdate,
    CropGenerationResult,
    DashboardRoomRead,
    DatasetExportPreview,
    DatasetExportRequest,
    DatasetExportResult,
    RoomCreate,
    RoomRead,
    RoomPulseConfigRead,
    RoomPulseConfigUpdate,
    RoomPulseDeliveryRead,
    RoomPulseTestResult,
    RoomUpdate,
    TrainingCropLabelRead,
    TrainingCropLabelUpdate,
    TrainingCropLabelsClear,
    TrainingCropLabelsClearRead,
    TrainingCropList,
    TrainingCropRead,
    TrainingCropRunLabelRead,
    TrainingCropRunLabelUpdate,
    TrainingLabelProgress,
    UnlabeledRoomOption,
    UnifiCameraRead,
    UnifiConfigRead,
    UnifiConfigUpdate,
)
from app.services.camera_capture import capture_all_cameras, capture_camera, sync_unifi_cameras
from app.services.camera_images import normalize_camera_image
from app.services.dataset_export import (
    DatasetExportError,
    export_classification_dataset,
    preview_classification_dataset,
)
from app.services.runtime_settings import (
    UNIFI_CONSOLE_ID_KEY,
    get_unifi_console_id,
    set_runtime_setting,
)
from app.services.room_pulse import get_room_pulse_config, send_room_pulse
from app.services.training_crops import generate_training_crops
from app.services.unifi_protect import UnifiProtectClient, UnifiProtectError

router = APIRouter(prefix="/api")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _protect_client(db: Session) -> UnifiProtectClient:
    return UnifiProtectClient(console_id=get_unifi_console_id(db))


@router.get("/health")
def api_health() -> dict[str, str]:
    return {"status": "ok"}


def _room_pulse_config_read(config) -> RoomPulseConfigRead:
    return RoomPulseConfigRead(
        enabled=config.enabled,
        endpoint_url=config.endpoint_url,
        public_base_url=config.public_base_url,
        interval_seconds=config.interval_seconds,
        send_on_change=config.send_on_change,
        include_image_url=config.include_image_url,
        token_configured=bool(config.bearer_token),
        timeout_seconds=config.timeout_seconds,
        last_sent_at=config.last_sent_at,
        last_error=config.last_error,
    )


def _validate_http_url(value: str | None, field: str) -> str | None:
    normalized = value.strip() if value else None
    if not normalized:
        return None
    url = httpx.URL(normalized)
    if url.scheme not in ("http", "https") or not url.host:
        raise HTTPException(status_code=422, detail=f"{field} must be an HTTP or HTTPS URL")
    return normalized.rstrip("/")


@router.get("/room-pulse/config", response_model=RoomPulseConfigRead)
def read_room_pulse_config(db: Session = Depends(get_db)) -> RoomPulseConfigRead:
    return _room_pulse_config_read(get_room_pulse_config(db))


@router.put("/room-pulse/config", response_model=RoomPulseConfigRead)
def update_room_pulse_config(
    payload: RoomPulseConfigUpdate,
    db: Session = Depends(get_db),
) -> RoomPulseConfigRead:
    endpoint_url = _validate_http_url(payload.endpoint_url, "Endpoint URL")
    public_base_url = _validate_http_url(payload.public_base_url, "Public app URL")
    if payload.enabled and endpoint_url is None:
        raise HTTPException(status_code=422, detail="Endpoint URL is required when enabled")
    config = get_room_pulse_config(db)
    config.enabled = payload.enabled
    config.endpoint_url = endpoint_url
    config.public_base_url = public_base_url
    config.interval_seconds = payload.interval_seconds
    config.send_on_change = payload.send_on_change
    config.include_image_url = payload.include_image_url
    config.timeout_seconds = payload.timeout_seconds
    if payload.clear_bearer_token:
        config.bearer_token = None
    elif payload.bearer_token:
        config.bearer_token = payload.bearer_token.strip()
    db.commit()
    db.refresh(config)
    return _room_pulse_config_read(config)


@router.get("/room-pulse/deliveries", response_model=list[RoomPulseDeliveryRead])
def list_room_pulse_deliveries(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[RoomPulseDelivery]:
    limit = min(max(limit, 1), 200)
    return list(
        db.scalars(select(RoomPulseDelivery).order_by(RoomPulseDelivery.id.desc()).limit(limit))
    )


@router.post("/room-pulse/test", response_model=RoomPulseTestResult)
def test_room_pulse(db: Session = Depends(get_db)) -> RoomPulseTestResult:
    try:
        delivery = send_room_pulse(db, "test")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RoomPulseTestResult(delivery=RoomPulseDeliveryRead.model_validate(delivery))


@router.get("/unifi/config", response_model=UnifiConfigRead)
def get_unifi_config(db: Session = Depends(get_db)) -> UnifiConfigRead:
    api_key = settings.unifi_api_key
    local_api_key = settings.unifi_local_api_key
    return UnifiConfigRead(
        connection_mode=settings.unifi_connection_mode,
        console_id=get_unifi_console_id(db) or settings.unifi_console_id,
        api_key_configured=bool(api_key and api_key.get_secret_value()),
        local_base_url=settings.unifi_local_base_url,
        local_api_key_configured=bool(local_api_key and local_api_key.get_secret_value()),
    )


@router.put("/unifi/config", response_model=UnifiConfigRead)
def update_unifi_config(
    payload: UnifiConfigUpdate,
    db: Session = Depends(get_db),
) -> UnifiConfigRead:
    set_runtime_setting(db, UNIFI_CONSOLE_ID_KEY, payload.console_id)
    return get_unifi_config(db)


@router.get("/unifi/cameras", response_model=list[UnifiCameraRead])
def list_unifi_cameras(db: Session = Depends(get_db)) -> list[UnifiCameraRead]:
    try:
        with _protect_client(db) as client:
            return [UnifiCameraRead(**camera.__dict__) for camera in client.list_cameras()]
    except UnifiProtectError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/unifi/sync", response_model=list[CameraRead])
def sync_cameras_from_unifi(db: Session = Depends(get_db)) -> list[Camera]:
    try:
        with _protect_client(db) as client:
            return sync_unifi_cameras(db, client)
    except UnifiProtectError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/captures/run", response_model=list[CaptureResult])
def capture_all(db: Session = Depends(get_db)) -> list[CaptureResult]:
    with _protect_client(db) as client:
        return capture_all_cameras(db, client)


@router.post("/cameras/{camera_id}/capture", response_model=CaptureResult)
def capture_one(camera_id: int, db: Session = Depends(get_db)) -> CaptureResult:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    with _protect_client(db) as client:
        return capture_camera(db, camera, client)


@router.get("/cameras/", response_model=list[CameraRead])
def list_cameras(db: Session = Depends(get_db)) -> list[Camera]:
    return list(db.scalars(select(Camera).order_by(Camera.id)))


@router.get("/cameras/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: int, db: Session = Depends(get_db)) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.patch("/cameras/{camera_id}", response_model=CameraRead)
def update_camera(camera_id: int, payload: CameraUpdate, db: Session = Depends(get_db)) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)
    return camera


@router.post("/cameras/{camera_id}/snapshot-image", response_model=CameraRead)
def upload_camera_snapshot_image(
    camera_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Camera:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    if (image.content_type or "") not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG, or WebP image")

    settings.camera_snapshot_dir.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc)
    filename = (
        f"camera_{camera.id}_view_{captured_at.strftime('%Y%m%dT%H%M%S%fZ')}.jpg"
    )
    destination = settings.camera_snapshot_dir / filename

    try:
        normalized_image = normalize_camera_image(image.file.read())
        destination.write_bytes(normalized_image)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        image.file.close()

    media_path = Path(settings.camera_snapshot_dir.name) / filename
    image_path = f"/media/{media_path.as_posix()}"
    snapshot = CameraSnapshot(camera_id=camera.id, image_path=image_path, captured_at=captured_at)
    camera.snapshot_image_path = image_path
    camera.last_snapshot_at = captured_at
    camera.last_error = None
    db.add(snapshot)
    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    db.delete(camera)
    db.commit()
    return {"deleted": True}


@router.post("/rooms/", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)) -> Room:
    if db.get(Camera, payload.camera_id) is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    room = Room(**payload.model_dump())
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.get("/rooms/", response_model=list[RoomRead])
def list_rooms(camera_id: int | None = None, db: Session = Depends(get_db)) -> list[Room]:
    query = select(Room).order_by(Room.room_id, Room.id)
    if camera_id is not None:
        query = query.where(Room.camera_id == camera_id)
    return list(db.scalars(query))


@router.get("/dashboard/rooms", response_model=list[DashboardRoomRead])
def list_dashboard_rooms(db: Session = Depends(get_db)) -> list[DashboardRoomRead]:
    latest_crop_path = (
        select(TrainingCrop.image_path)
        .join(CameraSnapshot, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .where(TrainingCrop.room_id == Room.id)
        .order_by(CameraSnapshot.captured_at.desc(), TrainingCrop.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Room, latest_crop_path.label("latest_crop_image_path")).order_by(
            Room.room_id, Room.id
        )
    )
    return [
        DashboardRoomRead(
            id=room.id,
            room_number=room.room_id,
            current_state=room.current_state,
            current_confidence=room.current_confidence,
            last_detected_state=room.last_detected_state,
            last_detected_confidence=room.last_detected_confidence,
            last_detection_at=room.last_detection_at,
            latest_crop_image_path=image_path,
        )
        for room, image_path in rows
    ]


@router.get("/rooms/{room_pk}", response_model=RoomRead)
def get_room(room_pk: int, db: Session = Depends(get_db)) -> Room:
    room = db.get(Room, room_pk)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.patch("/rooms/{room_pk}", response_model=RoomRead)
def update_room(room_pk: int, payload: RoomUpdate, db: Session = Depends(get_db)) -> Room:
    room = db.get(Room, room_pk)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(room, field, value)

    db.commit()
    db.refresh(room)
    return room


@router.delete("/rooms/{room_pk}")
def delete_room(room_pk: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    room = db.get(Room, room_pk)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    db.delete(room)
    db.commit()
    return {"deleted": True}


@router.post(
    "/camera-snapshots/",
    response_model=CameraSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
def create_camera_snapshot(
    payload: CameraSnapshotCreate,
    db: Session = Depends(get_db),
) -> CameraSnapshot:
    camera = db.get(Camera, payload.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    snapshot = CameraSnapshot(**payload.model_dump())
    camera.snapshot_image_path = payload.image_path
    camera.last_snapshot_at = payload.captured_at
    camera.last_error = None
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/camera-snapshots/", response_model=list[CameraSnapshotRead])
def list_camera_snapshots(
    camera_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[CameraSnapshot]:
    limit = min(max(limit, 1), 200)
    query = select(CameraSnapshot).order_by(CameraSnapshot.captured_at.desc()).limit(limit)
    if camera_id is not None:
        query = query.where(CameraSnapshot.camera_id == camera_id)
    return list(db.scalars(query))


@router.post("/training/crops/generate", response_model=CropGenerationResult)
def generate_crops(db: Session = Depends(get_db)) -> CropGenerationResult:
    return generate_training_crops(db)


@router.get("/training/crops/unlabeled", response_model=TrainingCropList)
def list_unlabeled_training_crops(
    limit: int = 48,
    offset: int = 0,
    room_number: int | None = None,
    preliminary_label: Literal["open", "closed"] | None = None,
    door_label: Literal["missing", "open", "closed", "partial", "unsure", "bad"]
    | None = None,
    vehicle_label: Literal[
        "missing", "present", "absent", "not_observable", "unsure"
    ]
    | None = None,
    db: Session = Depends(get_db),
) -> TrainingCropList:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    review_conditions = []
    if door_label == "missing":
        review_conditions.append(TrainingCrop.label.is_(None))
    elif door_label is not None:
        review_conditions.append(TrainingCrop.label == door_label)
    if vehicle_label == "missing":
        review_conditions.append(TrainingCrop.vehicle_label.is_(None))
        review_conditions.append(or_(TrainingCrop.label.is_(None), TrainingCrop.label != "bad"))
    elif vehicle_label is not None:
        review_conditions.append(TrainingCrop.vehicle_label == vehicle_label)
    if not review_conditions:
        review_conditions.append(_crop_needs_review())
    latest_preliminary_label = (
        select(DetectionEvent.predicted_state)
        .where(DetectionEvent.training_crop_id == TrainingCrop.id)
        .order_by(DetectionEvent.id.desc())
        .limit(1)
        .correlate(TrainingCrop)
        .scalar_subquery()
    )
    latest_preliminary_confidence = (
        select(DetectionEvent.confidence)
        .where(DetectionEvent.training_crop_id == TrainingCrop.id)
        .order_by(DetectionEvent.id.desc())
        .limit(1)
        .correlate(TrainingCrop)
        .scalar_subquery()
    )
    count_query = (
        select(func.count())
        .select_from(TrainingCrop)
        .join(Room, TrainingCrop.room_id == Room.id)
        .where(*review_conditions)
    )
    crop_query = (
        select(
            TrainingCrop,
            CameraSnapshot,
            Camera,
            Room,
            latest_preliminary_label.label("preliminary_label"),
            latest_preliminary_confidence.label("preliminary_confidence"),
        )
        .join(CameraSnapshot, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .join(Camera, CameraSnapshot.camera_id == Camera.id)
        .join(Room, TrainingCrop.room_id == Room.id)
        .where(*review_conditions)
        .order_by(CameraSnapshot.captured_at, TrainingCrop.id)
    )
    if room_number is not None:
        count_query = count_query.where(Room.room_id == room_number)
        crop_query = crop_query.where(Room.room_id == room_number)
    if preliminary_label is not None:
        count_query = count_query.where(latest_preliminary_label == preliminary_label)
        crop_query = crop_query.where(latest_preliminary_label == preliminary_label)
    total = db.scalar(count_query) or 0
    rows = db.execute(crop_query.offset(offset).limit(limit))
    return TrainingCropList(
        total=total,
        items=[
            TrainingCropRead(
                id=crop.id,
                image_path=crop.image_path,
                camera_id=camera.id,
                camera_name=camera.name,
                room_id=room.id,
                room_number=room.room_id,
                room_name=room.name,
                captured_at=snapshot.captured_at,
                preliminary_label=preliminary_label,
                preliminary_confidence=preliminary_confidence,
                door_label=crop.label,
                vehicle_label=crop.vehicle_label,
            )
            for crop, snapshot, camera, room, preliminary_label, preliminary_confidence in rows
        ],
    )


@router.get("/training/crops/unlabeled/rooms", response_model=list[UnlabeledRoomOption])
def list_unlabeled_room_options(
    db: Session = Depends(get_db),
) -> list[UnlabeledRoomOption]:
    rows = db.execute(
        select(Room.room_id, func.min(Room.name), func.count(TrainingCrop.id))
        .join(TrainingCrop, TrainingCrop.room_id == Room.id)
        .where(_crop_needs_review())
        .group_by(Room.room_id)
        .order_by(Room.room_id)
    )
    return [
        UnlabeledRoomOption(room_number=room_number, room_name=room_name, count=count)
        for room_number, room_name, count in rows
    ]


def _crop_needs_review():
    return or_(
        TrainingCrop.label.is_(None),
        and_(TrainingCrop.label != "bad", TrainingCrop.vehicle_label.is_(None)),
    )


def _apply_door_label(
    crop: TrainingCrop,
    label: str,
    *,
    source: str,
    labeled_at: datetime,
    batch_id: int | None = None,
    confidence: float | None = None,
) -> None:
    had_derived_vehicle_label = crop.vehicle_label_source == "door_closed_rule"
    crop.label = label
    crop.label_source = source
    crop.label_batch_id = batch_id
    crop.label_confidence = confidence
    crop.labeled_at = labeled_at
    if label == "closed":
        crop.vehicle_label = "not_observable"
        crop.vehicle_label_source = "door_closed_rule"
        crop.vehicle_labeled_at = labeled_at
    elif label == "bad" or had_derived_vehicle_label:
        crop.vehicle_label = None
        crop.vehicle_label_source = None
        crop.vehicle_labeled_at = None


def _clear_door_label(crop: TrainingCrop) -> None:
    if crop.vehicle_label_source == "door_closed_rule":
        crop.vehicle_label = None
        crop.vehicle_label_source = None
        crop.vehicle_labeled_at = None
    crop.label = None
    crop.label_source = None
    crop.label_batch_id = None
    crop.label_confidence = None
    crop.labeled_at = None


@router.get("/training/crops/label-progress", response_model=TrainingLabelProgress)
def read_training_label_progress(
    db: Session = Depends(get_db),
) -> TrainingLabelProgress:
    total, door_labeled, vehicle_labeled, fully_labeled = db.execute(
        select(
            func.count(TrainingCrop.id),
            func.count(TrainingCrop.label),
            func.count(TrainingCrop.vehicle_label),
            func.coalesce(
                func.sum(
                    case(
                        (
                            or_(
                                TrainingCrop.label == "bad",
                                and_(
                                    TrainingCrop.label.is_not(None),
                                    TrainingCrop.vehicle_label.is_not(None),
                                ),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        )
    ).one()
    door_counts = {
        label: 0 for label in ("open", "closed", "partial", "unsure", "bad")
    }
    vehicle_counts = {
        label: 0 for label in ("present", "absent", "not_observable", "unsure")
    }
    door_counts.update(
        db.execute(
            select(TrainingCrop.label, func.count())
            .where(TrainingCrop.label.in_(door_counts))
            .group_by(TrainingCrop.label)
        ).all()
    )
    vehicle_counts.update(
        db.execute(
            select(TrainingCrop.vehicle_label, func.count())
            .where(TrainingCrop.vehicle_label.in_(vehicle_counts))
            .group_by(TrainingCrop.vehicle_label)
        ).all()
    )
    return TrainingLabelProgress(
        total=total,
        door_labeled=door_labeled,
        vehicle_labeled=vehicle_labeled,
        fully_labeled=fully_labeled,
        needs_review=total - fully_labeled,
        door_counts=door_counts,
        vehicle_counts=vehicle_counts,
    )


@router.patch("/training/crops/{crop_id}/label", response_model=TrainingCropLabelRead)
def label_training_crop(
    crop_id: int,
    payload: TrainingCropLabelUpdate,
    db: Session = Depends(get_db),
) -> TrainingCropLabelRead:
    crop = db.get(TrainingCrop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="Training crop not found")
    now = datetime.now(timezone.utc)
    if payload.label is not None:
        _apply_door_label(crop, payload.label, source="manual", labeled_at=now)
    else:
        if crop.label == "bad":
            raise HTTPException(status_code=409, detail="Bad crops do not need a vehicle label")
        crop.vehicle_label = payload.vehicle_label
        crop.vehicle_label_source = "manual"
        crop.vehicle_labeled_at = now
    db.commit()
    return TrainingCropLabelRead(
        id=crop.id,
        label=crop.label,
        vehicle_label=crop.vehicle_label,
    )


@router.patch("/training/crops/label-run", response_model=TrainingCropRunLabelRead)
def label_training_crop_run(
    payload: TrainingCropRunLabelUpdate,
    db: Session = Depends(get_db),
) -> TrainingCropRunLabelRead:
    start_crop = db.get(TrainingCrop, payload.start_crop_id)
    if start_crop is None:
        raise HTTPException(status_code=404, detail="Starting training crop not found")
    is_vehicle_run = payload.vehicle_label is not None
    if is_vehicle_run and start_crop.label == "bad":
        raise HTTPException(status_code=409, detail="Bad crops do not need a vehicle label")
    current_value = start_crop.vehicle_label if is_vehicle_run else start_crop.label
    if current_value is not None:
        raise HTTPException(status_code=409, detail="Starting training crop is already labeled")
    start_snapshot = db.get(CameraSnapshot, start_crop.snapshot_id)
    crop_query = (
        select(TrainingCrop)
        .join(CameraSnapshot, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .where(
            TrainingCrop.room_id == start_crop.room_id,
            (
                TrainingCrop.vehicle_label.is_(None)
                if is_vehicle_run
                else TrainingCrop.label.is_(None)
            ),
            or_(
                CameraSnapshot.captured_at > start_snapshot.captured_at,
                and_(
                    CameraSnapshot.captured_at == start_snapshot.captured_at,
                    TrainingCrop.id >= start_crop.id,
                ),
            ),
        )
        .order_by(CameraSnapshot.captured_at, TrainingCrop.id)
        .limit(payload.count)
    )
    if is_vehicle_run:
        crop_query = crop_query.where(
            or_(TrainingCrop.label.is_(None), TrainingCrop.label != "bad")
        )
    if payload.preliminary_label is not None:
        latest_events = (
            select(
                DetectionEvent.training_crop_id,
                func.max(DetectionEvent.id).label("event_id"),
            )
            .group_by(DetectionEvent.training_crop_id)
            .subquery()
        )
        crop_query = (
            crop_query.join(
                latest_events,
                latest_events.c.training_crop_id == TrainingCrop.id,
            )
            .join(DetectionEvent, DetectionEvent.id == latest_events.c.event_id)
            .where(DetectionEvent.predicted_state == payload.preliminary_label)
        )
    crops = list(db.scalars(crop_query))
    now = datetime.now(timezone.utc)
    for crop in crops:
        if is_vehicle_run:
            crop.vehicle_label = payload.vehicle_label
            crop.vehicle_label_source = "manual"
            crop.vehicle_labeled_at = now
        else:
            _apply_door_label(crop, payload.label, source="manual", labeled_at=now)
    db.commit()
    crop_ids = [crop.id for crop in crops]
    return TrainingCropRunLabelRead(
        crop_ids=crop_ids,
        label=payload.label,
        vehicle_label=payload.vehicle_label,
        count=len(crop_ids),
    )


@router.post("/training/crops/labels/clear", response_model=TrainingCropLabelsClearRead)
def clear_training_crop_labels(
    payload: TrainingCropLabelsClear,
    db: Session = Depends(get_db),
) -> TrainingCropLabelsClearRead:
    crop_ids = list(dict.fromkeys(payload.crop_ids))
    crops = list(db.scalars(select(TrainingCrop).where(TrainingCrop.id.in_(crop_ids))))
    for crop in crops:
        if payload.dimension == "vehicle":
            crop.vehicle_label = None
            crop.vehicle_label_source = None
            crop.vehicle_labeled_at = None
        else:
            _clear_door_label(crop)
    db.commit()
    cleared_ids = [crop.id for crop in crops]
    return TrainingCropLabelsClearRead(
        crop_ids=cleared_ids,
        count=len(cleared_ids),
        dimension=payload.dimension,
    )


@router.delete("/training/crops/{crop_id}/label", response_model=TrainingCropLabelRead)
def clear_training_crop_label(
    crop_id: int,
    db: Session = Depends(get_db),
) -> TrainingCropLabelRead:
    crop = db.get(TrainingCrop, crop_id)
    if crop is None:
        raise HTTPException(status_code=404, detail="Training crop not found")
    _clear_door_label(crop)
    db.commit()
    return TrainingCropLabelRead(
        id=crop.id,
        label=None,
        vehicle_label=crop.vehicle_label,
    )


def _batch_eligible_statement(confidence_threshold: float, room_number: int | None):
    latest_events = (
        select(
            DetectionEvent.training_crop_id,
            func.max(DetectionEvent.id).label("event_id"),
        )
        .group_by(DetectionEvent.training_crop_id)
        .subquery()
    )
    query = (
        select(
            TrainingCrop.id.label("crop_id"),
            DetectionEvent.predicted_state,
            DetectionEvent.confidence,
            DetectionEvent.model_version,
        )
        .join(latest_events, latest_events.c.training_crop_id == TrainingCrop.id)
        .join(DetectionEvent, DetectionEvent.id == latest_events.c.event_id)
        .join(Room, TrainingCrop.room_id == Room.id)
        .where(
            TrainingCrop.label.is_(None),
            DetectionEvent.predicted_state.in_(("open", "closed")),
            DetectionEvent.confidence >= confidence_threshold,
        )
        .order_by(TrainingCrop.id)
    )
    if room_number is not None:
        query = query.where(Room.room_id == room_number)
    return query


def _latest_active_batch(db: Session) -> TrainingLabelBatch | None:
    return db.scalar(
        select(TrainingLabelBatch)
        .where(TrainingLabelBatch.undone_at.is_(None))
        .order_by(TrainingLabelBatch.id.desc())
        .limit(1)
    )


@router.post("/training/labels/batches/preview", response_model=BatchApprovalPreview)
def preview_training_label_batch(
    payload: BatchApprovalRequest,
    db: Session = Depends(get_db),
) -> BatchApprovalPreview:
    count_query = (
        select(func.count())
        .select_from(TrainingCrop)
        .join(Room, TrainingCrop.room_id == Room.id)
        .where(TrainingCrop.label.is_(None))
    )
    if payload.room_number is not None:
        count_query = count_query.where(Room.room_id == payload.room_number)
    total_unlabeled = db.scalar(count_query) or 0
    eligible = _batch_eligible_statement(
        payload.confidence_threshold, payload.room_number
    ).subquery()
    counts = {
        state: count
        for state, count in db.execute(
            select(eligible.c.predicted_state, func.count())
            .select_from(eligible)
            .group_by(eligible.c.predicted_state)
        )
    }
    predicted_open = counts.get("open", 0)
    predicted_closed = counts.get("closed", 0)
    eligible_count = predicted_open + predicted_closed
    latest_batch = _latest_active_batch(db)
    return BatchApprovalPreview(
        confidence_threshold=payload.confidence_threshold,
        room_number=payload.room_number,
        total_unlabeled=total_unlabeled,
        eligible=eligible_count,
        predicted_open=predicted_open,
        predicted_closed=predicted_closed,
        remaining_manual=total_unlabeled - eligible_count,
        latest_batch_id=latest_batch.id if latest_batch else None,
        latest_batch_count=latest_batch.images_approved if latest_batch else 0,
        can_undo=latest_batch is not None,
    )


@router.post("/training/labels/batches", response_model=BatchApprovalResult)
def approve_training_label_batch(
    payload: BatchApprovalRequest,
    db: Session = Depends(get_db),
) -> BatchApprovalResult:
    rows = list(
        db.execute(
            _batch_eligible_statement(
                payload.confidence_threshold, payload.room_number
            )
        )
    )
    if not rows:
        raise HTTPException(status_code=400, detail="No unlabeled crops match this batch.")
    now = datetime.now(timezone.utc)
    open_approved = sum(row.predicted_state == "open" for row in rows)
    closed_approved = sum(row.predicted_state == "closed" for row in rows)
    model_versions = sorted({row.model_version for row in rows})
    batch = TrainingLabelBatch(
        confidence_threshold=payload.confidence_threshold,
        room_number=payload.room_number,
        images_approved=len(rows),
        open_approved=open_approved,
        closed_approved=closed_approved,
        model_versions=json.dumps(model_versions),
        created_at=now,
    )
    db.add(batch)
    db.flush()
    crops = {
        crop.id: crop
        for crop in db.scalars(
            select(TrainingCrop).where(TrainingCrop.id.in_(row.crop_id for row in rows))
        )
    }
    for row in rows:
        crop = crops[row.crop_id]
        _apply_door_label(
            crop,
            row.predicted_state,
            source="batch",
            labeled_at=now,
            batch_id=batch.id,
            confidence=row.confidence,
        )
    db.commit()
    return BatchApprovalResult(
        batch_id=batch.id,
        confidence_threshold=batch.confidence_threshold,
        room_number=batch.room_number,
        images_approved=batch.images_approved,
        open_approved=batch.open_approved,
        closed_approved=batch.closed_approved,
        model_versions=model_versions,
        created_at=batch.created_at,
    )


@router.delete("/training/labels/batches/latest", response_model=BatchUndoResult)
def undo_latest_training_label_batch(
    db: Session = Depends(get_db),
) -> BatchUndoResult:
    batch = _latest_active_batch(db)
    if batch is None:
        raise HTTPException(status_code=404, detail="There is no batch to undo.")
    crops = list(
        db.scalars(
            select(TrainingCrop).where(
                TrainingCrop.label_batch_id == batch.id,
                TrainingCrop.label_source == "batch",
            )
        )
    )
    for crop in crops:
        _clear_door_label(crop)
    batch.undone_at = datetime.now(timezone.utc)
    db.commit()
    return BatchUndoResult(batch_id=batch.id, labels_reverted=len(crops))


@router.post("/training/dataset/export", response_model=DatasetExportResult)
def export_training_dataset(
    payload: DatasetExportRequest | None = None,
    db: Session = Depends(get_db),
) -> DatasetExportResult:
    try:
        return export_classification_dataset(db, payload or DatasetExportRequest())
    except DatasetExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/training/dataset/preview", response_model=DatasetExportPreview)
def preview_training_dataset(
    payload: DatasetExportRequest | None = None,
    db: Session = Depends(get_db),
) -> DatasetExportPreview:
    try:
        return preview_classification_dataset(db, payload or DatasetExportRequest())
    except DatasetExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
