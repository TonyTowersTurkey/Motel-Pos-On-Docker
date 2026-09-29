"""Room-related models for motel occupancy system.

Maps from SQLAlchemy app.database:
    Room -> Room
    PricingTier -> PricingTier
    Amenity -> Amenity
    RoomAmenity -> RoomAmenity
    MaintenanceLog -> MaintenanceLog
    RentalSession -> RentalSession
"""

from django.core.validators import RegexValidator
from django.db import models


numeric_room_id = RegexValidator(r"^[0-9]+$", "Room ID must contain numbers only.")


class Room(models.Model):  # type: ignore[misc]
    """Room with pricing tier and amenity support.

    Maps from SQLAlchemy app.database.Room.
    """

    room_id = models.CharField(max_length=50, primary_key=True, validators=[numeric_room_id])
    room_number = models.CharField(max_length=50)
    sensor_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Legacy external device identifier; not used for room-status ingestion.",
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    pricing_tier_code = models.CharField(max_length=20, blank=True, default="")
    price = models.IntegerField(default=0)
    ac = models.CharField(max_length=100, blank=True, default="")
    tv = models.CharField(max_length=100, blank=True, default="")
    edificio = models.CharField(max_length=100, blank=True, default="")
    cuenta_luma = models.IntegerField(default=0)
    max_occupants = models.IntegerField(default=1)
    amenities_snapshot = models.TextField(blank=True, default="")
    current_state = models.CharField(
        max_length=30,
        default="vacant",
        blank=True,
        help_text="Current occupancy state (from state machine).",
    )
    current_vehicle = models.ForeignKey(
        "guests.Vehicle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_rooms",
        help_text="Vehicle currently associated with this room.",
    )

    class Meta:
        db_table = "rooms"
        verbose_name = "room"
        verbose_name_plural = "rooms"
        ordering = ["room_number"]
        permissions = [
            ("operate_room", "Can perform front-desk room operations"),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Room {self.room_number} ({self.room_id})"


class RoomGroup(models.Model):  # type: ignore[misc]
    """Reusable grouping of rooms for maintenance and operations."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    rooms = models.ManyToManyField(
        Room,
        related_name="groups",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "room_groups"
        verbose_name = "room group"
        verbose_name_plural = "room groups"
        ordering = ["name"]

    def __str__(self) -> str:  # type: ignore[override]
        return self.name


class PricingTier(models.Model):  # type: ignore[misc]
    """Pricing tier definition from paper Cuadre reports.

    Maps from SQLAlchemy app.database.PricingTier.
    """

    code = models.CharField(max_length=20, unique=True)
    price_per_night = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,  # type: ignore[misc]
    )
    description = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "pricing_tiers"
        verbose_name = "pricing tier"
        verbose_name_plural = "pricing tiers"
        ordering = ["code"]

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.code} - ${float(self.price_per_night):.2f}"


class Amenity(models.Model):  # type: ignore[misc]
    """Available room amenities with optional price surcharge.

    Maps from SQLAlchemy app.database.Amenity.
    """

    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    icon_class = models.CharField(max_length=50, blank=True, default="")  # type: ignore[misc]
    price_surcharge = models.DecimalField(  # type: ignore[misc]
        max_digits=6, decimal_places=2, default=0.00
    )

    class Meta:
        db_table = "amenities"
        verbose_name = "amenity"
        verbose_name_plural = "amenities"
        ordering = ["name"]

    def __str__(self) -> str:  # type: ignore[override]
        return self.display_name


class RoomAmenity(models.Model):  # type: ignore[misc]
    """Junction table: rooms have many amenities,amenities on many rooms."""

    class AmenityStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        UNDER_REPAIR = "under_repair", "Under Repair"

    room_id = models.CharField(max_length=50)
    amenity_id = models.IntegerField()
    status = models.CharField(
        max_length=20, choices=AmenityStatus.choices,
        default=AmenityStatus.ACTIVE,
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "room_amenities"
        verbose_name = "room amenity"
        verbose_name_plural = "room amenities"
        constraints = [
            models.UniqueConstraint(
                fields=["room_id", "amenity_id"], name="unique_room_amenity"
            ),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"{self.room_id} - Amenity {self.amenity_id} ({self.status})"


class MaintenanceLog(models.Model):  # type: ignore[misc]
    """Per-room maintenance history with cost tracking."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    room_id = models.CharField(max_length=50)
    category = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_recurring = models.BooleanField(default=False)
    recurrence_interval_days = models.IntegerField(null=True, blank=True)
    last_performed = models.DateField(null=True, blank=True)
    next_due = models.DateField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    assigned_to = models.CharField(max_length=100, blank=True, default="")
    vendor_contact = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    completion_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "maintenance_log"
        verbose_name = "maintenance log"
        verbose_name_plural = "maintenance logs"
        ordering = ["-created_at"]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Maintenance #{self.pk} - Room {self.room_id}"


class RentalSession(models.Model):  # type: ignore[misc]
    """Rental session tracking for room bookings."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"
        CHECKED_IN = "checked_in", "Checked In"
        CHECKED_OUT = "checked_out", "Checked Out"
        CANCELLED = "cancelled", "Cancelled"

    session_id = models.AutoField(primary_key=True)
    room_id = models.CharField(max_length=50)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual room exit time; end time remains the billed stay boundary.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    source = models.CharField(max_length=50)
    vehicle = models.ForeignKey(
        "guests.Vehicle",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rental_sessions",
        help_text="Vehicle associated with this rental session.",
    )
    reviewed_by = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "rental_sessions"
        verbose_name = "rental session"
        verbose_name_plural = "rental sessions"
        ordering = ["-start_time"]
        permissions = [
            ("extend_rentalsession", "Can extend a rental session"),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        return f"Session #{self.pk} - Room {self.room_id}"


# =================================================
# Dynamic Pricing (Phase 2a extension - multi-rate tiers)
# =================================================


class DayOfWeek(models.TextChoices):
    """Day of week choices for recurring pricing rules."""

    MONDAY = "mon", "Monday"
    TUESDAY = "tue", "Tuesday"
    WEDNESDAY = "wed", "Wednesday"
    THURSDAY = "thu", "Thursday"
    FRIDAY = "fri", "Friday"
    SATURDAY = "sat", "Saturday"
    SUNDAY = "sun", "Sunday"


class DynamicPricingRule(models.Model):  # type: ignore[misc]
    """Price override rules for multi-rate pricing tiers.

    Supports seasonal rates and day-of-week variation.
    Resolution: base price -> active rule (highest priority) -> fallback.
    """

    class RuleType(models.TextChoices):
        SEASONAL = "seasonal", "Seasonal (date range)"
        DAY_OF_WEEK = "day_of_week", "Day-of-week recurring"
        SPECIAL = "special", "Special date override"

    tier_code = models.CharField(
        max_length=20, help_text="Pricing tier code this rule applies to."
    )
    name = models.CharField(max_length=100, blank=True, default="", null=True)

    rule_type = models.CharField(max_length=20, choices=RuleType.choices)
    start_date = models.DateField(help_text="Start of the price window.")
    end_date = models.DateField(
        blank=True, null=True, help_text="Inclusive end date. NULL for open-ended."
    )

    day_of_week = models.CharField(
        max_length=3, blank=True, choices=DayOfWeek.choices,
        help_text="Which weekday(s). Empty means all days in the window.",
    )

    price_override = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Price per night to use when this rule is active.",
    )

    description = models.TextField(blank=True, default="", null=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=100, help_text="Higher priority wins in conflicts.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_pricing_rules"
        ordering = ["-priority"]
        constraints = [
            models.UniqueConstraint(
                fields=["tier_code", "rule_type", "day_of_week"],
                name="unique_tier_day_rule",
                condition=models.Q(rule_type="day_of_week", is_active=True),
                violation_error_message="Active day-of-week rule for this tier/day already exists.",
            ),
        ]

    def __str__(self) -> str:  # type: ignore[override]
        part = self.name or f"{self.rule_type} {self.tier_code}"
        if self.day_of_week:
            part += f" ({self.day_of_week})"
        return f"{part} - ${float(self.price_override):.2f}"

    def is_date_in_window(self, target_date) -> bool:  # type: ignore[override]
        """Check if a date falls within this rule's effective window."""
        if not self.is_active or not self.start_date:
            return False
        if self.rule_type == DynamicPricingRule.RuleType.SEASONAL:
            end = self.end_date or target_date
            return self.start_date <= target_date <= end
        elif self.rule_type == DynamicPricingRule.RuleType.SPECIAL:
            if not self.start_date:
                return False
            end = self.end_date or self.start_date
            return self.start_date <= target_date <= end
        return False

    def matches_day(self, day_of_week_int: int) -> bool:  # type: ignore[override]
        """Check if the rule applies to a given Python weekday (0=Monday)."""
        if not self.day_of_week or not self.start_date:
            return False
        dw_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6,
        }
        target_dow = dw_map.get(self.day_of_week.lower())
        return target_dow is not None and target_dow == day_of_week_int
