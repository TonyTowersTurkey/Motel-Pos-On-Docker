"""Register rooms, occupancy, and revenue models in Django admin."""

from django.contrib import admin

from apps.occupancy.models import AuditLog, OccupancyEvent
from apps.revenue.models import OccupancySession, ShiftLedger
from apps.rooms.admin import (  # noqa: F401
    AmenityAdmin,
    MaintenanceLogAdmin,
    PricingTierAdmin,
    RentalSessionAdmin,
    RoomAdmin,
    RoomAmenityAdmin,
)


@admin.register(OccupancyEvent)
class OccupancyEventAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for occupancy events."""

    list_display = ("pk", "room_id", "event_type", "confidence", "source", "timestamp")
    list_filter = ("event_type", "source")
    search_fields = ("room_id",)
    readonly_fields = ("pk", "timestamp")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for audit logs."""

    list_display = ("pk", "user", "action", "object_type", "timestamp")
    list_filter = ("action", "object_type")
    search_fields = ("user", "action", "object_type")
    readonly_fields = ("pk", "timestamp")


@admin.register(OccupancySession)
class OccupancySessionAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for occupancy sessions."""

    list_display = (
        "pk",
        "room_id",
        "guest_name",
        "check_in",
        "check_out",
        "status",
    )
    list_filter = ("status", "source")
    search_fields = ("room_id", "guest_name", "phone")


@admin.register(ShiftLedger)
class ShiftLedgerAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for shift ledger entries."""

    list_display = (
        "pk",
        "date",
        "shift_number",
        "subtotal",
        "ath_subtotal",
        "logged_by",
    )
    list_filter = ("date",)
    search_fields = ("logged_by", "verified_by")
