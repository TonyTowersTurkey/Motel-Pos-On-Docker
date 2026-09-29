"""Serializers for occupancy models."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.occupancy.models import AuditLog, OccupancyEvent
from apps.rooms.models import Room


class RoomPulseRoomSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Validate one room entry from the Room Pulse 1.0 contract."""

    room_record_id = serializers.IntegerField(min_value=1)
    room_number = serializers.IntegerField(min_value=0)
    room_name = serializers.CharField(max_length=200, allow_blank=True)
    state = serializers.ChoiceField(choices=("open", "closed", "unknown"))
    confidence = serializers.FloatField(
        min_value=0.0, max_value=1.0, allow_null=True
    )
    state_source = serializers.ChoiceField(choices=("confirmed",))
    confirmation_streak = serializers.IntegerField(min_value=0)
    state_changed_at = serializers.DateTimeField(allow_null=True)
    last_observed_at = serializers.DateTimeField(allow_null=True)
    last_observed_state = serializers.ChoiceField(
        choices=("open", "closed", "unknown"), allow_null=True
    )
    last_observed_confidence = serializers.FloatField(
        min_value=0.0, max_value=1.0, allow_null=True
    )
    camera_id = serializers.IntegerField(min_value=1)
    camera_name = serializers.CharField(max_length=200, allow_blank=True)
    snapshot_id = serializers.IntegerField(min_value=1, allow_null=True)
    snapshot_captured_at = serializers.DateTimeField(allow_null=True)
    crop_image_path = serializers.CharField(
        max_length=1000, allow_blank=False, allow_null=True
    )
    crop_image_url = serializers.URLField(
        max_length=1000, allow_blank=False, allow_null=True
    )
    model_version = serializers.CharField(
        max_length=200, allow_blank=True, allow_null=True
    )
    stale = serializers.BooleanField()


class RoomPulseWebhookSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Validate a complete Room Pulse 1.0 snapshot."""

    schema_version = serializers.ChoiceField(choices=("1.0",))
    event_id = serializers.UUIDField()
    event_type = serializers.ChoiceField(
        choices=("room_state_changed", "room_state_heartbeat", "test")
    )
    generated_at = serializers.DateTimeField()
    source = serializers.CharField(max_length=100, allow_blank=False)
    room_count = serializers.IntegerField(min_value=0, max_value=1000)
    rooms = serializers.ListField(
        child=RoomPulseRoomSerializer(),
        allow_empty=True,
        max_length=1000,
    )

    def validate_generated_at(self, value):  # type: ignore[no-untyped-def]
        """Prevent a future-dated snapshot from blocking legitimate updates."""
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError(
                "Cannot be more than five minutes in the future."
            )
        return value

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        """Require the declared count and business mapping keys to be consistent."""
        if attrs["room_count"] != len(attrs["rooms"]):
            raise serializers.ValidationError(
                {"room_count": "Must equal the number of entries in rooms."}
            )

        room_numbers = [room["room_number"] for room in attrs["rooms"]]
        if len(room_numbers) != len(set(room_numbers)):
            raise serializers.ValidationError(
                {"rooms": "Each room_number must appear only once per snapshot."}
            )
        return attrs


class OccupancyEventSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for occupancy events."""

    room_number = serializers.SerializerMethodField()

    class Meta:
        model = OccupancyEvent
        fields = [
            "event_id",
            "room_id",
            "room_number",
            "timestamp",
            "event_type",
            "confidence",
            "source",
            "notes",
        ]
        read_only_fields = ["event_id", "timestamp"]

    def get_room_number(self, obj: OccupancyEvent) -> str:
        """Expose the cashier room number alongside the internal room id."""
        room = Room.objects.filter(room_id=obj.room_id).first()
        return room.room_number if room is not None else ""


class AuditLogSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for audit logs."""

    class Meta:
        model = AuditLog
        fields = [
            "audit_id",
            "timestamp",
            "user",
            "action",
            "object_type",
            "object_id",
            "previous_value",
            "new_value",
        ]
        read_only_fields = ["audit_id", "timestamp"]
