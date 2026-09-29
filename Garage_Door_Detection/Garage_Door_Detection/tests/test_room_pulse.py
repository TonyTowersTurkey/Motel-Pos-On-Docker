from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Camera, Room, RoomPulseConfig
from app.services.room_pulse import room_pulse_due, send_room_pulse


def test_room_pulse_sends_room_state_and_audits_delivery() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(202, json={"accepted": True})

    with session_local() as db:
        camera = Camera(name="Garage North", unifi_camera_id="pulse-camera")
        db.add(camera)
        db.flush()
        db.add(
            Room(
                room_id=225,
                camera_id=camera.id,
                name="Room 225",
                current_state="closed",
                current_confidence=0.992,
                last_detected_state="closed",
                last_detected_confidence=0.992,
                last_detection_at=datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc),
                last_confirmed_change_at=datetime(2026, 7, 15, 13, 42, tzinfo=timezone.utc),
            )
        )
        db.add(
            RoomPulseConfig(
                id=1,
                enabled=True,
                endpoint_url="https://receiver.example.test/room-state",
                public_base_url="https://garage.example.test",
                interval_seconds=60,
                send_on_change=True,
                include_image_url=True,
                bearer_token="pulse-token",
                timeout_seconds=5,
            )
        )
        db.commit()

        assert room_pulse_due(db, datetime(2026, 7, 15, 14, 31, tzinfo=timezone.utc)) == (
            "room_state_changed"
        )
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            delivery = send_room_pulse(db, "room_state_changed", client)

        assert delivery.status == "success"
        assert delivery.http_status == 202
        assert delivery.attempt_count == 1
        assert delivery.room_count == 1
        assert delivery.delivered_at is not None
        assert len(requests) == 1
        assert requests[0].headers["Authorization"] == "Bearer pulse-token"
        assert requests[0].headers["X-Room-Pulse-Event"] == delivery.event_id
        payload = __import__("json").loads(requests[0].content)
        assert payload["event_type"] == "room_state_changed"
        assert payload["schema_version"] == "1.0"
        assert payload["room_count"] == 1
        assert payload["rooms"][0]["room_number"] == 225
        assert payload["rooms"][0]["room_name"] == "Room 225"
        assert payload["rooms"][0]["state"] == "closed"
        assert payload["rooms"][0]["confidence"] == 0.992
        assert payload["rooms"][0]["camera_name"] == "Garage North"
        assert "bearer_token" not in delivery.payload

        assert room_pulse_due(db, delivery.delivered_at) is None
