"""Database-backed operational settings shared across the motel."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MotelSettings(models.Model):  # type: ignore[misc]
    """Singleton operational settings editable through Django Admin."""

    class OperatingMode(models.TextChoices):
        AUDIT_MODE = (
            "audit_mode",
            "Audit Mode — hands-off, no cashier interaction",
        )
        POS_HANDS_ON_MODE = (
            "pos_hands_on_mode",
            "POS Hands On Mode — wait for cashier, then mark room dirty",
        )

    singleton_id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    operating_mode = models.CharField(
        max_length=40,
        choices=OperatingMode.choices,
        default=OperatingMode.POS_HANDS_ON_MODE,
        help_text=(
            "Controls the motel's overall operating workflow. Audit Mode is "
            "hands-off; POS Hands On Mode waits for cashier interaction."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="updated_motel_settings",
    )

    class Meta:
        verbose_name = "motel operational settings"
        verbose_name_plural = "motel operational settings"

    def clean(self) -> None:
        if self.pk not in {None, 1}:
            raise ValidationError("Only one motel settings record is allowed.")

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def,override]
        self.singleton_id = 1
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def active_operating_mode(cls) -> str:
        """Return the active operating mode without creating records at runtime."""
        return (
            cls.objects.filter(pk=1)
            .values_list("operating_mode", flat=True)
            .first()
            or cls.OperatingMode.POS_HANDS_ON_MODE
        )

    def __str__(self) -> str:
        return "Motel operational settings"
