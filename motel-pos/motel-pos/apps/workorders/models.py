"""Work order models for ad hoc and planned maintenance tasks."""

from django.conf import settings
from django.db import models


class WorkOrder(models.Model):
    """A maintenance task that needs to be completed."""

    class Source(models.TextChoices):
        AD_HOC = "adhoc", "Ad Hoc"
        PLANNED_MAINTENANCE = "pm", "Planned Maintenance"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        IN_PROGRESS = "in_progress", "In Progress"
        WAITING_FOR_PARTS = "waiting_parts", "Waiting for Parts"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="work_orders")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.OPEN,
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.AD_HOC)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_work_orders",
    )
    assigned_to_label = models.CharField(max_length=100, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_work_orders",
    )
    due_date = models.DateField(null=True, blank=True)
    estimated_minutes = models.PositiveIntegerField(null=True, blank=True)
    instructions = models.TextField(blank=True)
    location_notes = models.TextField(blank=True)
    safety_notes = models.TextField(blank=True)
    checklist = models.JSONField(default=list, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_work_orders",
    )
    completion_notes = models.TextField(blank=True)
    parts_used = models.TextField(blank=True)
    issues_found = models.TextField(blank=True)
    time_spent_minutes = models.PositiveIntegerField(null=True, blank=True)
    planned_template = models.ForeignKey(
        "maintenance.PlannedMaintenanceTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_orders",
    )
    planned_occurrence = models.OneToOneField(
        "maintenance.PlannedMaintenanceOccurrence",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="work_order_link",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-due_date"]
        indexes = [
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["room", "due_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.room})"

    @property
    def is_open(self) -> bool:
        """Return True when the work order still needs attention."""
        return self.status not in {self.Status.COMPLETED, self.Status.CANCELLED}
