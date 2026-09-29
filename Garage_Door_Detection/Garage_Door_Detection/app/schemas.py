from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import DoorState


class CameraUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    enabled: bool | None = None
    automatic_snapshots: bool | None = None
    last_snapshot_at: datetime | None = None
    snapshot_image_path: str | None = None
    last_error: str | None = None


class CameraRead(BaseModel):
    id: int
    name: str
    unifi_camera_id: str
    location: str | None = None
    enabled: bool
    automatic_snapshots: bool
    last_snapshot_at: datetime | None = None
    snapshot_image_path: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomCreate(BaseModel):
    room_id: int
    camera_id: int
    name: str
    roi_x: int = Field(default=0, ge=0)
    roi_y: int = Field(default=0, ge=0)
    roi_width: int = Field(default=0, ge=0)
    roi_height: int = Field(default=0, ge=0)
    active: bool = True


class RoomUpdate(BaseModel):
    name: str | None = None
    roi_x: int | None = Field(default=None, ge=0)
    roi_y: int | None = Field(default=None, ge=0)
    roi_width: int | None = Field(default=None, ge=0)
    roi_height: int | None = Field(default=None, ge=0)
    current_state: DoorState | None = None
    current_confidence: float | None = Field(default=None, ge=0, le=1)
    active: bool | None = None


class RoomRead(RoomCreate):
    id: int
    current_state: DoorState
    current_confidence: float | None = None
    last_detected_state: DoorState | None = None
    last_detected_confidence: float | None = None
    consecutive_match_count: int
    last_detection_at: datetime | None = None
    last_confirmed_change_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DashboardRoomRead(BaseModel):
    id: int
    room_number: int
    current_state: DoorState
    current_confidence: float | None = None
    last_detected_state: DoorState | None = None
    last_detected_confidence: float | None = None
    last_detection_at: datetime | None = None
    latest_crop_image_path: str | None = None


class CameraSnapshotCreate(BaseModel):
    camera_id: int
    image_path: str
    captured_at: datetime


