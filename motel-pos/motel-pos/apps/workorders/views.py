"""ViewSets for work order CRUD."""

from __future__ import annotations

from rest_framework import filters, viewsets

from apps.core.permissions import DjangoActionPermissions
from apps.workorders.models import WorkOrder
from apps.workorders.serializers import WorkOrderSerializer


class WorkOrderViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """Create, update, and inspect work orders from the maintenance UI."""

    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "workorders.view_workorder",
        "retrieve": "workorders.view_workorder",
        "create": "workorders.add_workorder",
        "update": "workorders.change_workorder",
        "partial_update": "workorders.change_workorder",
        "destroy": "workorders.delete_workorder",
    }
    queryset = WorkOrder.objects.select_related("room", "assigned_to", "created_by")
    serializer_class = WorkOrderSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "title",
        "description",
        "category",
        "room__room_number",
        "room__room_id",
        "assigned_to_label",
    ]
    ordering_fields = ["created_at", "updated_at", "due_date", "priority", "status"]
    ordering = ["-created_at", "-due_date"]
