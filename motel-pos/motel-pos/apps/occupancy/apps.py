"""Django application configuration for the occupancy app."""

from django.apps import AppConfig


class OccupancyConfig(AppConfig):  # type: ignore[misc]
    """Configuration for the occupancy Django application.

    Attributes:
        name: Python package name of the app.
        verbose_name: Human-readable name displayed in admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.occupancy"
    verbose_name = "Occupancy Tracking"
