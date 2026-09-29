import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import cv2
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Camera, CameraSnapshot, DetectionEvent, Room, TrainingCrop
from app.schemas import DatasetExportPreview, DatasetExportRequest, DatasetExportResult

DOOR_CLASSES = ("open", "closed", "partial")
VEHICLE_CLASSES = ("present", "absent")
CLASSES = DOOR_CLASSES
SPLITS = ("train", "val", "test")
BENCHMARK_FILENAME = ".fixed_test_benchmark.json"
BENCHMARK_FILENAMES = {
    "door": BENCHMARK_FILENAME,
    "vehicle": ".fixed_test_benchmark_vehicle.json",
    "separate": ".fixed_test_benchmark_separate.json",
    "multitask": ".fixed_test_benchmark_multitask.json",
}


class DatasetExportError(RuntimeError):
    pass


@dataclass
class Candidate:
    crop: TrainingCrop
    snapshot: CameraSnapshot
    camera: Camera
    room: Room
    prediction: DetectionEvent | None
    source: Path
    sha256: str
    perceptual_hash: int | None
    mean_brightness: float | None
    glare_fraction: float | None
    blur_score: float | None
    edge_tags: list[str] = field(default_factory=list)
    selection_reasons: list[str] = field(default_factory=list)


@dataclass
class DatasetPlan:
    selected: list[Candidate]
    task_candidates: dict[str, list[Candidate]]
    benchmark: dict[str, object]
    benchmark_crop_ids: set[int]
    train_val_splits: dict[str, str]
    candidates_considered: int
    missing_images: int
    duplicates_removed: int
    conflicting_duplicates: int
    routine_images_skipped: int
    class_balance_removed: int
    benchmark_created: bool
    benchmark_group_exclusions: int

    def task_counts(self) -> dict[str, dict[str, dict[str, int]]]:
        result = {}
        for task, candidates in self.task_candidates.items():
            classes = _task_classes(task)
            task_result = {split: {label: 0 for label in classes} for split in SPLITS}
            for candidate in candidates:
                label = _task_label(candidate, task)
                if label not in classes:
                    continue
                split = self.split_for(candidate)
                task_result[split][label] += 1
            result[task] = task_result
        return result

    def counts(self) -> dict[str, dict[str, int]]:
        task_counts = self.task_counts()
        primary = next(iter(task_counts), "door")
        return task_counts.get(primary, {split: {} for split in SPLITS})

    def split_for(self, candidate: Candidate) -> str:
        return (
            "test"
            if candidate.crop.id in self.benchmark_crop_ids
            else self.train_val_splits[_group_key(candidate.snapshot)]
        )


