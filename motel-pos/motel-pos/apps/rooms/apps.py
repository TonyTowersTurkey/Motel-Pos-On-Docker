"""Django application configuration for the rooms app."""

from django.apps import AppConfig


class RoomsConfig(AppConfig):  # type: ignore[misc]
    """Configuration for the rooms Django application.

    Attributes:
        name: Python package name of the app.
        verbose_name: Human-readable name displayed in admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rooms"
    verbose_name = "Room Management"
