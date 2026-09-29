"""Read-only operational visibility for Room Pulse ingestion."""

from django.contrib import admin

from apps.occupancy.models import RoomPulseDelivery, RoomPulseRoomState


@admin.register(RoomPulseDelivery)
class RoomPulseDeliveryAdmin(admin.ModelAdmin):  # type: ignore[misc]
    list_display = (
        "event_id",
        "event_type",
        "generated_at",
        "room_count",
        "received_at",
    )
    list_filter = ("event_type", "schema_version")
    search_fields = ("event_id", "source")
    readonly_fields = (
        "event_id",
        "schema_version",
        "event_type",
        "generated_at",
        "source",
        "room_count",
        "received_at",
        "payload",
        "result",
    )

    def has_add_permission(  # noqa: ARG002
        self, request  # type: ignore[no-untyped-def]
    ) -> bool:
        return False

    def has_delete_permission(  # noqa: ARG002
        self, request, obj=None  # type: ignore[no-untyped-def]
    ) -> bool:
        return False


@admin.register(RoomPulseRoomState)
class RoomPulseRoomStateAdmin(admin.ModelAdmin):  # type: ignore[misc]
    list_display = (
        "room",
        "state",
        "stale",
        "confidence",
        "generated_at",
        "camera_name",
    )
    list_filter = ("state", "stale", "camera_name")
    search_fields = ("room__room_number", "room_name", "camera_name")
    list_select_related = ("room", "delivery")
    readonly_fields = (
        "room",
        "delivery",
        "generated_at",
        "room_record_id",
        "room_name",
        "state",
        "confidence",
        "state_source",
        "confirmation_streak",
        "state_changed_at",
        "last_observed_at",
        "last_observed_state",
        "last_observed_confidence",
        "camera_id",
        "camera_name",
        "snapshot_id",
        "snapshot_captured_at",
        "crop_image_path",
        "crop_image_url",
        "model_version",
        "stale",
        "updated_at",
    )

    def has_add_permission(  # noqa: ARG002
        self, request  # type: ignore[no-untyped-def]
    ) -> bool:
        return False

    def has_delete_permission(  # noqa: ARG002
        self, request, obj=None  # type: ignore[no-untyped-def]
    ) -> bool:
        return False