class CameraSnapshotRead(CameraSnapshotCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CropGenerationResult(BaseModel):
    snapshots_considered: int
    crops_created: int
    crops_updated: int
    crops_skipped: int
    missing_sources: int
    failed_sources: int
    log_entries: list[str] = Field(default_factory=list)


class TrainingCropRead(BaseModel):
    id: int
    image_path: str
    camera_id: int
    camera_name: str
    room_id: int
    room_number: int
    room_name: str
    captured_at: datetime
    preliminary_label: DoorState | None = None
    preliminary_confidence: float | None = None
    door_label: str | None = None
    vehicle_label: str | None = None


class TrainingCropList(BaseModel):
    total: int
    items: list[TrainingCropRead]


class UnlabeledRoomOption(BaseModel):
    room_number: int
    room_name: str
    count: int


class TrainingCropLabelUpdate(BaseModel):
    label: Literal["open", "closed", "partial", "unsure", "bad"] | None = None
    vehicle_label: Literal["present", "absent", "not_observable", "unsure"] | None = None

    @model_validator(mode="after")
    def validate_one_label(self):
        if (self.label is None) == (self.vehicle_label is None):
            raise ValueError("Provide exactly one door or vehicle label")
        return self


class TrainingCropLabelRead(BaseModel):
    id: int
    label: str | None
    vehicle_label: str | None


class TrainingCropRunLabelUpdate(BaseModel):
    start_crop_id: int
    label: Literal["open", "closed", "partial", "unsure", "bad"] | None = None
    vehicle_label: Literal["present", "absent", "not_observable", "unsure"] | None = None
    count: int = Field(default=8, ge=1, le=8)
    preliminary_label: Literal["open", "closed"] | None = None

    @model_validator(mode="after")
    def validate_one_label(self):
        if (self.label is None) == (self.vehicle_label is None):
            raise ValueError("Provide exactly one door or vehicle label")
        if self.vehicle_label is not None and self.preliminary_label is not None:
            raise ValueError("Preliminary filtering is only available for door labels")
        return self


class TrainingCropRunLabelRead(BaseModel):
    crop_ids: list[int]
    label: str | None = None
    vehicle_label: str | None = None
    count: int


class TrainingCropLabelsClear(BaseModel):
    crop_ids: list[int] = Field(min_length=1, max_length=8)
    dimension: Literal["door", "vehicle"] = "door"


class TrainingCropLabelsClearRead(BaseModel):
    crop_ids: list[int]
    count: int
    dimension: Literal["door", "vehicle"]


class TrainingLabelProgress(BaseModel):
    total: int
    door_labeled: int
    vehicle_labeled: int
    fully_labeled: int
    needs_review: int
    door_counts: dict[str, int]
    vehicle_counts: dict[str, int]


class BatchApprovalRequest(BaseModel):
    confidence_threshold: float = Field(ge=0.5, le=1.0)
    room_number: int | None = None


class BatchApprovalPreview(BaseModel):
    confidence_threshold: float
    room_number: int | None
    total_unlabeled: int
    eligible: int
    predicted_open: int
    predicted_closed: int
    remaining_manual: int
    latest_batch_id: int | None = None
    latest_batch_count: int = 0
    can_undo: bool = False


class BatchApprovalResult(BaseModel):
    batch_id: int
    confidence_threshold: float
    room_number: int | None
    images_approved: int
    open_approved: int
    closed_approved: int
    model_versions: list[str]
    created_at: datetime


class BatchUndoResult(BaseModel):
    batch_id: int
    labels_reverted: int


class DatasetExportResult(BaseModel):
    export_mode: Literal["door", "vehicle", "separate", "multitask"]
    dataset_version: str
    archive_url: str
    export_path: str
    images_exported: int
    missing_images: int
    excluded_bad: int
    candidates_considered: int
    duplicates_removed: int
    conflicting_duplicates: int
    routine_images_skipped: int
    class_balance_removed: int
    benchmark_created: bool
    counts: dict[str, dict[str, int]]
    task_counts: dict[str, dict[str, dict[str, int]]]


class DatasetExportRequest(BaseModel):
    export_mode: Literal["door", "vehicle", "separate", "multitask"] = "door"
    captured_from: date | None = None
    captured_through: date | None = None
    low_confidence_threshold: float = Field(default=0.8, ge=0.5, le=1.0)
    probability_margin_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    random_sample_percent: float = Field(default=20.0, ge=0.0, le=100.0)
    duplicate_window_minutes: int = Field(default=30, ge=0, le=1440)
    perceptual_distance: int = Field(default=6, ge=0, le=64)
    validation_percent: float = Field(default=15.0, ge=0.0, le=40.0)
    initial_test_percent: float = Field(default=15.0, ge=5.0, le=30.0)
    minimum_class_percent: float = Field(default=40.0, ge=0.0, le=50.0)
    vehicle_minimum_class_percent: float = Field(default=40.0, ge=0.0, le=50.0)
    include_low_confidence: bool = True
    include_misclassified: bool = True
    include_edge_cases: bool = True

    @model_validator(mode="after")
    def validate_date_range(self):
        if (
            self.captured_from is not None
            and self.captured_through is not None
            and self.captured_through < self.captured_from
        ):
            raise ValueError("Captured through must be on or after captured from")
        return self


class DatasetExportPreview(BaseModel):
    export_mode: Literal["door", "vehicle", "separate", "multitask"]
    candidates_considered: int
    queried_counts: dict[str, int]
    selected_images: int
    selected_counts: dict[str, int]
    split_counts: dict[str, dict[str, int]]
    queried_task_counts: dict[str, dict[str, int]]
    task_counts: dict[str, dict[str, dict[str, int]]]
    missing_images: int
    duplicates_removed: int
    conflicting_duplicates: int
    routine_images_skipped: int
    class_balance_removed: int
    benchmark_will_be_created: bool


class UnifiCameraRead(BaseModel):
    id: str
    name: str
    state: str
    model: str | None = None
    mac: str | None = None


class CaptureResult(BaseModel):
    camera_id: int
    camera_name: str
    success: bool
    image_path: str | None = None
    captured_at: datetime | None = None
    error: str | None = None


class RoomPulseConfigRead(BaseModel):
    enabled: bool
    endpoint_url: str | None
    public_base_url: str | None
    interval_seconds: int
    send_on_change: bool
    include_image_url: bool
    token_configured: bool
    timeout_seconds: int
    last_sent_at: datetime | None
    last_error: str | None


class RoomPulseConfigUpdate(BaseModel):
    enabled: bool = False
    endpoint_url: str | None = None
    public_base_url: str | None = None
    interval_seconds: int = Field(default=60, ge=10, le=86400)
    send_on_change: bool = True
    include_image_url: bool = True
    bearer_token: str | None = Field(default=None, max_length=4096)
    clear_bearer_token: bool = False
    timeout_seconds: int = Field(default=10, ge=1, le=60)


class RoomPulseDeliveryRead(BaseModel):
    id: int
    event_id: str
    event_type: str
    status: str
    http_status: int | None
    attempt_count: int
    room_count: int
    error: str | None
    created_at: datetime
    delivered_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class RoomPulseTestResult(BaseModel):
    delivery: RoomPulseDeliveryRead


class UnifiConfigRead(BaseModel):
    connection_mode: str
    console_id: str | None = None
    api_key_configured: bool
    local_base_url: str | None = None
    local_api_key_configured: bool


class UnifiConfigUpdate(BaseModel):
    console_id: str | None = Field(default=None, max_length=200)
