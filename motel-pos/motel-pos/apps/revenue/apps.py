"""Django application configuration for the revenue app."""

from django.apps import AppConfig


class RevenueConfig(AppConfig):  # type: ignore[misc]
    """Configuration for the revenue Django application.

    Attributes:
        name: Python package name of the app.
        verbose_name: Human-readable name displayed in admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.revenue"
    verbose_name = "Revenue Tracking"
