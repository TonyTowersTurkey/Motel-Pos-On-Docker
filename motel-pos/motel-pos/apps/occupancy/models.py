"""Occupancy history and Room Pulse webhook state."""

from django.db import models


class SensorReading(models.Model):  # type: ignore[misc]
    """Legacy sensor reading retained for historical data compatibility.

    Maps from SQLAlchemy app.database.SensorReading.
    """

    reading_id = models.AutoField(primary_key=True)
    room_id = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    distance_mm = models.IntegerField(help_text="Distance in millimeters from sensor.")
    presence = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="'present' or 'absent' as detected by the raw sensor.",
    )
    illuminance = models.IntegerField(null=True, blank=True)
    battery_level = models.FloatField(null=True, blank=True)
    signal_strength_dbm = models.IntegerField(null=True, blank=True)
    raw_payload = models.TextField(blank=True, default="")  # type: ignore[misc]

    class Meta:
        db_table = "sensor_readings"
        verbose_name = "sensor reading"
        verbose_name_plural = "sensor readings"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["room_id", "-timestamp"]),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Reading #{self.pk} - Room {self.room_id} at {self.timestamp}"


class OccupancyEvent(models.Model):  # type: ignore[misc]
    """Occupancy state transition event.

    Maps from SQLAlchemy app.database.OccupancyEvent.
    Emitted by the state machine when occupancy status changes.
    """

    class EventType(models.TextChoices):
        ARRIVAL = "arrival", "Arrival"
        DEPARTURE = "departure", "Departure"
        CHECK_IN = "check_in", "Check In"
        CHECK_OUT = "check_out", "Check Out"
        MAINTENANCE = "maintenance", "Maintenance Window"
        MANUAL_OVERRIDE = "manual_override", "Manual Override"
        VEHICLE_ATTACHED = "vehicle_attached", "Vehicle Attached"
        VEHICLE_CLEARED = "vehicle_cleared", "Vehicle Cleared"

    class Source(models.TextChoices):
        SENSOR_AUTO = "sensor_auto", "Automated Sensor"
        MANUAL_INPUT = "manual_input", "Manual Input"
        API_CALL = "api_call", "API Call"
        ROOM_PULSE = "room_pulse", "Room Pulse"

    event_id = models.AutoField(primary_key=True)
    room_id = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    confidence = models.FloatField(default=1.0)
    source = models.CharField(
        max_length=20, choices=Source.choices, default=Source.SENSOR_AUTO
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "occupancy_events"
        verbose_name = "occupancy event"
        verbose_name_plural = "occupancy events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["room_id", "-timestamp"]),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Event #{self.pk} - {self.event_type} - Room {self.room_id}"


class RoomPulseDelivery(models.Model):  # type: ignore[misc]
    """A durably accepted, idempotent Room Pulse snapshot delivery."""

    event_id = models.UUIDField(primary_key=True, editable=False)
    schema_version = models.CharField(max_length=20)
    event_type = models.CharField(max_length=40)
    generated_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=100)
    room_count = models.PositiveIntegerField()
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    payload = models.JSONField()
    result = models.JSONField(default=dict)

    class Meta:
        db_table = "room_pulse_deliveries"
        verbose_name = "Room Pulse delivery"
        verbose_name_plural = "Room Pulse deliveries"
        ordering = ("-received_at",)

    def __str__(self) -> str:  # type: ignore[override]
        return f"Room Pulse {self.event_id} ({self.event_type})"


class RoomPulseRoomState(models.Model):  # type: ignore[misc]
    """Latest accepted Room Pulse state and diagnostics for a mapped room."""

    class DoorState(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        UNKNOWN = "unknown", "Unknown"

    room = models.OneToOneField(
        "rooms.Room",
        on_delete=models.CASCADE,
        related_name="room_pulse_state",
    )
    delivery = models.ForeignKey(
        RoomPulseDelivery,
        on_delete=models.PROTECT,
        related_name="room_states",
    )
    generated_at = models.DateTimeField(db_index=True)
    room_record_id = models.PositiveIntegerField()
    room_name = models.CharField(max_length=200)
    state = models.CharField(max_length=10, choices=DoorState.choices)
    confidence = models.FloatField(null=True, blank=True)
    state_source = models.CharField(max_length=40)
    confirmation_streak = models.PositiveIntegerField()
    state_changed_at = models.DateTimeField(null=True, blank=True)
    last_observed_at = models.DateTimeField(null=True, blank=True)
    last_observed_state = models.CharField(
        max_length=10,
        choices=DoorState.choices,
        blank=True,
        default="",
    )
    last_observed_confidence = models.FloatField(null=True, blank=True)
    camera_id = models.PositiveIntegerField()
    camera_name = models.CharField(max_length=200)
    snapshot_id = models.PositiveIntegerField(null=True, blank=True)
    snapshot_captured_at = models.DateTimeField(null=True, blank=True)
    crop_image_path = models.CharField(max_length=1000, blank=True, default="")
    crop_image_url = models.URLField(max_length=1000, blank=True, default="")
    model_version = models.CharField(max_length=200, blank=True, default="")
    stale = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "room_pulse_room_states"
        verbose_name = "Room Pulse room state"
        verbose_name_plural = "Room Pulse room states"
        ordering = ("room__room_number",)

    def __str__(self) -> str:  # type: ignore[override]
        return f"Room {self.room.room_number}: {self.state}"


class AuditLog(models.Model):  # type: ignore[misc]
    """Audit trail for all significant operations.

    Maps from SQLAlchemy app.database.AuditLog.
    """

    audit_id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.CharField(max_length=100)
    action = models.CharField(max_length=50)
    object_type = models.CharField(max_length=50)
    object_id = models.IntegerField(null=True, blank=True)
    previous_value = models.TextField(blank=True, default="")  # type: ignore[misc]
    new_value = models.TextField(blank=True, default="")  # type: ignore[misc]

    class Meta:
        db_table = "audit_log"
        verbose_name = "audit log"
        verbose_name_plural = "audit logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Audit #{self.pk} - {self.action} by {self.user}"
