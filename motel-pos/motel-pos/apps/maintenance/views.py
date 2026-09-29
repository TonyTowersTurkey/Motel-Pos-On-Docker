"""API and frontend views for maintenance planning and work-order pages."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import DjangoActionPermissions
from apps.maintenance.mock_data import (
    MAINTENANCE_ASSIGNEES,
    MAINTENANCE_CATEGORY_CHOICES,
    MAINTENANCE_FILTERS,
    MAINTENANCE_FREQUENCY_OPTIONS,
    MAINTENANCE_METRICS,
    MAINTENANCE_PREVIEW_DAYS,
    MAINTENANCE_PRIORITY_CHOICES,
    MAINTENANCE_ROOM_ASSIGNMENT_OPTIONS,
    MAINTENANCE_ROOM_CHOICES,
    MAINTENANCE_ROOMS,
    MAINTENANCE_TEMPLATES,
    MAINTENANCE_WORK_ORDERS,
    MAINTENANCE_WORK_QUEUES,
)
from apps.maintenance.models import PlannedMaintenanceTemplate
from apps.maintenance.serializers import (
    PlannedMaintenancePreviewRequestSerializer,
    PlannedMaintenancePreviewSerializer,
    PlannedMaintenancePreviewSlotSerializer,
    PlannedMaintenanceTemplateSerializer,
)
from apps.maintenance.services import build_calendar_preview
from apps.workorders.models import WorkOrder
from apps.workorders.serializers import serialize_work_orders


MAINTENANCE_NAV = [
    {'label': 'Dashboard', 'url_name': 'maintenance:maintenance-dashboard', 'active_name': 'dashboard'},
    {'label': 'Work To Do', 'url_name': 'maintenance:maintenance-work-to-do', 'active_name': 'work-to-do'},
    {'label': 'Ad Hoc WO', 'url_name': 'maintenance:maintenance-work-order-new', 'active_name': 'work-order-new'},
    {'label': 'Planned PM', 'url_name': 'maintenance:maintenance-planned', 'active_name': 'planned'},
    {'label': 'Calendar', 'url_name': 'maintenance:maintenance-calendar-preview', 'active_name': 'calendar-preview'},
    {'label': 'Rooms', 'url_name': 'maintenance:maintenance-rooms', 'active_name': 'rooms'},
]


def _work_order_payload() -> list[dict[str, object]]:
    """Use live work orders when they exist, otherwise fall back to the MVP mock data."""
    live_work_orders = serialize_work_orders(
        WorkOrder.objects.select_related('room', 'assigned_to', 'created_by').all()[:50]
    )
    return live_work_orders or MAINTENANCE_WORK_ORDERS


def _maintenance_context(page_title: str, active: str, **extra: object) -> dict[str, object]:
    """Build the shared maintenance page context."""
    work_orders = extra.pop('work_orders', None)
    return {
        'page_title': page_title,
        'active_nav': active,
        'nav_items': MAINTENANCE_NAV,
        'today': date.today(),
        'room_choices': MAINTENANCE_ROOM_CHOICES,
        'category_choices': MAINTENANCE_CATEGORY_CHOICES,
        'priority_choices': MAINTENANCE_PRIORITY_CHOICES,
        'assignees': MAINTENANCE_ASSIGNEES,
        'work_orders': work_orders if work_orders is not None else _work_order_payload(),
        **extra,
    }


def _require_manager_or_admin(user: object) -> None:
    """Restrict maintenance pages to operational management roles."""
    if not user.has_perm("workorders.view_workorder"):  # type: ignore[attr-defined]
        raise PermissionDenied("Manager access required.")


@login_required
def maintenance_dashboard_view(request):  # type: ignore[no-untyped-def]
    """Render the MVP maintenance dashboard shell."""
    _require_manager_or_admin(request.user)
    metrics = MAINTENANCE_METRICS
    filters = MAINTENANCE_FILTERS
    work_orders = _work_order_payload()
    return render(
        request,
        'maintenance/dashboard.html',
        _maintenance_context(
            'Maintenance Dashboard',
            'dashboard',
            metrics=metrics,
            filters=filters,
            work_orders=work_orders,
        ),
    )


@login_required
def maintenance_work_to_do_view(request):  # type: ignore[no-untyped-def]
    """Render the maintenance staff task queue."""
    _require_manager_or_admin(request.user)
    queues = MAINTENANCE_WORK_QUEUES
    return render(
        request,
        'maintenance/work_to_do.html',
        _maintenance_context('Work To Be Done', 'work-to-do', queues=queues),
    )


@login_required
def maintenance_work_order_new_view(request):  # type: ignore[no-untyped-def]
    """Render the ad hoc work-order creation shell."""
    _require_manager_or_admin(request.user)
    return render(
        request,
        'maintenance/work_order_form.html',
        _maintenance_context(
            'New Work Order',
            'work-order-new',
            room_choices=MAINTENANCE_ROOM_CHOICES,
            category_choices=MAINTENANCE_CATEGORY_CHOICES,
            priority_choices=MAINTENANCE_PRIORITY_CHOICES,
            assignees=MAINTENANCE_ASSIGNEES,
        ),
    )


@login_required
def maintenance_planned_view(request):  # type: ignore[no-untyped-def]
    """Render the planned maintenance template manager."""
    _require_manager_or_admin(request.user)
    templates = MAINTENANCE_TEMPLATES
    return render(
        request,
        'maintenance/planned_maintenance.html',
        _maintenance_context(
            'Planned Maintenance',
            'planned',
            templates=templates,
            frequency_options=MAINTENANCE_FREQUENCY_OPTIONS,
            room_assignment_options=MAINTENANCE_ROOM_ASSIGNMENT_OPTIONS,
        ),
    )


@login_required
def maintenance_calendar_preview_view(request):  # type: ignore[no-untyped-def]
    """Render the PM calendar preview shell."""
    _require_manager_or_admin(request.user)
    preview_days = MAINTENANCE_PREVIEW_DAYS
    return render(
        request,
        'maintenance/calendar_preview.html',
        _maintenance_context(
            'PM Calendar Preview',
            'calendar-preview',
            preview_days=preview_days,
        ),
    )


@login_required
def maintenance_rooms_view(request):  # type: ignore[no-untyped-def]
    """Render the room assignment and maintenance metadata shell."""
    _require_manager_or_admin(request.user)
    rooms = MAINTENANCE_ROOMS
    return render(
        request,
        'maintenance/rooms.html',
        _maintenance_context('Maintenance Rooms', 'rooms', rooms=rooms),
    )


class PlannedMaintenanceTemplateViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """Create, inspect, and preview recurring maintenance templates."""

    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "maintenance.view_plannedmaintenancetemplate",
        "retrieve": "maintenance.view_plannedmaintenancetemplate",
        "create": "maintenance.add_plannedmaintenancetemplate",
        "update": "maintenance.change_plannedmaintenancetemplate",
        "partial_update": "maintenance.change_plannedmaintenancetemplate",
        "destroy": "maintenance.delete_plannedmaintenancetemplate",
        "preview": "maintenance.view_plannedmaintenancetemplate",
    }
    queryset = PlannedMaintenanceTemplate.objects.prefetch_related('rooms', 'room_groups')
    serializer_class = PlannedMaintenanceTemplateSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'name',
        'description',
        'category',
        'target_building',
        'target_floor',
        'target_room_type',
        'rooms__room_number',
        'room_groups__name',
    ]
    ordering_fields = ['name', 'created_at', 'updated_at', 'start_date', 'frequency_value']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):  # type: ignore[no-untyped-def]
        """Return a computed preview for a single template."""
        template = self.get_object()
        params = PlannedMaintenancePreviewRequestSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)

        rooms_per_day = params.validated_data.get('rooms_per_day', 15)
        today = params.validated_data.get('today')
        preview_slots = build_calendar_preview(
            template,
            rooms_per_day=rooms_per_day,
            today=today,
        )

        payload = {
            'template_id': template.id,
            'template_name': template.name,
            'cycle_due_date': preview_slots[0].due_date if preview_slots else template.start_date,
            'rooms_per_day': rooms_per_day,
            'total_rooms': len(preview_slots),
            'estimated_total_minutes': sum(slot.estimated_minutes for slot in preview_slots),
            'slots': [
                PlannedMaintenancePreviewSlotSerializer(slot).data
                for slot in preview_slots
            ],
        }
        serializer = PlannedMaintenancePreviewSerializer(payload)
        return Response(serializer.data)
