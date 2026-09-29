import csv
import json
from datetime import date, datetime, timezone
from zipfile import ZipFile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.models import Base, Camera, CameraSnapshot, Room, TrainingCrop
from app.schemas import DatasetExportRequest
from app.services.dataset_export import (
    CLASSES,
    DOOR_CLASSES,
    SPLITS,
    VEHICLE_CLASSES,
    Candidate,
    _balance_candidates,
    export_classification_dataset,
    preview_classification_dataset,
)


def test_export_classification_dataset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "media_root", tmp_path)
    monkeypatch.setattr(settings, "dataset_export_dir", tmp_path / "dataset_exports")
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
        camera_id = camera.id
        room_id = room.id

        for index, label in enumerate(("open", "closed", "partial", "bad")):
            source = crop_dir / f"crop_{index}.jpg"
            source.write_bytes(f"image-{index}".encode())
            snapshot = CameraSnapshot(
                camera_id=camera.id,
                image_path=f"/media/source_{index}.jpg",
                captured_at=datetime(2026, 7, 14, index * 6, tzinfo=timezone.utc),
            )
            db.add(snapshot)
            db.flush()
            db.add(
                TrainingCrop(
                    snapshot_id=snapshot.id,
                    room_id=room.id,
                    image_path=f"/media/training_crops/{source.name}",
                    roi_x=0,
                    roi_y=0,
                    roi_width=100,
                    roi_height=100,
                    label=label,
                )
            )
        db.commit()

        options = DatasetExportRequest(
            random_sample_percent=100,
            minimum_class_percent=0,
        )
        preview = preview_classification_dataset(db, options)
        assert preview.candidates_considered == 3
        assert preview.queried_counts == {"open": 1, "closed": 1, "partial": 1}
        assert preview.selected_images == 3
        assert sum(
            sum(class_counts.values()) for class_counts in preview.split_counts.values()
        ) == 3
        result = export_classification_dataset(db, options)

    assert result.images_exported == 3
    assert result.excluded_bad == 1
    assert sum(sum(labels.values()) for labels in result.counts.values()) == 3
    export_root = tmp_path / result.export_path.removeprefix("/media/")
    for split in SPLITS:
        for label in CLASSES:
            assert (export_root / split / label).is_dir()

    with (export_root / "manifest.csv").open(newline="", encoding="utf-8") as manifest:
        rows = list(csv.DictReader(manifest))
    assert {row["label"] for row in rows} == {"open", "closed", "partial"}
    assert {row["task"] for row in rows} == {"door"}
    assert {row["split"] for row in rows} == {"train", "val", "test"}
    assert all(row["review_status"] == "operator_verified" for row in rows)
    assert all("sha256" in row and "model_version" in row for row in rows)
    fixed_test_ids = {int(row["crop_id"]) for row in rows if row["split"] == "test"}

    metadata = json.loads((export_root / "dataset.json").read_text(encoding="utf-8"))
    assert metadata["format_version"] == 3
    assert metadata["export_mode"] == "door"
    assert set(metadata["benchmark"]["crop_ids"]) == fixed_test_ids

    with session_local() as db:
        source = crop_dir / "crop_new.jpg"
        source.write_bytes(b"new-production-image")
        snapshot = CameraSnapshot(
            camera_id=camera_id,
            image_path="/media/source_new.jpg",
            captured_at=datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
        )
        db.add(snapshot)
        db.flush()
        new_crop = TrainingCrop(
            snapshot_id=snapshot.id,
            room_id=room_id,
            image_path="/media/training_crops/crop_new.jpg",
            roi_x=0,
            roi_y=0,
            roi_width=100,
            roi_height=100,
            label="open",
        )
        db.add(new_crop)
        db.commit()
        db.refresh(new_crop)
        new_crop_id = new_crop.id
        second = export_classification_dataset(
            db,
            DatasetExportRequest(
                random_sample_percent=100,
                minimum_class_percent=0,
            ),
        )

    second_root = tmp_path / second.export_path.removeprefix("/media/")
    with (second_root / "manifest.csv").open(newline="", encoding="utf-8") as manifest:
        second_rows = list(csv.DictReader(manifest))
    second_test_ids = {
        int(row["crop_id"]) for row in second_rows if row["split"] == "test"
    }
    assert second.benchmark_created is False
    assert second_test_ids == fixed_test_ids
    new_crop_row = next(row for row in second_rows if int(row["crop_id"]) == new_crop_id)
    assert new_crop_row["split"] != "test"

    with session_local() as db:
        dated_preview = preview_classification_dataset(
            db,
            DatasetExportRequest(
                captured_from=date(2026, 7, 16),
                captured_through=date(2026, 7, 16),
                random_sample_percent=100,
                minimum_class_percent=0,
            ),
        )
    assert dated_preview.candidates_considered == 1
    assert dated_preview.queried_counts == {"open": 1, "closed": 0, "partial": 0}

    archive = tmp_path / result.archive_url.removeprefix("/media/")
    assert archive.is_file()
    with ZipFile(archive) as zipped:
        names = zipped.namelist()
    assert any(name.endswith("manifest.csv") for name in names)
    assert any("/train/" in name for name in names)


