"""Serializers for vehicle/customer records."""

from rest_framework import serializers

from apps.guests.models import Vehicle, VehicleShape, normalize_license_plate
from apps.rooms.models import RentalSession, Room


class VehicleShapeSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for manager-controlled vehicle shape choices."""

    vehicle_count = serializers.IntegerField(source="vehicles.count", read_only=True)

    class Meta:
        model = VehicleShape
        fields = [
            "id",
            "name",
            "active",
            "sort_order",
            "icon",
            "vehicle_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "icon", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a vehicle shape name.")
        queryset = VehicleShape.objects.filter(name__iexact=name)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("This vehicle shape already exists.")
        return name


class VehicleSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for cashier vehicle records."""

    room_context = serializers.SerializerMethodField()
    vehicle_shape_name = serializers.CharField(
        source="vehicle_shape.name", read_only=True, default=""
    )

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "make",
            "model",
            "color",
            "vehicle_shape",
            "vehicle_shape_name",
            "license_plate",
            "notes",
            "room_context",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_vehicle_shape(
        self, value: VehicleShape | None
    ) -> VehicleShape | None:
        if value is not None and not value.active:
            raise serializers.ValidationError("Select an active vehicle shape.")
        return value

    def get_room_context(self, obj: Vehicle) -> dict[str, list[dict[str, str]]]:
        """Summarize where the vehicle is currently attached or in use."""
        room_ids = {room.room_id for room in obj.current_rooms.all()}
        room_ids.update(session.room_id for session in obj.rental_sessions.all())
        rooms_by_id = (
            Room.objects.in_bulk(room_ids, field_name="room_id") if room_ids else {}
        )

        current_rooms = [
            {
                "room_id": room.room_id,
                "room_number": room.room_number,
            }
            for room in obj.current_rooms.all()
        ]
        active_sessions = []
        for session in obj.rental_sessions.all():
            if session.status not in {
                RentalSession.Status.DRAFT,
                RentalSession.Status.CONFIRMED,
                RentalSession.Status.CHECKED_IN,
            }:
                continue

            room = rooms_by_id.get(session.room_id)
            active_sessions.append(
                {
                    "room_id": session.room_id,
                    "room_number": room.room_number if room else "",
                    "status": session.status,
                }
            )
        return {
            "current_rooms": current_rooms,
            "active_rental_sessions": active_sessions,
        }

    def validate_license_plate(self, value: str) -> str:
        """Reject duplicate nonblank plates using normalized comparison."""
        value = value.upper()
        normalized = normalize_license_plate(value)
        if not normalized:
            return value

        qs = Vehicle.objects.filter(license_plate_normalized=normalized)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A vehicle with this license plate already exists."
            )
        return value
