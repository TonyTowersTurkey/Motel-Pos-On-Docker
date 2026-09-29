"""Admin interface for room management models."""

from django.contrib import admin

from apps.rooms.models import (
    Amenity,
    MaintenanceLog,
    PricingTier,
    RentalSession,
    Room,
    RoomAmenity,
)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin interface for rooms.

    Attributes:
        list_display: Columns shown in the room list view.
        list_filter: Fields available for filtering.
        search_fields: Fields searchable in the admin.
        list_editable: Inline-editable fields.
    """

    list_display = (
        "room_number",
        "room_id",
        "price",
        "edificio",
        "ac",
        "tv",
        "cuenta_luma",
        "pricing_tier_code",
        "active",
        "max_occupants",
    )
    list_filter = ("active", "edificio", "pricing_tier_code", "ac", "tv")
    search_fields = ("room_number", "room_id", "edificio", "notes")
    list_editable = ("price", "edificio", "ac", "tv", "cuenta_luma", "active")
    fieldsets = (
        (
            "Room",
            {
                "fields": (
                    "room_id",
                    "room_number",
                    "active",
                    "current_state",
                )
            },
        ),
        (
            "Configuration",
            {
                "fields": (
                    "price",
                    "ac",
                    "tv",
                    "edificio",
                    "cuenta_luma",
                    "pricing_tier_code",
                    "max_occupants",
                    "amenities_snapshot",
                )
            },
        ),
        ("Notes", {"fields": ("notes",)}),
    )


@admin.register(PricingTier)
class PricingTierAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin interface for pricing tiers."""

    list_display = ("code", "price_per_night", "description", "active")
    list_filter = ("active",)
    search_fields = ("code", "description")


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin interface for amenities."""

    list_display = ("display_name", "name", "price_surcharge")
    search_fields = ("name", "display_name")


@admin.register(RoomAmenity)
class RoomAmenityAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin interface for room-amenity associations."""

    list_display = ("room_id", "amenity_id", "status")
    list_filter = ("status",)
    search_fields = ("room_id",)


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin interface for maintenance logs."""

    list_display = (
        "pk",
        "room_id",
        "category",
        "status",
        "is_recurring",
        "next_due",
        "created_at",
    )
    list_filter = ("status", "is_recurring", "category")
    search_fields = ("room_id", "description", "assigned_to")


@admin.register(RentalSession)
class RentalSessionAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin interface for rental sessions."""

    list_display = (
        "pk",
        "room_id",
        "start_time",
        "end_time",
        "exit_time",
        "status",
        "source",
    )
    list_filter = ("status", "source")
    search_fields = ("room_id",)
