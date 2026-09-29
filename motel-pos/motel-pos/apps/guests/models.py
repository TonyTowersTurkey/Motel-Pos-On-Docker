"""Vehicle records for cashier-facing customer tracking."""

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q


def normalize_license_plate(value: str) -> str:
    """Normalize a license plate for duplicate checks."""
    return "".join(value.upper().split())


def validate_vehicle_shape_icon_size(value) -> None:  # type: ignore[no-untyped-def]
    """Keep lookup icons small enough for quick cashier dashboard loading."""
    max_size = 2 * 1024 * 1024
    if value.size > max_size:
        raise ValidationError("Vehicle shape icons must be 2 MB or smaller.")


class VehicleShape(models.Model):  # type: ignore[misc]
    """Manager-maintained vehicle body styles offered to front-desk staff."""

    name = models.CharField(max_length=50, unique=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    icon = models.ImageField(
        upload_to="vehicle-shapes/",
        blank=True,
        validators=[
            FileExtensionValidator(["png", "jpg", "jpeg", "webp"]),
            validate_vehicle_shape_icon_size,
        ],
        help_text="Upload a simple PNG, JPEG, or WebP silhouette (maximum 2 MB).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vehicle_shapes"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Vehicle(models.Model):  # type: ignore[misc]
    """Customer vehicle identity without personal guest details."""

    make = models.CharField(max_length=80, blank=True, default="")
    model = models.CharField(max_length=80, blank=True, default="")
    color = models.CharField(max_length=50, blank=True, default="")
    vehicle_shape = models.ForeignKey(
        VehicleShape,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vehicles",
    )
    license_plate = models.CharField(max_length=30, blank=True, default="")
    license_plate_normalized = models.CharField(
        max_length=30,
        blank=True,
        default="",
        editable=False,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vehicles"
        verbose_name = "vehicle"
        verbose_name_plural = "vehicles"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["license_plate_normalized"],
                condition=~Q(license_plate_normalized=""),
                name="unique_nonblank_vehicle_plate",
            ),
        ]

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def,override]
        """Store plate characters uppercase and keep duplicate detection normalized."""
        self.license_plate = (self.license_plate or "").upper()
        self.license_plate_normalized = normalize_license_plate(self.license_plate)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "license_plate" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"license_plate_normalized"}
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # type: ignore[override]
        label = " ".join(part for part in [self.color, self.make, self.model] if part)
        if self.license_plate:
            return f"{self.license_plate} - {label or 'Vehicle'}"
        return label or f"Vehicle #{self.pk}"