def test_balance_candidates_enforces_minimum_class_share(tmp_path) -> None:
    camera = Camera(id=1, name="Garage", unifi_camera_id="camera-1")
    room = Room(id=1, room_id=101, camera_id=1, name="Room 101")
    candidates = []
    labels = ["open"] * 8 + ["closed"] * 3 + ["partial"] * 2
    for index, label in enumerate(labels, start=1):
        snapshot = CameraSnapshot(
            id=index,
            camera_id=1,
            image_path=f"/media/source-{index}.jpg",
            captured_at=datetime(2026, 7, 14, index, tzinfo=timezone.utc),
        )
        crop = TrainingCrop(
            id=index,
            snapshot_id=index,
            room_id=1,
            image_path=f"/media/crop-{index}.jpg",
            roi_x=0,
            roi_y=0,
            roi_width=100,
            roi_height=100,
            label=label,
        )
        candidates.append(
            Candidate(
                crop=crop,
                snapshot=snapshot,
                camera=camera,
                room=room,
                prediction=None,
                source=tmp_path / f"crop-{index}.jpg",
                sha256=f"{index:064x}",
                perceptual_hash=index,
                mean_brightness=100,
                glare_fraction=0,
                blur_score=100,
            )
        )

    balanced, removed = _balance_candidates(candidates, set(), 40)
    counts = {label: sum(candidate.crop.label == label for candidate in balanced) for label in CLASSES}
    assert counts == {"open": 5, "closed": 3, "partial": 2}
    assert removed == 3


def test_vehicle_separate_and_multitask_exports(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "media_root", tmp_path)
    monkeypatch.setattr(settings, "dataset_export_dir", tmp_path / "dataset_exports")
    crop_dir = tmp_path / "training_crops"
    crop_dir.mkdir()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    labels = [
        ("open", "present"),
        ("closed", "not_observable"),
        ("partial", "present"),
        ("open", "absent"),
        ("closed", "absent"),
        ("open", "unsure"),
    ]
    with session_local() as db:
        camera = Camera(name="Garage", unifi_camera_id="camera-multitask")
        db.add(camera)
        db.flush()
        room = Room(room_id=201, camera_id=camera.id, name="Room 201")
        db.add(room)
        db.flush()
        for index, (door_label, vehicle_label) in enumerate(labels):
            source = crop_dir / f"dual_{index}.jpg"
            source.write_bytes(f"dual-image-{index}".encode())
            snapshot = CameraSnapshot(
                camera_id=camera.id,
                image_path=f"/media/source-dual-{index}.jpg",
                captured_at=datetime(2026, 7, 10 + index, 12, tzinfo=timezone.utc),
            )
            db.add(snapshot)
            db.flush()
            db.add(
                TrainingCrop(
                    snapshot_id=snapshot.id,
                    room_id=room.id,
                    image_path=f"/media/training_crops/{source.name}",
                    roi_x=0,
                    roi_y=0,
                    roi_width=100,
                    roi_height=100,
                    label=door_label,
                    label_source="manual",
                    vehicle_label=vehicle_label,
                    vehicle_label_source="manual",
                )
            )
        db.commit()

        vehicle_options = DatasetExportRequest(
            export_mode="vehicle",
            random_sample_percent=100,
            minimum_class_percent=0,
            vehicle_minimum_class_percent=0,
        )
        vehicle_preview = preview_classification_dataset(db, vehicle_options)
        assert vehicle_preview.queried_task_counts == {
            "vehicle": {"present": 2, "absent": 2}
        }
        vehicle_result = export_classification_dataset(db, vehicle_options)

        separate_result = export_classification_dataset(
            db,
            DatasetExportRequest(
                export_mode="separate",
                random_sample_percent=100,
                minimum_class_percent=0,
                vehicle_minimum_class_percent=0,
            ),
        )
        multitask_result = export_classification_dataset(
            db,
            DatasetExportRequest(
                export_mode="multitask",
                random_sample_percent=100,
                minimum_class_percent=0,
                vehicle_minimum_class_percent=0,
            ),
        )

    vehicle_root = tmp_path / vehicle_result.export_path.removeprefix("/media/")
    assert set(vehicle_result.task_counts) == {"vehicle"}
    for split in SPLITS:
        for label in VEHICLE_CLASSES:
            assert (vehicle_root / split / label).is_dir()

    separate_root = tmp_path / separate_result.export_path.removeprefix("/media/")
    assert set(separate_result.task_counts) == {"door", "vehicle"}
    for split in SPLITS:
        for label in DOOR_CLASSES:
            assert (separate_root / "door" / split / label).is_dir()
        for label in VEHICLE_CLASSES:
            assert (separate_root / "vehicle" / split / label).is_dir()
    with (separate_root / "manifest.csv").open(newline="", encoding="utf-8") as manifest:
        separate_rows = list(csv.DictReader(manifest))
    rows_by_crop: dict[str, list[dict[str, str]]] = {}
    for row in separate_rows:
        rows_by_crop.setdefault(row["crop_id"], []).append(row)
    for crop_rows in rows_by_crop.values():
        if len(crop_rows) == 2:
            assert {row["task"] for row in crop_rows} == {"door", "vehicle"}
            assert len({row["split"] for row in crop_rows}) == 1

    multitask_root = tmp_path / multitask_result.export_path.removeprefix("/media/")
    with (multitask_root / "manifest.csv").open(newline="", encoding="utf-8") as manifest:
        multitask_rows = list(csv.DictReader(manifest))
    assert len(multitask_rows) == 6
    assert {row["task"] for row in multitask_rows} == {"multitask"}
    invalid_vehicle = {
        row["vehicle_label"]
        for row in multitask_rows
        if row["vehicle_label_valid"] == "False"
    }
    assert invalid_vehicle == {"not_observable", "unsure"}
    assert all(row["door_label_valid"] == "True" for row in multitask_rows)
    assert all((multitask_root / row["relative_path"]).is_file() for row in multitask_rows)
