"""Admin registration for vehicle records."""

from django.contrib import admin
from django.utils.html import format_html

from apps.guests.models import Vehicle, VehicleShape


@admin.register(VehicleShape)
class VehicleShapeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["icon_preview", "name", "active", "sort_order", "updated_at"]
    list_editable = ["active", "sort_order"]
    search_fields = ["name"]
    readonly_fields = ["icon_preview", "created_at", "updated_at"]
    fields = [
        "name",
        "icon",
        "icon_preview",
        "active",
        "sort_order",
        "created_at",
        "updated_at",
    ]

    @admin.display(description="Logo")
    def icon_preview(self, obj: VehicleShape) -> str:
        if not obj.icon:
            return "—"
        return format_html(
            '<img src="{}" alt="" style="width:88px;height:44px;object-fit:contain">',
            obj.icon.url,
        )


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Manage vehicle records in Django admin."""

    list_display = [
        "license_plate",
        "make",
        "model",
        "color",
        "vehicle_shape",
        "updated_at",
    ]
    search_fields = [
        "license_plate",
        "make",
        "model",
        "color",
        "vehicle_shape__name",
        "notes",
    ]
    readonly_fields = ["license_plate_normalized", "created_at", "updated_at"]
