"""Custom user model for motel occupancy system."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):  # type: ignore[misc]
    """Custom user extending Django's AbstractUser for motel role-based access."""

    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        ADMIN = "admin", "Administrator"

    role = models.CharField(  # type: ignore[misc]
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER,
        help_text="Role-based access level for the user.",
    )
    phone = models.CharField(  # type: ignore[misc]
        max_length=30,
        blank=True,
        default="",
    )
    notes = models.TextField(blank=True, default="")  # type: ignore[misc]

    class Meta:
        db_table = "auth_user"
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            models.UniqueConstraint(fields=["email"], name="unique_email"),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return self.get_username()

    @property
    def is_manager(self) -> bool:
        """Return True if user has manager or admin role."""
        return self.role in (self.Role.MANAGER, self.Role.ADMIN)

    @property
    def is_admin(self) -> bool:
        """Return True if user has admin role."""
        return self.role == self.Role.ADMIN
