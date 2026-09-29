from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models import (
    Base,
    Camera,
    CameraSnapshot,
    DetectionEvent,
    DoorState,
    InferenceJob,
    Room,
    TrainingCrop,
)
from app.services.classification import ClassificationPrediction
from app.services.inference import (
    enqueue_crop,
    enqueue_unprocessed_crops,
    process_inference_jobs,
)


class FakeClassifier:
    model_version = "fake-model:test"

    def __init__(self, predictions: list[ClassificationPrediction]) -> None:
        self.predictions = predictions

    def predict(self, image_paths: list[Path]) -> list[ClassificationPrediction]:
        return [self.predictions.pop(0) for _path in image_paths]


def prediction(state: DoorState, confidence: float) -> ClassificationPrediction:
    open_probability = confidence if state == DoorState.open else 1 - confidence
    return ClassificationPrediction(
        state=state,
        confidence=confidence,
        closed_probability=1 - open_probability,
        open_probability=open_probability,
    )


def test_inference_jobs_confirm_room_state_and_keep_manual_labels(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "media_root", tmp_path)
    crop_dir = tmp_path / "training_crops"
    crop_dir.mkdir()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with session_local() as db:
        camera = Camera(name="Garage", unifi_camera_id="camera-1")
        db.add(camera)
        db.flush()
        room = Room(room_id=101, camera_id=camera.id, name="Room 101")
        db.add(room)
        db.flush()

        started_at = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        for index in range(4):
            image_path = crop_dir / f"crop_{index}.jpg"
            image_path.write_bytes(b"test-image")
            snapshot = CameraSnapshot(
                camera_id=camera.id,
                image_path=f"/media/camera_captures/snapshot_{index}.jpg",
                captured_at=started_at + timedelta(minutes=index),
            )
            db.add(snapshot)
            db.flush()
            crop = TrainingCrop(
                snapshot_id=snapshot.id,
                room_id=room.id,
                image_path=f"/media/training_crops/{image_path.name}",
                roi_x=0,
                roi_y=0,
                roi_width=100,
                roi_height=100,
                label="closed" if index == 0 else None,
            )
            db.add(crop)
            enqueue_crop(db, crop)
        db.commit()

        classifier = FakeClassifier(
            [
                prediction(DoorState.open, 0.96),
                prediction(DoorState.open, 0.94),
                prediction(DoorState.open, 0.92),
                prediction(DoorState.unknown, 0.55),
            ]
        )

        assert process_inference_jobs(db, classifier, batch_size=1, confirmation_count=3) == 1
        db.refresh(room)
        assert room.current_state == DoorState.unknown
        assert room.consecutive_match_count == 1

        process_inference_jobs(db, classifier, batch_size=1, confirmation_count=3)
        process_inference_jobs(db, classifier, batch_size=1, confirmation_count=3)
        db.refresh(room)
        assert room.current_state == DoorState.open
        assert room.current_confidence == 0.92
        assert room.last_confirmed_change_at == (
            started_at + timedelta(minutes=2)
        ).replace(tzinfo=None)

        process_inference_jobs(db, classifier, batch_size=1, confirmation_count=3)
        db.refresh(room)
        assert room.current_state == DoorState.open
        assert room.last_detected_state == DoorState.unknown
        assert room.last_detected_confidence == 0.55
        assert room.consecutive_match_count == 0
        assert len(list(db.scalars(select(DetectionEvent)))) == 4
        assert all(
            job.status == "completed" for job in db.scalars(select(InferenceJob))
        )
        assert db.scalar(select(TrainingCrop).order_by(TrainingCrop.id)).label == "closed"


def test_historical_crops_are_queued_as_lower_priority_backfill(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "media_root", tmp_path)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with session_local() as db:
        camera = Camera(name="Historical", unifi_camera_id="camera-history")
        db.add(camera)
        db.flush()
        room = Room(room_id=202, camera_id=camera.id, name="Room 202")
        db.add(room)
        snapshot = CameraSnapshot(
            camera_id=camera.id,
            image_path="/media/camera_captures/history.jpg",
            captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        db.add(snapshot)
        db.flush()
        crop = TrainingCrop(
            snapshot_id=snapshot.id,
            room_id=room.id,
            image_path="/media/training_crops/history.jpg",
            roi_x=0,
            roi_y=0,
            roi_width=100,
            roi_height=100,
        )
        db.add(crop)
        db.commit()

        assert enqueue_unprocessed_crops(db) == 1
        job = db.scalar(select(InferenceJob))
        assert job is not None
        assert job.training_crop_id == crop.id
        assert job.status == "queued"
        assert job.is_backfill is True
        assert enqueue_unprocessed_crops(db) == 0
