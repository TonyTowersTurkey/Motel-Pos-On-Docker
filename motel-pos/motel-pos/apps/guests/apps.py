"""App configuration for vehicle/customer records."""

from django.apps import AppConfig


class GuestsConfig(AppConfig):
    """Vehicle/customer tracking app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.guests"
