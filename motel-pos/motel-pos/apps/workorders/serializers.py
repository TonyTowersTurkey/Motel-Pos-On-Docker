"""Serializers for work order CRUD and template rendering."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.rooms.models import Room
from apps.workorders.models import WorkOrder

User = get_user_model()


def _resolve_user(label: str):
    if not label or label.lower() == "unassigned":
        return None
    return (
        User.objects.filter(username__iexact=label).first()
        or User.objects.filter(first_name__iexact=label).first()
        or User.objects.filter(last_name__iexact=label).first()
    )


class WorkOrderSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serialize work orders for the maintenance UI and API."""

    room_number = serializers.CharField(write_only=True)
    assigned_to_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        default="",
    )
    checklist = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    attachments = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    room = serializers.SerializerMethodField()
    room_id = serializers.SerializerMethodField()
    assigned_to = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = WorkOrder
        fields = [
            "id",
            "room",
            "room_id",
            "room_number",
            "title",
            "description",
            "category",
            "priority",
            "status",
            "source",
            "assigned_to",
            "assigned_to_name",
            "created_by",
            "due_date",
            "estimated_minutes",
            "instructions",
            "location_notes",
            "safety_notes",
            "checklist",
            "attachments",
            "completed_at",
            "completion_notes",
            "parts_used",
            "issues_found",
            "time_spent_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "room",
            "room_id",
            "assigned_to",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_room(self, obj: WorkOrder) -> str:
        return obj.room.room_number

    def get_room_id(self, obj: WorkOrder) -> str:
        return obj.room.room_id

    def get_assigned_to(self, obj: WorkOrder) -> str:
        if obj.assigned_to_label:
            return obj.assigned_to_label
        if obj.assigned_to:
            return obj.assigned_to.get_username()
        return "Unassigned"

    def get_created_by(self, obj: WorkOrder) -> str:
        if obj.created_by:
            return obj.created_by.get_username()
        return ""

    def to_representation(self, instance: WorkOrder) -> dict[str, object]:
        data = super().to_representation(instance)
        data["room"] = instance.room.room_number
        data["room_id"] = instance.room.room_id
        data["assigned_to"] = self.get_assigned_to(instance)
        data["created_by"] = self.get_created_by(instance)
        return data

    def create(self, validated_data: dict[str, object]) -> WorkOrder:
        room_number = validated_data.pop("room_number")
        assigned_to_name = validated_data.pop("assigned_to_name", "")
        room = Room.objects.get(room_number=room_number)
        assigned_to = _resolve_user(str(assigned_to_name))
        request = self.context.get("request")
        created_by = getattr(request, "user", None)
        if not getattr(created_by, "is_authenticated", False):
            created_by = None
        return WorkOrder.objects.create(
            room=room,
            assigned_to=assigned_to,
            assigned_to_label=str(assigned_to_name or ""),
            created_by=created_by,
            **validated_data,
        )

    def update(self, instance: WorkOrder, validated_data: dict[str, object]) -> WorkOrder:
        room_number = validated_data.pop("room_number", None)
        assigned_to_name = validated_data.pop("assigned_to_name", None)
        if room_number:
            instance.room = Room.objects.get(room_number=room_number)
        if assigned_to_name is not None:
            instance.assigned_to = _resolve_user(str(assigned_to_name))
            instance.assigned_to_label = str(assigned_to_name or "")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


def serialize_work_orders(work_orders):
    return WorkOrderSerializer(work_orders, many=True).data
