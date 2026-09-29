from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import (
    Base,
    Camera,
    CameraSnapshot,
    DetectionEvent,
    Room,
    TrainingCrop,
    TrainingLabelBatch,
)


def test_camera_room_flow(tmp_path) -> None:
    settings.camera_snapshot_dir = tmp_path / "camera_snapshots"
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with session_local() as db:
        camera = Camera(name="Front", unifi_camera_id="protect-camera-1")
        db.add(camera)
        db.commit()
        db.refresh(camera)
        camera_id = camera.id

    assert client.post("/api/cameras/", json={"name": "Manual"}).status_code == 405

    room_response = client.post(
        "/api/rooms/",
        json={"room_id": 101, "camera_id": camera_id, "name": "Room 101"},
    )
    assert room_response.status_code == 201
    assert room_response.json()["room_id"] == 101
    room_pk = room_response.json()["id"]

    assert client.get("/api/cameras/").json()[0]["name"] == "Front"
    assert client.get("/api/rooms/").json()[0]["name"] == "Room 101"

    roi_response = client.patch(
        f"/api/rooms/{room_pk}",
        json={"roi_x": 10, "roi_y": 20, "roi_width": 300, "roi_height": 180},
    )
    assert roi_response.status_code == 200
    assert roi_response.json()["roi_width"] == 300
    assert roi_response.json()["roi_height"] == 180

    update_response = client.patch(
        f"/api/cameras/{camera_id}",
        json={
            "name": "Front Updated",
            "location": "Lobby",
            "enabled": False,
            "automatic_snapshots": True,
            "snapshot_image_path": "/tmp/front.jpg",
            "last_error": "offline",
        },
    )
    assert update_response.status_code == 200
    updated_camera = update_response.json()
    assert updated_camera["name"] == "Front Updated"
    assert updated_camera["enabled"] is False
    assert updated_camera["automatic_snapshots"] is True
    assert updated_camera["snapshot_image_path"] == "/tmp/front.jpg"

    success, uploaded_png = cv2.imencode(
        ".png", np.full((600, 800, 3), 180, dtype=np.uint8)
    )
    assert success
    upload_response = client.post(
        f"/api/cameras/{camera_id}/snapshot-image",
        files={"image": ("camera.png", uploaded_png.tobytes(), "image/png")},
    )
    assert upload_response.status_code == 200
    uploaded_camera = upload_response.json()
    assert uploaded_camera["snapshot_image_path"].startswith("/media/camera_snapshots/")
    stored_image = cv2.imread(
        str(settings.camera_snapshot_dir / uploaded_camera["snapshot_image_path"].rsplit("/", 1)[-1])
    )
    assert stored_image.shape[:2] == (1080, 1920)
    assert uploaded_camera["last_snapshot_at"] is not None
    assert len(client.get("/api/camera-snapshots/").json()) == 1

    with session_local() as db:
        snapshot = db.query(CameraSnapshot).one()
        crop = TrainingCrop(
            snapshot_id=snapshot.id,
            room_id=room_pk,
            image_path="/media/training_crops/test.jpg",
            roi_x=10,
            roi_y=20,
            roi_width=300,
            roi_height=180,
        )
        db.add(crop)
        db.flush()
        db.add(
            DetectionEvent(
                training_crop_id=crop.id,
                room_id=room_pk,
                snapshot_id=snapshot.id,
                predicted_state="open",
                confidence=0.91,
                closed_probability=0.09,
                open_probability=0.91,
                model_version="test-model",
            )
        )
        db.commit()

    crop_response = client.post("/api/training/crops/generate")
    assert crop_response.status_code == 200
    assert crop_response.json()["log_entries"] == []

    dashboard_rooms = client.get("/api/dashboard/rooms")
    assert dashboard_rooms.status_code == 200
    assert dashboard_rooms.json() == [
        {
            "id": room_pk,
            "room_number": 101,
            "current_state": "unknown",
            "current_confidence": None,
            "last_detected_state": None,
            "last_detected_confidence": None,
            "last_detection_at": None,
            "latest_crop_image_path": "/media/training_crops/test.jpg",
        }
    ]

    unlabeled_response = client.get("/api/training/crops/unlabeled")
    assert unlabeled_response.status_code == 200
    assert unlabeled_response.json()["total"] == 1
    unlabeled_crop = unlabeled_response.json()["items"][0]
    assert unlabeled_crop["room_number"] == 101
    assert unlabeled_crop["camera_name"] == "Front Updated"
    assert unlabeled_crop["preliminary_label"] == "open"
    assert unlabeled_crop["preliminary_confidence"] == 0.91
    assert unlabeled_crop["door_label"] is None
    assert unlabeled_crop["vehicle_label"] is None
    assert client.get("/api/training/crops/unlabeled?room_number=101").json()["total"] == 1
    assert client.get("/api/training/crops/unlabeled?room_number=999").json()["total"] == 0
    assert client.get("/api/training/crops/unlabeled?preliminary_label=open").json()["total"] == 1
    assert client.get("/api/training/crops/unlabeled?preliminary_label=closed").json()["total"] == 0
    assert client.get("/api/training/crops/unlabeled?preliminary_label=unknown").status_code == 422
    room_options = client.get("/api/training/crops/unlabeled/rooms").json()
    assert room_options == [{"room_number": 101, "room_name": "Room 101", "count": 1}]
    partial_response = client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"label": "partial"},
    )
    assert partial_response.status_code == 200
    assert partial_response.json() == {
        "id": unlabeled_crop["id"],
        "label": "partial",
        "vehicle_label": None,
    }

    label_response = client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"label": "open"},
    )
    assert label_response.status_code == 200
    assert label_response.json()["label"] == "open"
    assert client.get("/api/training/crops/unlabeled").json()["total"] == 1
    assert client.get("/api/training/crops/unlabeled?door_label=open").json()["total"] == 1
    assert client.get("/api/training/crops/unlabeled?door_label=missing").json()["total"] == 0
    assert client.get("/api/training/crops/unlabeled?vehicle_label=missing").json()["total"] == 1

    vehicle_response = client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"vehicle_label": "present"},
    )
    assert vehicle_response.status_code == 200
    assert vehicle_response.json()["vehicle_label"] == "present"
    assert client.get("/api/training/crops/unlabeled").json()["total"] == 0
    assert client.get("/api/training/crops/unlabeled?vehicle_label=present").json()["total"] == 1
    progress = client.get("/api/training/crops/label-progress").json()
    assert progress["total"] == 1
    assert progress["door_labeled"] == 1
    assert progress["vehicle_labeled"] == 1
    assert progress["fully_labeled"] == 1
    assert progress["needs_review"] == 0

    vehicle_undo = client.post(
        "/api/training/crops/labels/clear",
        json={"crop_ids": [unlabeled_crop["id"]], "dimension": "vehicle"},
    )
    assert vehicle_undo.status_code == 200
    assert vehicle_undo.json()["dimension"] == "vehicle"
    assert client.get("/api/training/crops/unlabeled").json()["total"] == 1

    closed_response = client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"label": "closed"},
    )
    assert closed_response.status_code == 200
    assert closed_response.json()["vehicle_label"] == "not_observable"
    assert client.get("/api/training/crops/unlabeled").json()["total"] == 0

    reopened_response = client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"label": "open"},
    )
    assert reopened_response.status_code == 200
    assert reopened_response.json()["vehicle_label"] is None
    assert client.get("/api/training/crops/unlabeled").json()["total"] == 1

    client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"label": "closed"},
    )
    client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"vehicle_label": "absent"},
    )
    manual_vehicle_preserved = client.patch(
        f"/api/training/crops/{unlabeled_crop['id']}/label",
        json={"label": "open"},
    )
    assert manual_vehicle_preserved.json()["vehicle_label"] == "absent"
    client.post(
        "/api/training/crops/labels/clear",
        json={"crop_ids": [unlabeled_crop["id"]], "dimension": "vehicle"},
    )

    undo_response = client.delete(f"/api/training/crops/{unlabeled_crop['id']}/label")
    assert undo_response.status_code == 200
    assert undo_response.json()["label"] is None
    assert client.get("/api/training/crops/unlabeled").json()["total"] == 1
    assert client.post("/api/training/dataset/export").status_code == 400

    config_response = client.put(
        "/api/unifi/config",
        json={"console_id": "console-from-dashboard"},
    )
    assert config_response.status_code == 200
    assert config_response.json()["console_id"] == "console-from-dashboard"
    assert client.get("/api/unifi/config").json()["console_id"] == "console-from-dashboard"

    pulse_config = client.put(
        "/api/room-pulse/config",
        json={
            "enabled": False,
            "endpoint_url": "https://receiver.example.test/rooms",
            "public_base_url": "https://garage.example.test",
            "interval_seconds": 90,
            "send_on_change": True,
            "include_image_url": True,
            "bearer_token": "test-secret",
            "timeout_seconds": 5,
        },
    )
    assert pulse_config.status_code == 200
    assert pulse_config.json()["token_configured"] is True
    assert "bearer_token" not in pulse_config.json()
    assert client.get("/api/room-pulse/config").json()["interval_seconds"] == 90
    invalid_pulse = client.put(
        "/api/room-pulse/config",
        json={"enabled": True, "interval_seconds": 60, "timeout_seconds": 10},
    )
    assert invalid_pulse.status_code == 422

    app.dependency_overrides.clear()