def export_classification_dataset(
    db: Session,
    options: DatasetExportRequest | None = None,
) -> DatasetExportResult:
    options = options or DatasetExportRequest()
    plan = _plan_dataset(db, options, persist_benchmark=True)

    created_at = datetime.now(timezone.utc)
    dataset_version = f"v{created_at.strftime('%Y%m%dT%H%M%S%fZ')}"
    export_name = f"garage_dataset_{options.export_mode}_{dataset_version}"
    export_root = settings.dataset_export_dir / export_name
    counts = plan.counts()
    task_counts = plan.task_counts()
    manifest_rows: list[dict[str, object]] = []
    if options.export_mode == "multitask":
        door_target_ids = {candidate.crop.id for candidate in plan.task_candidates["door"]}
        vehicle_target_ids = {
            candidate.crop.id for candidate in plan.task_candidates["vehicle"]
        }
        for split in SPLITS:
            (export_root / split / "images").mkdir(parents=True, exist_ok=True)
        for candidate in plan.selected:
            split = plan.split_for(candidate)
            filename = f"crop_{candidate.crop.id:08d}_{candidate.source.name}"
            relative_path = Path(split) / "images" / filename
            shutil.copy2(candidate.source, export_root / relative_path)
            manifest_rows.append(
                _manifest_row(
                    candidate,
                    relative_path,
                    split,
                    task="multitask",
                    label="",
                    door_label_valid=candidate.crop.id in door_target_ids,
                    vehicle_label_valid=candidate.crop.id in vehicle_target_ids,
                )
            )
    else:
        for task, candidates in plan.task_candidates.items():
            base = Path(task) if options.export_mode == "separate" else Path()
            for split in SPLITS:
                for label in _task_classes(task):
                    (export_root / base / split / label).mkdir(parents=True, exist_ok=True)
            for candidate in candidates:
                label = _task_label(candidate, task)
                if label not in _task_classes(task):
                    continue
                split = plan.split_for(candidate)
                filename = f"crop_{candidate.crop.id:08d}_{candidate.source.name}"
                relative_path = base / split / label / filename
                shutil.copy2(candidate.source, export_root / relative_path)
                manifest_rows.append(
                    _manifest_row(candidate, relative_path, split, task=task, label=label)
                )

    if not manifest_rows:
        raise DatasetExportError("No curated images were available to write")

    _write_manifest(export_root, manifest_rows)
    if options.export_mode in {"door", "vehicle"}:
        task = options.export_mode
        (export_root / "classes.txt").write_text(
            "\n".join(_task_classes(task)) + "\n", encoding="utf-8"
        )
    else:
        (export_root / "door_classes.txt").write_text(
            "\n".join(DOOR_CLASSES) + "\n", encoding="utf-8"
        )
        (export_root / "vehicle_classes.txt").write_text(
            "\n".join(VEHICLE_CLASSES) + "\n", encoding="utf-8"
        )
    excluded_bad = (
        db.scalar(select(func.count()).select_from(TrainingCrop).where(TrainingCrop.label == "bad"))
        or 0
    )
    metadata = {
        "format_version": 3,
        "export_mode": options.export_mode,
        "dataset_version": dataset_version,
        "created_at": created_at.isoformat(),
        "classes": {
            "door": list(DOOR_CLASSES),
            "vehicle": list(VEHICLE_CLASSES),
        },
        "directory_layout": _directory_layout(options.export_mode),
        "review_policy": (
            "Only operator-reviewed door and vehicle labels are eligible. Unsure, bad, and "
            "not-observable vehicle targets are excluded from classification loss."
        ),
        "curation": options.model_dump(mode="json"),
        "split_strategy": (
            "Persistent fixed benchmark test set; deterministic camera/hour groups for validation; "
            "new images never enter test."
        ),
        "benchmark": plan.benchmark,
        "images_exported": len(manifest_rows),
        "candidates_considered": plan.candidates_considered,
        "missing_images": plan.missing_images,
        "duplicates_removed": plan.duplicates_removed,
        "conflicting_duplicates": plan.conflicting_duplicates,
        "benchmark_group_exclusions": plan.benchmark_group_exclusions,
        "routine_images_skipped": plan.routine_images_skipped,
        "class_balance_removed": plan.class_balance_removed,
        "excluded_bad": excluded_bad,
        "counts": counts,
        "task_counts": task_counts,
    }
    (export_root / "dataset.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (export_root / "README.md").write_text(
        _dataset_readme(options.export_mode), encoding="utf-8"
    )

    archive = Path(
        shutil.make_archive(
            str(export_root),
            "zip",
            root_dir=export_root.parent,
            base_dir=export_root.name,
        )
    )
    return DatasetExportResult(
        export_mode=options.export_mode,
        dataset_version=dataset_version,
        archive_url=_media_url(archive),
        export_path=_media_url(export_root),
        images_exported=len(manifest_rows),
        missing_images=plan.missing_images,
        excluded_bad=excluded_bad,
        candidates_considered=plan.candidates_considered,
        duplicates_removed=plan.duplicates_removed,
        conflicting_duplicates=plan.conflicting_duplicates,
        routine_images_skipped=plan.routine_images_skipped,
        class_balance_removed=plan.class_balance_removed,
        benchmark_created=plan.benchmark_created,
        counts=counts,
        task_counts=task_counts,
    )


