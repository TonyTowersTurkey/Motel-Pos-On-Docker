"""Helpers for planned maintenance preview and occurrence generation."""

from __future__ import annotations

from datetime import date

from django.db import transaction

from apps.maintenance.models import PlannedMaintenanceOccurrence, PlannedMaintenanceTemplate
from apps.maintenance.planner import (
    RoomTarget,
    PreviewSlot,
    build_preview_slots,
    next_due_date,
)
from apps.rooms.models import Room
from apps.workorders.models import WorkOrder


def _room_field_names() -> set[str]:
    return {field.name for field in Room._meta.get_fields()}


def get_template_rooms(template: PlannedMaintenanceTemplate) -> list[Room]:
    """Resolve the rooms that a template applies to."""
    room_fields = _room_field_names()
    rooms = Room.objects.none()
    active_field = 'active' if 'active' in room_fields else 'is_active' if 'is_active' in room_fields else None
    if template.all_rooms:
        rooms = Room.objects.all()
        if active_field:
            rooms = rooms.filter(**{active_field: True})
    else:
        room_ids = set(template.rooms.values_list('pk', flat=True))
        group_rooms = template.room_groups.prefetch_related('rooms')
        for group in group_rooms:
            room_ids.update(group.rooms.values_list('pk', flat=True))
        if room_ids:
            rooms = Room.objects.filter(pk__in=room_ids)

    if template.target_building:
        if 'building' in room_fields:
            rooms = rooms.filter(building=template.target_building)
        elif 'edificio' in room_fields:
            rooms = rooms.filter(edificio=template.target_building)
    if template.target_floor and 'floor' in room_fields:
        rooms = rooms.filter(floor=template.target_floor)
    if template.target_room_type and 'room_type' in room_fields:
        rooms = rooms.filter(room_type=template.target_room_type)

    return list(rooms.order_by('room_number'))


def get_next_due_date(
    template: PlannedMaintenanceTemplate,
    today: date | None = None,
) -> date:
    """Return the next cycle due date on or after today."""
    return next_due_date(
        template.start_date,
        template.frequency_value,
        template.frequency_unit,
        today=today,
    )


def build_calendar_preview(
    template: PlannedMaintenanceTemplate,
    *,
    rooms_per_day: int = 15,
    today: date | None = None,
) -> list[PreviewSlot]:
    """Spread the next PM cycle across one or more days."""
    rooms = get_template_rooms(template)
    if not rooms:
        return []

    cycle_due_date = get_next_due_date(template, today=today)
    room_targets = [RoomTarget(room_id=str(room.pk), room_number=room.room_number) for room in rooms]
    return build_preview_slots(
        room_targets,
        cycle_due_date,
        rooms_per_day=rooms_per_day,
        estimated_minutes=template.estimated_minutes_per_room,
    )


@transaction.atomic
def ensure_pm_occurrences(
    template: PlannedMaintenanceTemplate,
    *,
    rooms_per_day: int = 15,
    today: date | None = None,
) -> list[PlannedMaintenanceOccurrence]:
    """Create any missing PM occurrences for the next cycle."""
    preview = build_calendar_preview(template, rooms_per_day=rooms_per_day, today=today)
    occurrences: list[PlannedMaintenanceOccurrence] = []

    for item in preview:
        room = Room.objects.get(pk=item.room_id)
        occurrence, _created = PlannedMaintenanceOccurrence.objects.get_or_create(
            template=template,
            room=room,
            due_date=item.due_date,
        )
        occurrences.append(occurrence)

        if template.auto_create_work_orders and occurrence.work_order_id is None:
            work_order = WorkOrder.objects.create(
                room=room,
                title=template.name,
                description=template.description,
                category=template.category,
                priority=template.default_priority,
                status=WorkOrder.Status.OPEN,
                source=WorkOrder.Source.PLANNED_MAINTENANCE,
                due_date=item.due_date,
                planned_template=template,
                planned_occurrence=occurrence,
            )
            occurrence.work_order = work_order
            occurrence.save(update_fields=['work_order', 'updated_at'])

    return occurrences
