"""Serializers for planned maintenance templates and previews."""

from __future__ import annotations

from rest_framework import serializers

from apps.maintenance.models import PlannedMaintenanceTemplate
from apps.maintenance.services import build_calendar_preview
from apps.rooms.models import Room, RoomGroup


class PlannedMaintenancePreviewSlotSerializer(serializers.Serializer):
    """Render a single PM preview row."""

    room_id = serializers.CharField()
    room_number = serializers.CharField()
    due_date = serializers.DateField()
    estimated_minutes = serializers.IntegerField()


class PlannedMaintenancePreviewSerializer(serializers.Serializer):
    """Return the computed PM calendar preview for a template."""

    template_id = serializers.IntegerField()
    template_name = serializers.CharField()
    cycle_due_date = serializers.DateField()
    rooms_per_day = serializers.IntegerField()
    total_rooms = serializers.IntegerField()
    estimated_total_minutes = serializers.IntegerField()
    slots = PlannedMaintenancePreviewSlotSerializer(many=True)


class PlannedMaintenanceTemplateSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """CRUD serializer for recurring maintenance templates."""

    rooms = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Room.objects.all(),
        required=False,
    )
    room_groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=RoomGroup.objects.all(),
        required=False,
    )
    preview = serializers.SerializerMethodField()

    class Meta:
        model = PlannedMaintenanceTemplate
        fields = [
            "id",
            "name",
            "description",
            "category",
            "default_priority",
            "frequency_value",
            "frequency_unit",
            "start_date",
            "end_date",
            "is_active",
            "auto_create_work_orders",
            "create_days_before_due",
            "estimated_minutes_per_room",
            "all_rooms",
            "rooms",
            "room_groups",
            "target_building",
            "target_floor",
            "target_room_type",
            "preview",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "preview", "created_at", "updated_at"]

    def get_preview(self, obj: PlannedMaintenanceTemplate) -> dict[str, object]:
        """Expose a tiny preview summary alongside the template."""
        preview = build_calendar_preview(obj)
        return {
            "rooms": len(preview),
            "next_due_date": preview[0].due_date if preview else None,
        }

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Keep the date range coherent."""
        start_date = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = attrs.get("end_date") if "end_date" in attrs else getattr(self.instance, "end_date", None)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be on or after the start date."}
            )
        return attrs

    def create(self, validated_data: dict[str, object]) -> PlannedMaintenanceTemplate:
        rooms = validated_data.pop("rooms", [])
        room_groups = validated_data.pop("room_groups", [])
        template = super().create(validated_data)
        if rooms:
            template.rooms.set(rooms)
        if room_groups:
            template.room_groups.set(room_groups)
        return template

    def update(self, instance: PlannedMaintenanceTemplate, validated_data: dict[str, object]) -> PlannedMaintenanceTemplate:
        rooms = validated_data.pop("rooms", None)
        room_groups = validated_data.pop("room_groups", None)
        template = super().update(instance, validated_data)
        if rooms is not None:
            template.rooms.set(rooms)
        if room_groups is not None:
            template.room_groups.set(room_groups)
        return template


class PlannedMaintenancePreviewRequestSerializer(serializers.Serializer):
    """Validate preview request parameters."""

    rooms_per_day = serializers.IntegerField(required=False, min_value=1, default=15)
    today = serializers.DateField(required=False)