def preview_classification_dataset(
    db: Session,
    options: DatasetExportRequest | None = None,
) -> DatasetExportPreview:
    options = options or DatasetExportRequest()
    plan = _plan_dataset(db, options, persist_benchmark=False)
    counts = plan.counts()
    task_counts = plan.task_counts()
    queried_task_counts = {
        task: {label: 0 for label in _task_classes(task)} for task in _mode_tasks(options.export_mode)
    }
    for crop, _snapshot, _camera, _room, _prediction in _reviewed_rows(db, options):
        for task in queried_task_counts:
            label = _crop_task_label(crop, task)
            if label in queried_task_counts[task]:
                queried_task_counts[task][label] += 1
    primary_task = next(iter(queried_task_counts))
    queried_counts = queried_task_counts[primary_task]
    selected_images = (
        len(plan.selected)
        if options.export_mode == "multitask"
        else sum(len(candidates) for candidates in plan.task_candidates.values())
    )
    return DatasetExportPreview(
        export_mode=options.export_mode,
        candidates_considered=plan.candidates_considered,
        queried_counts=queried_counts,
        selected_images=selected_images,
        selected_counts={
            label: sum(counts[split][label] for split in SPLITS)
            for label in queried_counts
        },
        split_counts=counts,
        queried_task_counts=queried_task_counts,
        task_counts=task_counts,
        missing_images=plan.missing_images,
        duplicates_removed=plan.duplicates_removed,
        conflicting_duplicates=plan.conflicting_duplicates,
        routine_images_skipped=plan.routine_images_skipped,
        class_balance_removed=plan.class_balance_removed,
        benchmark_will_be_created=plan.benchmark_created,
    )


def _plan_dataset(
    db: Session,
    options: DatasetExportRequest,
    *,
    persist_benchmark: bool,
) -> DatasetPlan:
    rows = _reviewed_rows(db, options)
    if not rows:
        raise DatasetExportError("Review and label at least one crop before exporting a dataset")

    candidates, missing = _load_candidates(rows)
    if not candidates:
        raise DatasetExportError("Reviewed crop records exist, but their image files are missing")

    candidates, conflicting_duplicates = _remove_label_conflicts(candidates, options.export_mode)
    candidates, duplicates_removed = _remove_duplicates(candidates, options)
    if persist_benchmark:
        settings.dataset_export_dir.mkdir(parents=True, exist_ok=True)
    benchmark_path = settings.dataset_export_dir / BENCHMARK_FILENAMES[options.export_mode]
    benchmark = _load_benchmark(benchmark_path)
    benchmark_created = benchmark is None
    benchmark_crop_ids = set(benchmark.get("crop_ids", [])) if benchmark else set()
    benchmark_groups = set(benchmark.get("group_keys", [])) if benchmark else set()

    selected: list[Candidate] = []
    benchmark_group_exclusions = 0
    for candidate in candidates:
        group = _group_key(candidate.snapshot)
        if candidate.crop.id in benchmark_crop_ids:
            candidate.selection_reasons.append("fixed_benchmark")
            selected.append(candidate)
            continue
        if benchmark and group in benchmark_groups:
            benchmark_group_exclusions += 1
            continue
        reasons = _priority_reasons(candidate, options)
        if reasons:
            candidate.selection_reasons.extend(reasons)
            selected.append(candidate)
        elif _deterministic_sample(candidate, options.random_sample_percent):
            candidate.selection_reasons.append("routine_random_sample")
            selected.append(candidate)

    _ensure_representative_floor(selected, candidates, benchmark_groups, options)
    selected = sorted({item.crop.id: item for item in selected}.values(), key=_candidate_order)
    if not selected:
        raise DatasetExportError(
            "The curation filters selected no images; increase the routine sample or enable a "
            "priority category"
        )

    if benchmark_created:
        benchmark = _create_benchmark(
            selected,
            options,
            benchmark_path if persist_benchmark else None,
        )
        benchmark_crop_ids = set(benchmark["crop_ids"])
        benchmark_groups = set(benchmark["group_keys"])
        for candidate in selected:
            if candidate.crop.id in benchmark_crop_ids:
                candidate.selection_reasons.append("fixed_benchmark")

    selected_ids = {candidate.crop.id for candidate in selected}
    routine_images_skipped = max(
        0,
        len(candidates) - len(selected_ids) - benchmark_group_exclusions,
    )
    task_candidates = {}
    class_balance_removed = 0
    for task in _mode_tasks(options.export_mode):
        eligible = [
            candidate
            for candidate in selected
            if _task_candidate_is_eligible(candidate, task)
        ]
        minimum_percent = (
            options.minimum_class_percent
            if task == "door"
            else options.vehicle_minimum_class_percent
        )
        balanced, removed = _balance_task_candidates(
            eligible,
            benchmark_crop_ids,
            minimum_percent,
            task,
        )
        task_candidates[task] = balanced
        class_balance_removed += removed
    selected = sorted(
        {
            candidate.crop.id: candidate
            for candidates in task_candidates.values()
            for candidate in candidates
        }.values(),
        key=_candidate_order,
    )
    if not selected:
        raise DatasetExportError("No reviewed labels are eligible for the selected export mode")
    non_test = [candidate for candidate in selected if candidate.crop.id not in benchmark_crop_ids]
    train_val_splits = _train_validation_assignments(non_test, options.validation_percent)
    return DatasetPlan(
        selected=selected,
        task_candidates=task_candidates,
        benchmark=benchmark,
        benchmark_crop_ids=benchmark_crop_ids,
        train_val_splits=train_val_splits,
        candidates_considered=len(rows),
        missing_images=missing,
        duplicates_removed=duplicates_removed,
        conflicting_duplicates=conflicting_duplicates,
        routine_images_skipped=routine_images_skipped,
        class_balance_removed=class_balance_removed,
        benchmark_created=benchmark_created,
        benchmark_group_exclusions=benchmark_group_exclusions,
    )


