import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DoorState(str, enum.Enum):
    open = "open"
    closed = "closed"
    unknown = "unknown"


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RoomPulseConfig(Base):
    __tablename__ = "room_pulse_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    public_base_url: Mapped[str | None] = mapped_column(Text)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    send_on_change: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_image_url: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bearer_token: Mapped[str | None] = mapped_column(Text)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RoomPulseDelivery(Base):
    __tablename__ = "room_pulse_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    room_count: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unifi_camera_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    automatic_snapshots: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_image_path: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    snapshots: Mapped[list["CameraSnapshot"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )
    rooms: Mapped[list["Room"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan"
    )


class CameraSnapshot(Base):
    __tablename__ = "camera_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    camera: Mapped[Camera] = relationship(back_populates="snapshots")
    training_crops: Mapped[list["TrainingCrop"]] = relationship(
        back_populates="snapshot", cascade="all, delete-orphan"
    )


class Room(Base):
    __tablename__ = "room"
    __table_args__ = (
        CheckConstraint(
            "current_state IN ('open', 'closed', 'unknown')",
            name="ck_room_current_state",
        ),
        CheckConstraint(
            "last_detected_state IS NULL OR last_detected_state IN "
            "('open', 'closed', 'unknown')",
            name="ck_room_last_detected_state",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(Integer, nullable=False)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    roi_x: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    roi_y: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    roi_width: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    roi_height: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_state: Mapped[DoorState] = mapped_column(
        String(20), default=DoorState.unknown, nullable=False
    )
    current_confidence: Mapped[float | None] = mapped_column(Float)
    last_detected_state: Mapped[DoorState | None] = mapped_column(String(20))
    last_detected_confidence: Mapped[float | None] = mapped_column(Float)
    consecutive_match_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_detection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_confirmed_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    camera: Mapped[Camera] = relationship(back_populates="rooms")
    training_crops: Mapped[list["TrainingCrop"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="room", cascade="all, delete-orphan"
    )


class TrainingCrop(Base):
    __tablename__ = "training_crops"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "room_id", name="uq_training_crop_snapshot_room"),
        Index("ix_training_crops_label", "label"),
        Index("ix_training_crops_vehicle_label", "vehicle_label"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("camera_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("room.id", ondelete="CASCADE"), nullable=False
    )
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    roi_x: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_y: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_width: Mapped[int] = mapped_column(Integer, nullable=False)
    roi_height: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(20))
    label_source: Mapped[str | None] = mapped_column(String(20))
    label_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_label_batches.id", ondelete="SET NULL"), index=True
    )
    label_confidence: Mapped[float | None] = mapped_column(Float)
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vehicle_label: Mapped[str | None] = mapped_column(String(20))
    vehicle_label_source: Mapped[str | None] = mapped_column(String(20))
    vehicle_labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    snapshot: Mapped[CameraSnapshot] = relationship(back_populates="training_crops")
    room: Mapped[Room] = relationship(back_populates="training_crops")
    inference_job: Mapped["InferenceJob"] = relationship(
        back_populates="crop", cascade="all, delete-orphan", uselist=False
    )
    detection_events: Mapped[list["DetectionEvent"]] = relationship(
        back_populates="crop", cascade="all, delete-orphan"
    )
    label_batch: Mapped["TrainingLabelBatch | None"] = relationship(back_populates="crops")


class TrainingLabelBatch(Base):
    __tablename__ = "training_label_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    room_number: Mapped[int | None] = mapped_column(Integer)
    images_approved: Mapped[int] = mapped_column(Integer, nullable=False)
    open_approved: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_approved: Mapped[int] = mapped_column(Integer, nullable=False)
    model_versions: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    crops: Mapped[list[TrainingCrop]] = relationship(back_populates="label_batch")


class InferenceJob(Base):
    __tablename__ = "inference_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_inference_job_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    training_crop_id: Mapped[int] = mapped_column(
        ForeignKey("training_crops.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False, index=True
    )
    is_backfill: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    crop: Mapped[TrainingCrop] = relationship(back_populates="inference_job")


class DetectionEvent(Base):
    __tablename__ = "detection_events"
    __table_args__ = (
        CheckConstraint(
            "predicted_state IN ('open', 'closed', 'unknown')",
            name="ck_detection_event_state",
        ),
        Index("ix_detection_events_training_crop_id_id", "training_crop_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    training_crop_id: Mapped[int] = mapped_column(
        ForeignKey("training_crops.id", ondelete="CASCADE"), nullable=False
    )
    room_id: Mapped[int] = mapped_column(
        ForeignKey("room.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("camera_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    predicted_state: Mapped[DoorState] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    closed_probability: Mapped[float] = mapped_column(Float, nullable=False)
    open_probability: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    crop: Mapped[TrainingCrop] = relationship(back_populates="detection_events")
    room: Mapped[Room] = relationship(back_populates="detection_events")
