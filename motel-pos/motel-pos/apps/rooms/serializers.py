"""Serializers for room management models."""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from rest_framework import serializers

from apps.guests.models import Vehicle
from apps.guests.serializers import VehicleSerializer
from apps.occupancy.models import OccupancyEvent
from apps.revenue.models import OccupancySession
from apps.rooms.models import (
    Amenity,
    DynamicPricingRule,
    MaintenanceLog,
    PricingTier,
    RentalSession,
    Room,
    RoomAmenity,
)


class RoomVehicleSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Lightweight vehicle summary for room cards and room detail views."""

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
        ]

class RoomSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the Room model."""

    active_occupancy_session = serializers.SerializerMethodField()
    latest_occupancy_event = serializers.SerializerMethodField()
    entered_at = serializers.SerializerMethodField()
    max_stay_at = serializers.SerializerMethodField()
    current_vehicle = RoomVehicleSerializer(read_only=True)

    class Meta:
        model = Room
        fields = [
            "room_id",
            "room_number",
            "active",
            "notes",
            "pricing_tier_code",
            "price",
            "ac",
            "tv",
            "edificio",
            "cuenta_luma",
            "max_occupants",
            "amenities_snapshot",
            "current_state",
            "current_vehicle",
            "active_occupancy_session",
            "latest_occupancy_event",
            "entered_at",
            "max_stay_at",
        ]

    def validate_room_id(self, value: str) -> str:
        room_id = value.strip()
        if not room_id.isdigit():
            raise serializers.ValidationError("Room ID must contain numbers only.")
        return room_id

    def validate_room_number(self, value: str) -> str:
        # Reject duplicate room numbers so the editor stays unambiguous.
        room_number = value.strip()
        if not room_number:
            return room_number
        queryset = Room.objects.filter(room_number=room_number)
        if self.instance is not None:
            queryset = queryset.exclude(room_id=self.instance.room_id)
        if queryset.exists():
            raise serializers.ValidationError(
                "Room number is already assigned to another room."
            )
        return room_number

    def get_active_occupancy_session(
        self, obj: Room
    ) -> dict[str, object] | None:
        """Return the active occupancy session, if the room is currently occupied."""
        session = (
            OccupancySession.objects.filter(
                room_id=obj.room_id,
                status=OccupancySession.Status.ACTIVE,
            )
            .order_by("-check_in", "-id")
            .first()
        )
        if session is None:
            return None
        return {
            "session_id": session.id,
            "room_id": session.room_id,
            "check_in": session.check_in.isoformat(),
            "status": session.status,
            "source": session.source,
        }

    def get_latest_occupancy_event(
        self, obj: Room
    ) -> dict[str, object] | None:
        """Return the latest occupancy event so cashier cards can show confidence."""
        event = OccupancyEvent.objects.filter(room_id=obj.room_id).first()
        if event is None:
            return None
        return {
            "event_id": event.event_id,
            "room_id": event.room_id,
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "confidence": event.confidence,
            "source": event.source,
        }

    def _stay_window(self, obj: Room) -> tuple[datetime | None, datetime | None]:
        cached = getattr(obj, "_cashier_stay_window", None)
        if cached is not None:
            return cached
        occupancy = (
            OccupancySession.objects.filter(
                room_id=obj.room_id, status=OccupancySession.Status.ACTIVE
            )
            .order_by("check_in", "id")
            .first()
        )
        rental = (
            RentalSession.objects.filter(
                room_id=obj.room_id, status=RentalSession.Status.CHECKED_IN
            )
            .order_by("start_time", "session_id")
            .first()
        )
        starts = [
            value
            for value in [
                occupancy.check_in if occupancy else None,
                rental.start_time if rental else None,
            ]
            if value
        ]
        if not starts:
            window = (None, None)
            obj._cashier_stay_window = window
            return window
        entered_at = min(starts)
        duration_hours = 8
        if rental and rental.end_time:
            scheduled_hours = round(
                (rental.end_time - rental.start_time).total_seconds() / 3600
            )
            if scheduled_hours in (16, 24):
                duration_hours = scheduled_hours
        window = (entered_at, entered_at + timedelta(hours=duration_hours))
        obj._cashier_stay_window = window
        return window

    def get_entered_at(self, obj: Room) -> str | None:
        entered_at, _ = self._stay_window(obj)
        return entered_at.isoformat() if entered_at else None

    def get_max_stay_at(self, obj: Room) -> str | None:
        _, max_stay_at = self._stay_window(obj)
        return max_stay_at.isoformat() if max_stay_at else None

class PricingTierSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the PricingTier model."""

    class Meta:
        model = PricingTier
        fields = [
            "id",
            "code",
            "price_per_night",
            "description",
            "active",
        ]


class AmenitySerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the Amenity model."""

    class Meta:
        model = Amenity
        fields = [
            "id",
            "name",
            "display_name",
            "icon_class",
            "price_surcharge",
        ]


class RoomAmenitySerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the RoomAmenity junction model."""

    class Meta:
        model = RoomAmenity
        fields = [
            "room_id",
            "amenity_id",
            "status",
            "notes",
        ]


class MaintenanceLogSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the MaintenanceLog model."""

    class Meta:
        model = MaintenanceLog
        fields = [
            "id",
            "room_id",
            "category",
            "description",
            "is_recurring",
            "recurrence_interval_days",
            "last_performed",
            "next_due",
            "estimated_cost",
            "actual_cost",
            "assigned_to",
            "vendor_contact",
            "status",
            "completion_notes",
            "created_at",
        ]


class RentalSessionSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the RentalSession model."""

    vehicle = VehicleSerializer(read_only=True)
    duration_hours = serializers.SerializerMethodField()
    rental_type = serializers.SerializerMethodField()
    room_number = serializers.SerializerMethodField()
    sale_amount = serializers.SerializerMethodField()
    vehicle_id = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        source="vehicle",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = RentalSession
        fields = [
            "session_id",
            "room_id",
            "start_time",
            "end_time",
            "exit_time",
            "duration_hours",
            "rental_type",
            "status",
            "source",
            "room_number",
            "sale_amount",
            "vehicle",
            "vehicle_id",
            "reviewed_by",
            "notes",
        ]

    def get_duration_hours(self, obj: RentalSession) -> float | None:
        """Return scheduled rental duration in hours when both endpoints exist."""
        if obj.start_time is None or obj.end_time is None:
            return None
        seconds = (obj.end_time - obj.start_time).total_seconds()
        return round(max(seconds, 0) / 3600, 2)

    def get_rental_type(self, obj: RentalSession) -> str:
        """Label the billed 8-hour block count for cashier review."""
        duration = self.get_duration_hours(obj) or 8
        if duration > 16:
            return "Triple"
        if duration > 8:
            return "Double"
        return "Single"

    def get_room_number(self, obj: RentalSession) -> str:
        """Expose cashier-friendly room number without requiring a second API call."""
        room = Room.objects.filter(room_id=obj.room_id).first()
        return room.room_number if room is not None else obj.room_id

    def get_sale_amount(self, obj: RentalSession) -> float:
        """Estimate sale amount from room price and 8-hour rental blocks."""
        room = Room.objects.filter(room_id=obj.room_id).first()
        price = Decimal(str(room.price if room is not None else 0))
        duration = self.get_duration_hours(obj) or 8
        blocks = max(1, math.ceil(duration / 8))
        return float(price * Decimal(blocks))




class DynamicPricingRuleSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for the DynamicPricingRule model."""

    class Meta:
        model = DynamicPricingRule
        fields = [
            "id",
            "tier_code",
            "name",
            "rule_type",
            "start_date",
            "end_date",
            "day_of_week",
            "price_override",
            "description",
            "is_active",
            "priority",
            "created_at",
            "updated_at",
        ]