def _reviewed_rows(
    db: Session,
    options: DatasetExportRequest | None = None,
) -> list[tuple[TrainingCrop, CameraSnapshot, Camera, Room, DetectionEvent | None]]:
    latest_events = (
        select(
            DetectionEvent.training_crop_id,
            func.max(DetectionEvent.id).label("event_id"),
        )
        .group_by(DetectionEvent.training_crop_id)
        .subquery()
    )
    query = (
        select(TrainingCrop, CameraSnapshot, Camera, Room, DetectionEvent)
        .join(CameraSnapshot, TrainingCrop.snapshot_id == CameraSnapshot.id)
        .join(Camera, CameraSnapshot.camera_id == Camera.id)
        .join(Room, TrainingCrop.room_id == Room.id)
        .outerjoin(latest_events, latest_events.c.training_crop_id == TrainingCrop.id)
        .outerjoin(DetectionEvent, DetectionEvent.id == latest_events.c.event_id)
        .order_by(CameraSnapshot.captured_at, TrainingCrop.id)
    )
    if options is None or options.export_mode == "door":
        query = query.where(TrainingCrop.label.in_(DOOR_CLASSES))
    elif options.export_mode == "vehicle":
        query = query.where(
            TrainingCrop.vehicle_label.in_(VEHICLE_CLASSES),
            or_(TrainingCrop.label.is_(None), TrainingCrop.label != "bad"),
        )
    elif options.export_mode == "separate":
        query = query.where(
            or_(
                TrainingCrop.label.in_(DOOR_CLASSES),
                (
                    TrainingCrop.vehicle_label.in_(VEHICLE_CLASSES)
                    & or_(TrainingCrop.label.is_(None), TrainingCrop.label != "bad")
                ),
            )
        )
    else:
        query = query.where(
            TrainingCrop.label.in_(DOOR_CLASSES),
            TrainingCrop.vehicle_label.is_not(None),
        )
    if options is not None and options.captured_from is not None:
        query = query.where(
            CameraSnapshot.captured_at
            >= datetime.combine(options.captured_from, time.min, tzinfo=timezone.utc)
        )
    if options is not None and options.captured_through is not None:
        exclusive_end = datetime.combine(
            options.captured_through + timedelta(days=1),
            time.min,
            tzinfo=timezone.utc,
        )
        query = query.where(CameraSnapshot.captured_at < exclusive_end)
    return list(db.execute(query))


