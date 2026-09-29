import json

import httpx
import cv2
import numpy as np
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, settings
from app.models import Base, Camera, CameraSnapshot, InferenceJob, Room, TrainingCrop
from app.services.camera_capture import (
    capture_all_cameras,
    capture_automatic_cameras,
    sync_unifi_cameras,
)
from app.services.unifi_protect import UnifiCamera, UnifiProtectClient, UnifiProtectError


class FakeProtectClient:
    def list_cameras(self) -> list[UnifiCamera]:
        return [
            UnifiCamera(
                id="protect-camera-1",
                name="Garage East",
                state="CONNECTED",
                model="UVC-G5-Bullet",
            )
        ]

    def get_snapshot(self, camera_id: str) -> bytes:
        assert camera_id == "protect-camera-1"
        success, encoded = cv2.imencode(".jpg", np.zeros((360, 640, 3), dtype=np.uint8))
        assert success
        return encoded.tobytes()


def test_sync_and_capture_unifi_camera(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "media_root", tmp_path)
    monkeypatch.setattr(settings, "camera_capture_dir", tmp_path / "camera_captures")
    monkeypatch.setattr(settings, "training_crop_dir", tmp_path / "training_crops")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with session_local() as db:
        synced = sync_unifi_cameras(db, FakeProtectClient())
        assert len(synced) == 1
        assert synced[0].unifi_camera_id == "protect-camera-1"
        synced[0].automatic_snapshots = True
        db.add(
            Room(
                room_id=101,
                camera_id=synced[0].id,
                name="Garage 101",
                roi_x=100,
                roi_y=200,
                roi_width=300,
                roi_height=400,
            )
        )
        db.commit()

        results = capture_all_cameras(db, FakeProtectClient())
        assert results[0].success is True
        assert results[0].image_path is not None
        stored_image = cv2.imread(
            str(tmp_path / results[0].image_path.removeprefix("/media/"))
        )
        assert stored_image.shape[:2] == (1080, 1920)
        stored_path = tmp_path / results[0].image_path.removeprefix("/media/")
        assert stored_path.parent.relative_to(tmp_path).parts[:2] == (
            "camera_captures",
            "camera_0001",
        )
        metadata = json.loads(stored_path.with_suffix(".json").read_text())
        assert metadata["image_width"] == 1920
        assert metadata["image_height"] == 1080
        assert metadata["camera"]["id"] == synced[0].id
        assert metadata["rooms"][0] == {
            "active": True,
            "id": 1,
            "name": "Garage 101",
            "roi_height": 400,
            "roi_width": 300,
            "roi_x": 100,
            "roi_y": 200,
            "room_id": 101,
        }
        training_crop = db.scalar(select(TrainingCrop))
        assert training_crop is not None
        crop_image = cv2.imread(
            str(tmp_path / training_crop.image_path.removeprefix("/media/"))
        )
        assert crop_image.shape[:2] == (400, 300)
        inference_job = db.scalar(select(InferenceJob))
        assert inference_job is not None
        assert inference_job.status == "queued"
        automatic_results = capture_automatic_cameras(db, FakeProtectClient())
        assert automatic_results[0].success is True
        assert len(list(db.scalars(select(CameraSnapshot)))) == 2
        assert len(list(db.scalars(select(TrainingCrop)))) == 2
        assert len(list(db.scalars(select(InferenceJob)))) == 2

        # Sync is idempotent and updates the existing imported record.
        sync_unifi_cameras(db, FakeProtectClient())
        assert len(list(db.scalars(select(Camera)))) == 1


def test_remote_protect_client_uses_official_connector_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[{"id": "camera/1", "name": "Garage", "state": "CONNECTED"}],
        )

    config = Settings(
        _env_file=None,
        unifi_connection_mode="remote",
        unifi_api_key="test-key",
    )
    client = UnifiProtectClient(config, console_id="console-id")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        cameras = client.list_cameras()
    finally:
        client.close()

    assert cameras[0].id == "camera/1"
    assert requests[0].url == (
        "https://api.ui.com/v1/connector/consoles/console-id/proxy/protect/integration/v1/cameras"
    )
    assert requests[0].headers["X-API-Key"] == "test-key"


def test_snapshot_falls_back_when_high_quality_is_unsupported() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.params.get("highQuality") == "true":
            return httpx.Response(400, json={"code": "bad_request"})
        return httpx.Response(200, content=b"standard-quality-jpeg")

    config = Settings(
        _env_file=None,
        unifi_connection_mode="remote",
        unifi_api_key="test-key",
        unifi_snapshot_high_quality=True,
    )
    client = UnifiProtectClient(config, console_id="console-id")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        snapshot = client.get_snapshot("camera-id")
    finally:
        client.close()

    assert snapshot == b"standard-quality-jpeg"
    assert [request.url.params["highQuality"] for request in requests] == ["true", "false"]


def test_snapshot_explains_protect_server_error_after_quality_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status_code = 400 if request.url.params.get("highQuality") == "true" else 500
        return httpx.Response(status_code, json={"error": "Unexpected error"})

    config = Settings(
        _env_file=None,
        unifi_connection_mode="remote",
        unifi_api_key="test-key",
        unifi_snapshot_high_quality=True,
    )
    client = UnifiProtectClient(config, console_id="console-id")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        try:
            client.get_snapshot("camera-id")
        except UnifiProtectError as exc:
            assert exc.status_code == 500
            assert "could not generate a snapshot" in str(exc)
            assert "RTSPS" in str(exc)
        else:
            raise AssertionError("Expected a UniFi Protect snapshot error")
    finally:
        client.close()
