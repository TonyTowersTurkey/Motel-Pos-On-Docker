"""Revenue-related models for motel occupancy system.

Maps from existing SQLAlchemy models:
    OccupancySession → OccupancySession
    ShiftLedger → ShiftLedger
"""

from decimal import Decimal

from django.db import models


class OccupancySession(models.Model):  # type: ignore[misc]
    """Tracks guest stays with pricing for revenue calculation.

    Maps from SQLAlchemy app.database.OccupancySession.
    Populated by the state machine and manual override at check-in/checkout.
    """

    class Source(models.TextChoices):
        SENSOR_AUTO = "sensor_auto", "Sensor Auto"
        MANUAL_OVERRIDE = "manual_override", "Manual Override"
        FRONT_DESK = "front_desk", "Front Desk"
        ROOM_PULSE = "room_pulse", "Room Pulse"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CHECKED_OUT = "checked_out", "Checked Out"
        CANCELLED = "cancelled", "Cancelled"

    id = models.AutoField(primary_key=True)
    room_id = models.CharField(max_length=50, db_index=True)
    guest_name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=30, blank=True, default="")
    license_plate = models.CharField(max_length=30, blank=True, default="")
    check_in = models.DateTimeField(db_index=True)
    check_out = models.DateTimeField(null=True, blank=True)
    room_type_code = models.CharField(max_length=20, blank=True, default="")
    price_per_night = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )  # type: ignore[misc]
    amenities_charges = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    estimated_revenue = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )  # type: ignore[misc]
    actual_revenue = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )  # type: ignore[misc]
    source = models.CharField(max_length=20, choices=Source.choices)
    status = models.CharField(max_length=20, choices=Status.choices)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "occupancy_sessions"
        verbose_name = "occupancy session"
        verbose_name_plural = "occupancy sessions"
        ordering = ["-check_in"]
        indexes = [
            models.Index(fields=["room_id", "-check_in"]),
            models.Index(fields=["status"]),
            models.Index(fields=["check_out", "status"]),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Session #{self.pk} - Room {self.room_id}"

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def,override]
        """Store historical license plate characters in uppercase."""
        self.license_plate = (self.license_plate or "").upper()
        super().save(*args, **kwargs)


class ShiftLedger(models.Model):  # type: ignore[misc]
    """Daily shift ledger matching the manual Cuadre ATH report format.

    Maps from SQLAlchemy app.database.ShiftLedger.
    """

    date = models.DateField(db_index=True)
    shift_number = models.IntegerField()

    # Per-tier counts (from paper Cuadre format)
    tier_1_bgo_count = models.IntegerField(default=0)
    tier_2_y0_dndein_count = models.IntegerField(default=0)
    tier_3_boo_count = models.IntegerField(default=0)
    tier_4_buys_count = models.IntegerField(default=0)
    tier_5_s0_luxury_count = models.IntegerField(default=0)

    # Per-tier revenues
    tier_1_bgo_revenue = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    tier_2_y0_dndein_revenue = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    tier_3_boo_revenue = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    tier_4_buys_revenue = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    tier_5_s0_luxury_revenue = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]

    # Totals (calculated columns populated at save time)
    subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    barra_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]
    ath_subtotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )  # type: ignore[misc]

    logged_by = models.CharField(max_length=100, blank=True, default="")
    verified_by = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "shift_ledger"
        verbose_name = "shift ledger"
        verbose_name_plural = "shift ledgers"
        ordering = ["-date", "-shift_number"]
        permissions = [
            ("view_shift_reports", "Can view shift reports"),
            ("generate_shift", "Can generate and save a shift ledger"),
            ("generate_management_reports", "Can generate management reports"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "shift_number"], name="unique_shift_per_day"
            ),
        ]

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Calculate and store subtotal/ATH totals before saving."""
        tier_revenues = [
            self.tier_1_bgo_revenue,
            self.tier_2_y0_dndein_revenue,
            self.tier_3_boo_revenue,
            self.tier_4_buys_revenue,
            self.tier_5_s0_luxury_revenue,
        ]
        self.subtotal = sum(rev for rev in tier_revenues if rev is not None)
        self.ath_subtotal = self.subtotal + self.barra_amount  # type: ignore[operator]
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # type: ignore[override]
        return f"Shift {self.shift_number} - {self.date}"