def _load_candidates(
    rows: list[tuple[TrainingCrop, CameraSnapshot, Camera, Room, DetectionEvent | None]],
) -> tuple[list[Candidate], int]:
    candidates = []
    missing = 0
    for crop, snapshot, camera, room, prediction in rows:
        source = _media_disk_path(crop.image_path)
        if not source.is_file():
            missing += 1
            continue
        sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        perceptual_hash, brightness, glare, blur, edge_tags = _image_signals(source)
        candidates.append(
            Candidate(
                crop=crop,
                snapshot=snapshot,
                camera=camera,
                room=room,
                prediction=prediction,
                source=source,
                sha256=sha256,
                perceptual_hash=perceptual_hash,
                mean_brightness=brightness,
                glare_fraction=glare,
                blur_score=blur,
                edge_tags=edge_tags,
            )
        )
    return candidates, missing


def _image_signals(
    source: Path,
) -> tuple[int | None, float | None, float | None, float | None, list[str]]:
    image = cv2.imread(str(source), cv2.IMREAD_GRAYSCALE)
    if image is None or image.size == 0:
        return None, None, None, None, []
    resized = cv2.resize(image, (9, 8), interpolation=cv2.INTER_AREA)
    differences = resized[:, 1:] > resized[:, :-1]
    perceptual_hash = 0
    for index, value in enumerate(differences.flatten()):
        if value:
            perceptual_hash |= 1 << index
    brightness = float(image.mean())
    glare = float((image >= 245).mean())
    blur = float(cv2.Laplacian(image, cv2.CV_64F).var())
    tags = []
    if brightness < 55:
        tags.append("dark_or_night")
    if glare > 0.18:
        tags.append("glare_or_headlights")
    if blur < 50:
        tags.append("possible_motion_blur")
    return perceptual_hash, brightness, glare, blur, tags


def _remove_label_conflicts(
    candidates: list[Candidate], export_mode: str = "door"
) -> tuple[list[Candidate], int]:
    labels_by_hash: dict[str, set[str]] = {}
    for candidate in candidates:
        labels_by_hash.setdefault(candidate.sha256, set()).add(
            _candidate_label_signature(candidate, export_mode)
        )
    conflicts = {value for value, labels in labels_by_hash.items() if len(labels) > 1}
    return [candidate for candidate in candidates if candidate.sha256 not in conflicts], len(conflicts)


def _remove_duplicates(
    candidates: list[Candidate], options: DatasetExportRequest
) -> tuple[list[Candidate], int]:
    accepted: list[Candidate] = []
    exact_hashes: set[str] = set()
    recent_by_scene: dict[tuple[int, int, str], list[Candidate]] = {}
    window = timedelta(minutes=options.duplicate_window_minutes)
    removed = 0
    for candidate in sorted(candidates, key=_candidate_order):
        if candidate.sha256 in exact_hashes:
            removed += 1
            continue
        key = (
            candidate.camera.id,
            candidate.room.id,
            _candidate_label_signature(candidate, options.export_mode),
        )
        recent = recent_by_scene.setdefault(key, [])
        if window > timedelta(0):
            recent[:] = [
                previous
                for previous in recent
                if candidate.snapshot.captured_at - previous.snapshot.captured_at <= window
            ]
        is_near_duplicate = window > timedelta(0) and any(
            _perceptual_distance(candidate.perceptual_hash, previous.perceptual_hash)
            <= options.perceptual_distance
            for previous in recent
            if candidate.perceptual_hash is not None and previous.perceptual_hash is not None
        )
        if is_near_duplicate:
            removed += 1
            continue
        accepted.append(candidate)
        exact_hashes.add(candidate.sha256)
        recent.append(candidate)
    return accepted, removed


