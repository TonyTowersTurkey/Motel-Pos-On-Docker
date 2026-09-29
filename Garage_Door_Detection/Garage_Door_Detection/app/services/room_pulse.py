import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    Camera,
    CameraSnapshot,
    DetectionEvent,
    Room,
    RoomPulseConfig,
    RoomPulseDelivery,
    TrainingCrop,
)

logger = logging.getLogger(__name__)


def get_room_pulse_config(db: Session) -> RoomPulseConfig:
    config = db.get(RoomPulseConfig, 1)
    if config is None:
        config = RoomPulseConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def build_room_pulse_payload(
    db: Session, config: RoomPulseConfig, event_type: str
) -> dict:
    latest_crop_path = (
        select(TrainingCrop.image_path)
        .join(CameraSnapshot, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .where(TrainingCrop.room_id == Room.id)
        .order_by(CameraSnapshot.captured_at.desc(), TrainingCrop.id.desc())
        .limit(1)
        .correlate(Room)
        .scalar_subquery()
    )
    latest_snapshot_id = (
        select(TrainingCrop.snapshot_id)
        .join(CameraSnapshot, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .where(TrainingCrop.room_id == Room.id)
        .order_by(CameraSnapshot.captured_at.desc(), TrainingCrop.id.desc())
        .limit(1)
        .correlate(Room)
        .scalar_subquery()
    )
    latest_snapshot_at = (
        select(CameraSnapshot.captured_at)
        .join(TrainingCrop, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .where(TrainingCrop.room_id == Room.id)
        .order_by(CameraSnapshot.captured_at.desc(), TrainingCrop.id.desc())
        .limit(1)
        .correlate(Room)
        .scalar_subquery()
    )
    latest_model = (
        select(DetectionEvent.model_version)
        .where(DetectionEvent.room_id == Room.id)
        .order_by(DetectionEvent.id.desc())
        .limit(1)
        .correlate(Room)
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            Room,
            Camera,
            latest_crop_path.label("crop_path"),
            latest_snapshot_id.label("snapshot_id"),
            latest_snapshot_at.label("snapshot_at"),
            latest_model.label("model_version"),
        )
        .join(Camera, Room.camera_id == Camera.id)
        .where(Room.active.is_(True))
        .order_by(Room.room_id, Room.id)
    )
    rooms = []
    for room, camera, crop_path, snapshot_id, snapshot_at, model_version in rows:
        image_url = None
        if config.include_image_url and crop_path and config.public_base_url:
            image_url = urljoin(config.public_base_url.rstrip("/") + "/", crop_path.lstrip("/"))
        rooms.append(
            {
                "room_record_id": room.id,
                "room_number": room.room_id,
                "room_name": room.name,
                "state": room.current_state.value
                if hasattr(room.current_state, "value")
                else room.current_state,
                "confidence": room.current_confidence,
                "state_source": "confirmed",
                "confirmation_streak": room.consecutive_match_count,
                "state_changed_at": _iso(room.last_confirmed_change_at),
                "last_observed_at": _iso(room.last_detection_at),
                "last_observed_state": room.last_detected_state.value
                if hasattr(room.last_detected_state, "value")
                else room.last_detected_state,
                "last_observed_confidence": room.last_detected_confidence,
                "camera_id": camera.id,
                "camera_name": camera.name,
                "snapshot_id": snapshot_id,
                "snapshot_captured_at": _iso(snapshot_at),
                "crop_image_path": crop_path if config.include_image_url else None,
                "crop_image_url": image_url,
                "model_version": model_version,
                "stale": room.last_detection_at is None
                or datetime.now(timezone.utc)
                - (
                    room.last_detection_at.replace(tzinfo=timezone.utc)
                    if room.last_detection_at.tzinfo is None
                    else room.last_detection_at
                )
                > timedelta(minutes=3),
            }
        )
    return {
        "schema_version": "1.0",
        "event_id": str(uuid4()),
        "event_type": event_type,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": settings.app_name,
        "room_count": len(rooms),
        "rooms": rooms,
    }


def send_room_pulse(
    db: Session,
    event_type: str,
    client: httpx.Client | None = None,
) -> RoomPulseDelivery:
    config = get_room_pulse_config(db)
    if not config.endpoint_url:
        raise ValueError("Room Pulse endpoint URL is not configured")
    payload = build_room_pulse_payload(db, config, event_type)
    delivery = RoomPulseDelivery(
        event_id=payload["event_id"],
        event_type=event_type,
        status="pending",
        endpoint_url=config.endpoint_url,
        room_count=payload["room_count"],
        payload=json.dumps(payload, separators=(",", ":")),
    )
    db.add(delivery)
    db.commit()
    headers = {"Content-Type": "application/json", "X-Room-Pulse-Event": delivery.event_id}
    if config.bearer_token:
        headers["Authorization"] = f"Bearer {config.bearer_token}"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=config.timeout_seconds)
    try:
        for attempt in range(1, 4):
            delivery.attempt_count = attempt
            try:
                response = http_client.post(config.endpoint_url, json=payload, headers=headers)
                delivery.http_status = response.status_code
                response.raise_for_status()
                delivery.status = "success"
                delivery.delivered_at = datetime.now(timezone.utc)
                delivery.error = None
                config.last_sent_at = delivery.delivered_at
                config.last_error = None
                break
            except httpx.HTTPError as exc:
                delivery.status = "failed"
                delivery.error = str(exc)[:1000]
                config.last_error = delivery.error
        db.commit()
        db.refresh(delivery)
        return delivery
    finally:
        if owns_client:
            http_client.close()


def room_pulse_due(db: Session, now: datetime | None = None) -> str | None:
    config = get_room_pulse_config(db)
    if not config.enabled or not config.endpoint_url:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    last_sent = config.last_sent_at
    if last_sent and last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=timezone.utc)
    latest_change = db.scalar(select(func.max(Room.last_confirmed_change_at)))
    if latest_change and latest_change.tzinfo is None:
        latest_change = latest_change.replace(tzinfo=timezone.utc)
    if config.send_on_change and latest_change and (last_sent is None or latest_change > last_sent):
        return "room_state_changed"
    if last_sent is None or current - last_sent >= timedelta(seconds=config.interval_seconds):
        return "room_state_heartbeat"
    return None


def run_room_pulse_pass() -> None:
    with SessionLocal() as db:
        event_type = room_pulse_due(db)
        if event_type:
            delivery = send_room_pulse(db, event_type)
            if delivery.status != "success":
                logger.warning("Room Pulse delivery failed: %s", delivery.error)


async def automatic_room_pulse_worker() -> None:
    while True:
        try:
            await asyncio.to_thread(run_room_pulse_pass)
        except Exception:
            logger.exception("Unexpected Room Pulse worker error")
        await asyncio.sleep(2)