def test_page_navigation() -> None:
    client = TestClient(app)

    dashboard_response = client.get("/dashboard")
    assert dashboard_response.status_code == 200
    assert "<h1>Dashboard</h1>" in dashboard_response.text
    assert 'id="dashboard-room-rows"' in dashboard_response.text
    assert 'class="room-status-grid"' in dashboard_response.text
    assert 'class="shell dashboard-shell"' in dashboard_response.text
    assert 'data-collapsible-id="dashboard-rooms"' in dashboard_response.text
    assert "/static/js/collapsible_sections.js" in dashboard_response.text
    assert "/static/js/room_dashboard.js" in dashboard_response.text
    assert 'href="/cameras"' in dashboard_response.text
    assert 'href="/training"' in dashboard_response.text
    assert 'href="/room-pulse"' in dashboard_response.text
    assert client.get("/").text == dashboard_response.text

    cameras_response = client.get("/cameras")
    assert cameras_response.status_code == 200
    assert 'href="/dashboard"' in cameras_response.text
    assert 'href="/training"' in cameras_response.text
    assert 'data-collapsible-id="recent-snapshots" data-collapsed="true"' in cameras_response.text
    assert 'data-collapsible-id="camera-list"' in cameras_response.text
    assert 'data-collapsible-id="camera-rooms"' in cameras_response.text
    assert "/static/js/collapsible_sections.js" in cameras_response.text
    assert 'aria-current="page"' in cameras_response.text

    training_response = client.get("/training")
    assert training_response.status_code == 200
    assert "<h1>Training</h1>" in training_response.text
    assert 'href="/dashboard"' in training_response.text
    assert 'href="/cameras"' in training_response.text
    assert 'id="generate-training-crops"' in training_response.text
    assert 'id="crop-generation-log"' in training_response.text
    assert 'id="crop-generation-log-output"' in training_response.text
    assert 'class="generation-log-chevron"' in training_response.text
    assert 'id="labeling-workspace"' in training_response.text
    assert 'data-crop-label="open"' in training_response.text
    assert 'data-crop-label="closed"' in training_response.text
    assert 'data-crop-label="partial"' in training_response.text
    assert 'data-vehicle-label="present"' in training_response.text
    assert 'data-vehicle-label="absent"' in training_response.text
    assert 'data-vehicle-label="not_observable"' in training_response.text
    assert 'data-crop-label="bad"' in training_response.text
    assert 'id="undo-crop-label"' in training_response.text
    assert 'id="export-training-dataset"' in training_response.text
    assert 'id="download-training-dataset"' in training_response.text
    assert 'id="export-low-confidence"' in training_response.text
    assert 'id="export-probability-margin"' in training_response.text
    assert 'id="export-duplicate-window"' in training_response.text
    assert 'id="export-include-misclassified"' in training_response.text
    assert 'id="refresh-dataset-preview"' in training_response.text
    assert 'id="export-mode"' in training_response.text
    assert 'id="dataset-preview-task-counts"' in training_response.text
    assert 'id="export-minimum-class-percent"' in training_response.text
    assert 'id="export-minimum-class-value"' in training_response.text
    assert 'id="export-vehicle-minimum-class-percent"' in training_response.text
    assert 'id="export-captured-from"' in training_response.text
    assert 'id="export-captured-through"' in training_response.text
    assert 'id="dataset-help-dialog"' in training_response.text
    assert 'id="dataset-help-title"' in training_response.text
    assert training_response.text.count("data-dataset-help=") == 15
    assert 'id="unlabeled-room-filter"' in training_response.text
    assert 'id="unlabeled-status-filter"' in training_response.text
    assert 'id="door-label-filter"' in training_response.text
    assert 'id="vehicle-label-filter"' in training_response.text
    assert 'id="label-progress-complete"' in training_response.text
    assert 'id="active-crop-preliminary"' in training_response.text
    assert 'id="confirm-preliminary-label"' in training_response.text
    assert 'data-crop-run-label="open"' in training_response.text
    assert 'data-crop-run-label="closed"' in training_response.text
    assert 'data-crop-run-label="partial"' in training_response.text
    assert 'data-vehicle-run-label="present"' in training_response.text
    assert 'data-collapsible-id="batch-approval"' in training_response.text
    assert 'id="batch-confidence-threshold"' in training_response.text
    assert 'id="batch-room-filter"' in training_response.text
    assert 'id="batch-approval-dialog"' in training_response.text
    assert 'id="undo-label-batch"' in training_response.text
    assert 'data-collapsible-id="training-crops"' in training_response.text
    assert 'data-collapsible-id="unlabeled-crops"' in training_response.text
    assert 'data-collapsible-id="dataset-export"' in training_response.text
    assert "/static/js/collapsible_sections.js" in training_response.text
    assert "/static/js/training.js" in training_response.text

    pulse_response = client.get("/room-pulse")
    assert pulse_response.status_code == 200
    assert "<h1>Room Pulse</h1>" in pulse_response.text
    assert 'aria-current="page"' in pulse_response.text
    assert 'id="pulse-config-form"' in pulse_response.text
    assert 'id="pulse-send-test"' in pulse_response.text
    assert 'id="pulse-history-body"' in pulse_response.text
    assert "/static/js/room_pulse.js" in pulse_response.text