def _priority_reasons(candidate: Candidate, options: DatasetExportRequest) -> list[str]:
    reasons = []
    prediction = candidate.prediction
    if (
        options.include_misclassified
        and prediction is not None
        and prediction.predicted_state in CLASSES
        and prediction.predicted_state != candidate.crop.label
    ):
        reasons.append("corrected_misclassification")
    if (
        options.include_low_confidence
        and prediction is not None
        and (
            prediction.confidence < options.low_confidence_threshold
            or abs(prediction.open_probability - prediction.closed_probability)
            < options.probability_margin_threshold
        )
    ):
        reasons.append("low_confidence")
    if options.include_edge_cases and candidate.edge_tags:
        reasons.append("visual_edge_case")
    return reasons


def _deterministic_sample(candidate: Candidate, percent: float) -> bool:
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    digest = hashlib.sha256(f"{candidate.crop.id}:{candidate.sha256}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < percent / 100


def _ensure_representative_floor(
    selected: list[Candidate],
    candidates: list[Candidate],
    benchmark_groups: set[str],
    options: DatasetExportRequest,
) -> None:
    if options.random_sample_percent <= 0:
        return
    selected_groups = {
        (
            candidate.camera.id,
            candidate.room.id,
            _candidate_label_signature(candidate, options.export_mode),
        )
        for candidate in selected
    }
    available: dict[tuple[int, int, str], list[Candidate]] = {}
    for candidate in candidates:
        if _group_key(candidate.snapshot) in benchmark_groups:
            continue
        key = (
            candidate.camera.id,
            candidate.room.id,
            _candidate_label_signature(candidate, options.export_mode),
        )
        available.setdefault(key, []).append(candidate)
    for key, group_candidates in available.items():
        if key in selected_groups:
            continue
        representative = min(
            group_candidates,
            key=lambda item: hashlib.sha256(f"floor:{item.crop.id}".encode()).hexdigest(),
        )
        representative.selection_reasons.append("representative_floor")
        selected.append(representative)


def _balance_candidates(
    selected: list[Candidate],
    benchmark_crop_ids: set[int],
    minimum_class_percent: float,
) -> tuple[list[Candidate], int]:
    return _balance_task_candidates(
        selected,
        benchmark_crop_ids,
        minimum_class_percent,
        "door",
    )


def _balance_task_candidates(
    selected: list[Candidate],
    benchmark_crop_ids: set[int],
    minimum_class_percent: float,
    task: str,
) -> tuple[list[Candidate], int]:
    if minimum_class_percent <= 0:
        return selected, 0
    fixed_test = [candidate for candidate in selected if candidate.crop.id in benchmark_crop_ids]
    eligible = [candidate for candidate in selected if candidate.crop.id not in benchmark_crop_ids]
    classes = _task_classes(task)
    by_label = {
        label: [candidate for candidate in eligible if _task_label(candidate, task) == label]
        for label in classes
    }
    available_labels = [label for label, candidates in by_label.items() if candidates]
    if len(available_labels) < 2:
        return selected, 0
    minority_count = min(len(by_label[label]) for label in available_labels)
    maximum_per_class = math.floor(minority_count * 100 / minimum_class_percent + 1e-9)

    priority = {
        "corrected_misclassification": 0,
        "low_confidence": 1,
        "visual_edge_case": 2,
        "representative_floor": 3,
        "routine_random_sample": 4,
        "fixed_benchmark": 5,
    }

    def retention_key(candidate: Candidate) -> tuple[int, str]:
        rank = min((priority.get(reason, 6) for reason in candidate.selection_reasons), default=6)
        digest = hashlib.sha256(f"balance:{candidate.crop.id}:{candidate.sha256}".encode()).hexdigest()
        return rank, digest

    kept = []
    for label in available_labels:
        kept.extend(sorted(by_label[label], key=retention_key)[:maximum_per_class])
    balanced = fixed_test + kept
    balanced.sort(key=_candidate_order)
    return balanced, len(eligible) - len(kept)


def _create_benchmark(
    selected: list[Candidate], options: DatasetExportRequest, path: Path | None
) -> dict[str, object]:
    groups = sorted(
        {_group_key(candidate.snapshot) for candidate in selected},
        key=lambda value: hashlib.sha256(f"benchmark:{value}".encode()).hexdigest(),
    )
    if len(groups) <= 1:
        test_groups: list[str] = []
    else:
        count = max(1, round(len(groups) * options.initial_test_percent / 100))
        test_groups = groups[: min(count, len(groups) - 1)]
    test_group_set = set(test_groups)
    crop_ids = [
        candidate.crop.id
        for candidate in selected
        if _group_key(candidate.snapshot) in test_group_set
    ]
    benchmark = {
        "format_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "crop_ids": crop_ids,
        "group_keys": test_groups,
        "policy": "Fixed forever unless the benchmark file is deliberately removed.",
    }
    if path is not None:
        path.write_text(json.dumps(benchmark, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return benchmark


def _load_benchmark(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetExportError(f"Could not read fixed benchmark file: {exc}") from exc
    if not isinstance(payload.get("crop_ids"), list) or not isinstance(
        payload.get("group_keys"), list
    ):
        raise DatasetExportError("Fixed benchmark file is invalid")
    return payload


def _train_validation_assignments(
    candidates: list[Candidate], validation_percent: float
) -> dict[str, str]:
    groups = sorted(
        {_group_key(candidate.snapshot) for candidate in candidates},
        key=lambda value: hashlib.sha256(f"validation:{value}".encode()).hexdigest(),
    )
    result = {group: "train" for group in groups}
    if len(groups) <= 1 or validation_percent <= 0:
        return result
    count = max(1, round(len(groups) * validation_percent / 100))
    for group in groups[: min(count, len(groups) - 1)]:
        result[group] = "val"
    return result


def _mode_tasks(export_mode: str) -> tuple[str, ...]:
    if export_mode == "door":
        return ("door",)
    if export_mode == "vehicle":
        return ("vehicle",)
    return ("door", "vehicle")


def _task_classes(task: str) -> tuple[str, ...]:
    return DOOR_CLASSES if task == "door" else VEHICLE_CLASSES


def _crop_task_label(crop: TrainingCrop, task: str) -> str | None:
    return crop.label if task == "door" else crop.vehicle_label


def _task_label(candidate: Candidate, task: str) -> str | None:
    return _crop_task_label(candidate.crop, task)


def _task_candidate_is_eligible(candidate: Candidate, task: str) -> bool:
    if task == "vehicle" and candidate.crop.label == "bad":
        return False
    return _task_label(candidate, task) in _task_classes(task)


def _candidate_label_signature(candidate: Candidate, export_mode: str) -> str:
    if export_mode == "door":
        return f"door:{candidate.crop.label}"
    if export_mode == "vehicle":
        return f"vehicle:{candidate.crop.vehicle_label}"
    return f"door:{candidate.crop.label}|vehicle:{candidate.crop.vehicle_label}"


def _directory_layout(export_mode: str) -> str:
    if export_mode == "separate":
        return "<task>/<split>/<class>/<image>.jpg"
    if export_mode == "multitask":
        return "<split>/images/<image>.jpg with masked targets in manifest.csv"
    return "<split>/<class>/<image>.jpg"


def _manifest_row(
    candidate: Candidate,
    relative_path: Path,
    split: str,
    *,
    task: str,
    label: str,
    door_label_valid: bool | None = None,
    vehicle_label_valid: bool | None = None,
) -> dict[str, object]:
    prediction = candidate.prediction
    if door_label_valid is None:
        door_label_valid = task == "door" and candidate.crop.label in DOOR_CLASSES
    if vehicle_label_valid is None:
        vehicle_label_valid = task == "vehicle" and candidate.crop.vehicle_label in VEHICLE_CLASSES
    return {
        "relative_path": relative_path.as_posix(),
        "task": task,
        "label": label,
        "door_label": candidate.crop.label or "",
        "door_label_valid": door_label_valid,
        "vehicle_label": candidate.crop.vehicle_label or "",
        "vehicle_label_valid": vehicle_label_valid,
        "split": split,
        "crop_id": candidate.crop.id,
        "camera_id": candidate.camera.id,
        "camera_external_id": candidate.camera.unifi_camera_id,
        "camera_name": candidate.camera.name,
        "door_id": candidate.room.id,
        "door_number": candidate.room.room_id,
        "door_name": candidate.room.name,
        "captured_at": candidate.snapshot.captured_at.isoformat(),
        "predicted_class": prediction.predicted_state if prediction else "",
        "confidence": prediction.confidence if prediction else "",
        "closed_probability": prediction.closed_probability if prediction else "",
        "open_probability": prediction.open_probability if prediction else "",
        "model_version": prediction.model_version if prediction else "",
        "review_status": "operator_verified",
        "review_source": candidate.crop.label_source or "legacy_manual",
        "reviewed_at": candidate.crop.labeled_at.isoformat() if candidate.crop.labeled_at else "",
        "vehicle_review_source": candidate.crop.vehicle_label_source or "",
        "vehicle_reviewed_at": (
            candidate.crop.vehicle_labeled_at.isoformat()
            if candidate.crop.vehicle_labeled_at
            else ""
        ),
        "selection_reasons": "|".join(dict.fromkeys(candidate.selection_reasons)),
        "edge_case_tags": "|".join(candidate.edge_tags),
        "sha256": candidate.sha256,
        "perceptual_hash": (
            f"{candidate.perceptual_hash:016x}" if candidate.perceptual_hash is not None else ""
        ),
        "mean_brightness": (
            candidate.mean_brightness if candidate.mean_brightness is not None else ""
        ),
        "glare_fraction": candidate.glare_fraction if candidate.glare_fraction is not None else "",
        "blur_score": candidate.blur_score if candidate.blur_score is not None else "",
        "source_crop_path": candidate.crop.image_path,
    }


def _perceptual_distance(first: int | None, second: int | None) -> int:
    if first is None or second is None:
        return 65
    return (first ^ second).bit_count()


def _candidate_order(candidate: Candidate) -> tuple[datetime, int]:
    return candidate.snapshot.captured_at, candidate.crop.id


def _group_key(snapshot: CameraSnapshot) -> str:
    captured_at = snapshot.captured_at
    return f"camera-{snapshot.camera_id}:{captured_at:%Y-%m-%d}:{captured_at.hour:02d}"


def _write_manifest(export_root: Path, rows: list[dict[str, object]]) -> None:
    with (export_root / "manifest.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _media_disk_path(image_path: str) -> Path:
    if not image_path.startswith("/media/"):
        return Path("/__invalid_media_path__")
    destination = (settings.media_root / image_path.removeprefix("/media/")).resolve()
    try:
        destination.relative_to(settings.media_root.resolve())
    except ValueError:
        return Path("/__invalid_media_path__")
    return destination


def _media_url(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(settings.media_root.resolve())
    except ValueError as exc:
        raise DatasetExportError("DATASET_EXPORT_DIR must be inside MEDIA_ROOT") from exc
    return f"/media/{relative.as_posix()}"


def _dataset_readme(export_mode: str) -> str:
    return f"""# Curated Garage Image Classification Dataset

Export mode: `{export_mode}`. Door classes are `open`, `closed`, and `partial`. Vehicle classes are
`present` and `absent`. `not_observable`, `unsure`, and `bad` labels are never treated as ordinary
classification targets. Multi-task exports keep per-head validity flags in `manifest.csv`; training
must mask the loss for any target whose validity flag is false.

The exporter prioritizes corrected model mistakes, low-confidence predictions, and automatically
detected dark, glare, or blurry scenes. It retains a deterministic sample of routine images and
removes exact and visually similar consecutive images.

`manifest.csv` records source camera and door IDs, capture time, the model prediction and
probabilities, model version, review status, selection reasons, image hashes, and visual-quality
signals. `dataset.json` records the exact curation settings and counts for reproducibility.

The test directory is a persistent benchmark. Its crop IDs and camera/hour groups are stored in the
export root's hidden `.fixed_test_benchmark.json` file. Later exports reuse those exact test images;
new reviewed images enter only train or validation. Back up that benchmark file with the media and
database. Do not train on the test directory.
"""
