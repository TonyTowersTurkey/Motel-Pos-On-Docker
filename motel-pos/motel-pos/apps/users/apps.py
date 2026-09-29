"""Django application configuration for the users app."""

from django.apps import AppConfig


class UsersConfig(AppConfig):  # type: ignore[misc]
    """Configuration for the users Django application.

    Attributes:
        name: Python package name of the app.
        verbose_name: Human-readable name displayed in admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "User Management"

    def ready(self) -> None:
        """Provision role groups after Django creates model permissions."""
        from django.db.models.signals import post_migrate  # noqa: PLC0415

        from apps.users.access import provision_role_groups  # noqa: PLC0415

        def provision_groups(sender, using, **kwargs):  # type: ignore[no-untyped-def]  # noqa: ARG001
            provision_role_groups(using=using, migrate_users=False)

        post_migrate.connect(
            provision_groups,
            dispatch_uid="users.provision_role_groups",
            weak=False,
        )
