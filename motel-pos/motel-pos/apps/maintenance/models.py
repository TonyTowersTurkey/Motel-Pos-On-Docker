"""Planned maintenance models."""

from django.db import models

from apps.workorders.models import WorkOrder


class PlannedMaintenanceTemplate(models.Model):
    """A recurring maintenance rule that can create room work orders."""

    class FrequencyUnit(models.TextChoices):
        DAYS = "days", "Days"
        WEEKS = "weeks", "Weeks"
        MONTHS = "months", "Months"
        YEARS = "years", "Years"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    default_priority = models.CharField(
        max_length=20,
        choices=WorkOrder.Priority.choices,
        default=WorkOrder.Priority.NORMAL,
    )
    frequency_value = models.PositiveIntegerField(default=6)
    frequency_unit = models.CharField(
        max_length=10,
        choices=FrequencyUnit.choices,
        default=FrequencyUnit.MONTHS,
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    auto_create_work_orders = models.BooleanField(default=True)
    create_days_before_due = models.PositiveIntegerField(default=7)
    estimated_minutes_per_room = models.PositiveIntegerField(default=20)
    all_rooms = models.BooleanField(default=False)
    rooms = models.ManyToManyField("rooms.Room", blank=True, related_name="maintenance_templates")
    room_groups = models.ManyToManyField(
        "rooms.RoomGroup",
        blank=True,
        related_name="maintenance_templates",
    )
    target_building = models.CharField(max_length=100, blank=True)
    target_floor = models.CharField(max_length=50, blank=True)
    target_room_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PlannedMaintenanceOccurrence(models.Model):
    """A scheduled occurrence for one room on one due date."""

    template = models.ForeignKey(
        PlannedMaintenanceTemplate,
        on_delete=models.CASCADE,
        related_name="occurrences",
    )
    room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="maintenance_occurrences")
    due_date = models.DateField()
    work_order = models.OneToOneField(
        "workorders.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_occurrence_record",
    )
    is_skipped = models.BooleanField(default=False)
    skipped_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "room__room_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "room", "due_date"],
                name="unique_template_room_due_date",
            )
        ]

    def __str__(self) -> str:
        return f"{self.template} / {self.room} / {self.due_date}"
