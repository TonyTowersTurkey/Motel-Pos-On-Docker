"""Django application configuration for the core app."""

from django.apps import AppConfig


class CoreConfig(AppConfig):  # type: ignore[misc]
    """Configuration for the core shared Django application.

    Contains shared utilities, exception handling, pagination, permissions.

    Attributes:
        name: Python package name of the app.
        verbose_name: Human-readable name displayed in admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core Infrastructure"

    def ready(self) -> None:
        """Register post-commit dashboard notifications."""
        from apps.core import signals  # noqa: F401, PLC0415
