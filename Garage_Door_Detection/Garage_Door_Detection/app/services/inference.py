import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import DetectionEvent, DoorState, InferenceJob, TrainingCrop
from app.services.classification import (
    ClassificationModelError,
    ClassificationPrediction,
    YoloGarageDoorClassifier,
)

logger = logging.getLogger(__name__)


class GarageDoorClassifier(Protocol):
    model_version: str

    def predict(self, image_paths: list[Path]) -> list[ClassificationPrediction]: ...


def enqueue_crop(db: Session, crop: TrainingCrop) -> InferenceJob:
    """Queue a new crop, or reset its job when crop pixels/coordinates changed."""
    db.flush()
    job = db.scalar(
        select(InferenceJob).where(InferenceJob.training_crop_id == crop.id)
    )
    if job is None:
        job = InferenceJob(training_crop_id=crop.id)
        db.add(job)
    else:
        job.status = "queued"
        job.is_backfill = False
        job.attempt_count = 0
        job.model_version = None
        job.last_error = None
        job.started_at = None
        job.completed_at = None
    return job


def recover_interrupted_jobs(db: Session) -> None:
    db.execute(
        update(InferenceJob)
        .where(InferenceJob.status == "running")
        .values(status="queued", started_at=None, last_error="Worker restarted")
    )
    db.commit()


def enqueue_unprocessed_crops(db: Session) -> int:
    """Queue historical crops that were created before classification was enabled."""
    crop_ids = list(
        db.scalars(
            select(TrainingCrop.id)
            .outerjoin(
                InferenceJob,
                InferenceJob.training_crop_id == TrainingCrop.id,
            )
            .where(InferenceJob.id.is_(None))
            .order_by(TrainingCrop.id)
        )
    )
    if crop_ids:
        db.add_all(
            [
                InferenceJob(training_crop_id=crop_id, is_backfill=True)
                for crop_id in crop_ids
            ]
        )
        db.commit()
    return len(crop_ids)


def process_inference_jobs(
    db: Session,
    classifier: GarageDoorClassifier,
    *,
    batch_size: int | None = None,
    max_attempts: int | None = None,
    confirmation_count: int | None = None,
) -> int:
    batch_limit = batch_size or settings.classification_batch_size
    attempt_limit = max_attempts or settings.classification_max_attempts
    confirmations = confirmation_count or settings.classification_confirmation_count
    jobs = list(
        db.scalars(
            select(InferenceJob)
            .options(
                joinedload(InferenceJob.crop).joinedload(TrainingCrop.room),
                joinedload(InferenceJob.crop).joinedload(TrainingCrop.snapshot),
            )
            .where(
                or_(InferenceJob.status == "queued", InferenceJob.status == "failed"),
                InferenceJob.attempt_count < attempt_limit,
            )
            .order_by(InferenceJob.is_backfill, InferenceJob.id)
            .limit(batch_limit)
        )
    )
    if not jobs:
        return 0

    started_at = datetime.now(timezone.utc)
    for job in jobs:
        job.status = "running"
        job.attempt_count += 1
        job.started_at = started_at
        job.completed_at = None
        job.last_error = None
    db.commit()

    ready_jobs: list[InferenceJob] = []
    image_paths: list[Path] = []
    for job in jobs:
        path = _media_disk_path(job.crop.image_path)
        if not path.is_file():
            _fail_job(job, f"Crop image not found: {job.crop.image_path}")
        else:
            ready_jobs.append(job)
            image_paths.append(path)

    if ready_jobs:
        try:
            predictions = classifier.predict(image_paths)
            if len(predictions) != len(ready_jobs):
                raise ClassificationModelError(
                    f"Classifier returned {len(predictions)} results for "
                    f"{len(ready_jobs)} jobs"
                )
            for job, prediction in zip(ready_jobs, predictions, strict=True):
                _complete_job(job, prediction, classifier.model_version, confirmations)
        except Exception as exc:
            logger.exception("Garage-door classification batch failed")
            for job in ready_jobs:
                _fail_job(job, str(exc))

    db.commit()
    return len(jobs)


def _complete_job(
    job: InferenceJob,
    prediction: ClassificationPrediction,
    model_version: str,
    confirmation_count: int,
) -> None:
    crop = job.crop
    detected_at = crop.snapshot.captured_at
    room = crop.room
    if _is_current_detection(detected_at, room.last_detection_at):
        room.last_detection_at = detected_at
        room.last_detected_confidence = prediction.confidence

        if prediction.state == DoorState.unknown:
            room.last_detected_state = DoorState.unknown
            room.consecutive_match_count = 0
        else:
            if room.last_detected_state == prediction.state:
                room.consecutive_match_count += 1
            else:
                room.consecutive_match_count = 1
            room.last_detected_state = prediction.state

            if room.consecutive_match_count >= confirmation_count:
                if room.current_state != prediction.state:
                    room.current_state = prediction.state
                    room.last_confirmed_change_at = detected_at
                room.current_confidence = prediction.confidence

    job.status = "completed"
    job.model_version = model_version
    job.last_error = None
    job.completed_at = datetime.now(timezone.utc)
    job.crop.detection_events.append(
        DetectionEvent(
            room_id=room.id,
            snapshot_id=crop.snapshot_id,
            predicted_state=prediction.state,
            confidence=prediction.confidence,
            closed_probability=prediction.closed_probability,
            open_probability=prediction.open_probability,
            model_version=model_version,
        )
    )


def _fail_job(job: InferenceJob, message: str) -> None:
    job.status = "failed"
    job.last_error = message[:2000]
    job.completed_at = datetime.now(timezone.utc)


def _is_current_detection(detected_at: datetime, last_detection_at: datetime | None) -> bool:
    if last_detection_at is None:
        return True
    return _utc_naive(detected_at) >= _utc_naive(last_detection_at)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _media_disk_path(image_path: str) -> Path:
    prefix = "/media/"
    if not image_path.startswith(prefix):
        return Path("/__invalid_media_path__")
    destination = (settings.media_root / image_path.removeprefix(prefix)).resolve()
    try:
        destination.relative_to(settings.media_root.resolve())
    except ValueError:
        return Path("/__invalid_media_path__")
    return destination


def run_inference_pass(classifier: GarageDoorClassifier) -> int:
    with SessionLocal() as db:
        return process_inference_jobs(db, classifier)


async def automatic_inference_worker() -> None:
    if not settings.classification_enabled:
        logger.info("Automatic garage-door classification is disabled")
        return
    try:
        classifier = await asyncio.to_thread(
            YoloGarageDoorClassifier,
            settings.classification_model_path,
            settings.classification_confidence_threshold,
        )
    except Exception as exc:
        logger.error("Automatic garage-door classification unavailable: %s", exc)
        return

    with SessionLocal() as db:
        recover_interrupted_jobs(db)
        queued = enqueue_unprocessed_crops(db)
    if queued:
        logger.info("Queued %d historical crops for preliminary classification", queued)
    logger.info("Loaded garage-door classifier %s", classifier.model_version)

    while True:
        try:
            processed = await asyncio.to_thread(run_inference_pass, classifier)
        except Exception:
            logger.exception("Unexpected automatic classification worker error")
            processed = 0
        if processed == 0:
            await asyncio.sleep(settings.classification_poll_seconds)
