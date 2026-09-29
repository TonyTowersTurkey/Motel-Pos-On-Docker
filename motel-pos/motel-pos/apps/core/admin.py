"""Django Admin controls for global motel operations."""

from django.contrib import admin

from apps.core.models import MotelSettings


@admin.register(MotelSettings)
class MotelSettingsAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Expose the singleton operational configuration with an audit stamp."""

    list_display = (
        "__str__",
        "operating_mode",
        "updated_at",
        "updated_by",
    )
    fields = (
        "operating_mode",
        "updated_at",
        "updated_by",
    )
    readonly_fields = ("updated_at", "updated_by")

    def has_add_permission(self, request) -> bool:  # type: ignore[no-untyped-def]
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # type: ignore[no-untyped-def]
        return False

    def save_model(self, request, obj, form, change) -> None:  # type: ignore[no-untyped-def]
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