def test_batch_approval_preview_approve_and_undo() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with session_local() as db:
        camera = Camera(name="Batch Camera", unifi_camera_id="batch-camera")
        db.add(camera)
        db.flush()
        rooms = {
            number: Room(room_id=number, camera_id=camera.id, name=f"Room {number}")
            for number in (101, 102)
        }
        db.add_all(rooms.values())
        db.flush()
        predictions = [
            (101, "open", 0.995),
            (101, "closed", 0.991),
            (101, "unknown", 0.999),
            (101, "open", 0.900),
            (102, "open", 0.997),
        ]
        crop_ids = []
        started_at = datetime(2026, 7, 15, tzinfo=timezone.utc)
        for index, (room_number, state, confidence) in enumerate(predictions):
            snapshot = CameraSnapshot(
                camera_id=camera.id,
                image_path=f"/media/camera-captures/batch-{index}.jpg",
                captured_at=started_at + timedelta(minutes=index),
            )
            db.add(snapshot)
            db.flush()
            crop = TrainingCrop(
                snapshot_id=snapshot.id,
                room_id=rooms[room_number].id,
                image_path=f"/media/training-crops/batch-{index}.jpg",
                roi_x=0,
                roi_y=0,
                roi_width=100,
                roi_height=100,
            )
            db.add(crop)
            db.flush()
            crop_ids.append(crop.id)
            db.add(
                DetectionEvent(
                    training_crop_id=crop.id,
                    room_id=rooms[room_number].id,
                    snapshot_id=snapshot.id,
                    predicted_state=state,
                    confidence=confidence,
                    closed_probability=1 - confidence if state == "open" else confidence,
                    open_probability=confidence if state == "open" else 1 - confidence,
                    model_version="batch-test-model.pt",
                )
            )
        db.commit()

    payload = {"confidence_threshold": 0.99, "room_number": 101}
    preview = client.post("/api/training/labels/batches/preview", json=payload)
    assert preview.status_code == 200
    assert preview.json() == {
        "confidence_threshold": 0.99,
        "room_number": 101,
        "total_unlabeled": 4,
        "eligible": 2,
        "predicted_open": 1,
        "predicted_closed": 1,
        "remaining_manual": 2,
        "latest_batch_id": None,
        "latest_batch_count": 0,
        "can_undo": False,
    }

    approval = client.post("/api/training/labels/batches", json=payload)
    assert approval.status_code == 200
    assert approval.json()["images_approved"] == 2
    assert approval.json()["model_versions"] == ["batch-test-model.pt"]
    batch_id = approval.json()["batch_id"]

    with session_local() as db:
        first, second, unknown, low, other_room = [db.get(TrainingCrop, crop_id) for crop_id in crop_ids]
        assert (first.label, first.label_source, first.label_batch_id) == (
            "open",
            "batch",
            batch_id,
        )
        assert (second.label, second.label_source) == ("closed", "batch")
        assert (second.vehicle_label, second.vehicle_label_source) == (
            "not_observable",
            "door_closed_rule",
        )
        assert unknown.label is None
        assert low.label is None
        assert other_room.label is None
        audit = db.get(TrainingLabelBatch, batch_id)
        assert audit.confidence_threshold == 0.99
        assert audit.images_approved == 2

    manual_override = client.patch(
        f"/api/training/crops/{crop_ids[0]}/label", json={"label": "closed"}
    )
    assert manual_override.status_code == 200
    undo = client.delete("/api/training/labels/batches/latest")
    assert undo.status_code == 200
    assert undo.json() == {"batch_id": batch_id, "labels_reverted": 1}

    with session_local() as db:
        first = db.get(TrainingCrop, crop_ids[0])
        second = db.get(TrainingCrop, crop_ids[1])
        audit = db.get(TrainingLabelBatch, batch_id)
        assert (first.label, first.label_source, first.label_batch_id) == (
            "closed",
            "manual",
            None,
        )
        assert (second.label, second.label_source, second.label_batch_id) == (None, None, None)
        assert second.vehicle_label is None
        assert audit.undone_at is not None

    assert client.delete("/api/training/labels/batches/latest").status_code == 404

    run_response = client.patch(
        "/api/training/crops/label-run",
        json={"start_crop_id": crop_ids[1], "label": "open", "count": 8},
    )
    assert run_response.status_code == 200
    assert run_response.json() == {
        "crop_ids": crop_ids[1:4],
        "label": "open",
        "vehicle_label": None,
        "count": 3,
    }
    with session_local() as db:
        assert [db.get(TrainingCrop, crop_id).label for crop_id in crop_ids] == [
            "closed",
            "open",
            "open",
            "open",
            None,
        ]
        assert all(
            db.get(TrainingCrop, crop_id).label_source == "manual"
            for crop_id in crop_ids[1:4]
        )

    clear_response = client.post(
        "/api/training/crops/labels/clear",
        json={"crop_ids": run_response.json()["crop_ids"]},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["count"] == 3
    with session_local() as db:
        assert all(db.get(TrainingCrop, crop_id).label is None for crop_id in crop_ids[1:4])

    filtered_run = client.patch(
        "/api/training/crops/label-run",
        json={
            "start_crop_id": crop_ids[1],
            "label": "open",
            "count": 8,
            "preliminary_label": "closed",
        },
    )
    assert filtered_run.status_code == 200
    assert filtered_run.json()["crop_ids"] == [crop_ids[1]]

    vehicle_run = client.patch(
        "/api/training/crops/label-run",
        json={
            "start_crop_id": crop_ids[1],
            "vehicle_label": "not_observable",
            "count": 2,
        },
    )
    assert vehicle_run.status_code == 200
    assert vehicle_run.json() == {
        "crop_ids": crop_ids[1:3],
        "label": None,
        "vehicle_label": "not_observable",
        "count": 2,
    }
    with session_local() as db:
        assert [db.get(TrainingCrop, crop_id).vehicle_label for crop_id in crop_ids[1:3]] == [
            "not_observable",
            "not_observable",
        ]

    clear_vehicle = client.post(
        "/api/training/crops/labels/clear",
        json={"crop_ids": crop_ids[1:3], "dimension": "vehicle"},
    )
    assert clear_vehicle.status_code == 200
    assert clear_vehicle.json()["dimension"] == "vehicle"
    with session_local() as db:
        assert all(
            db.get(TrainingCrop, crop_id).vehicle_label is None
            for crop_id in crop_ids[1:3]
        )

    assert (
        client.patch(
            f"/api/training/crops/{crop_ids[0]}/label",
            json={"label": "open", "vehicle_label": "present"},
        ).status_code
        == 422
    )
    app.dependency_overrides.clear()
