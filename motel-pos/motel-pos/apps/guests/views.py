"""API views for vehicle/customer tracking."""

import re
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import filters, viewsets

from apps.core.permissions import DjangoActionPermissions
from apps.guests.models import Vehicle, VehicleShape
from apps.guests.serializers import VehicleSerializer, VehicleShapeSerializer


def _normalize_plate_search(value: str) -> str:
    """Normalize a plate search string to match stored plate identity."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


@login_required
@ensure_csrf_cookie
def vehicle_manager_view(request):  # type: ignore[no-untyped-def]
    """Render the dedicated manager vehicle workspace."""
    if not request.user.has_perm("guests.change_vehicle"):
        raise PermissionDenied("Manager access required.")
    return render(request, "guests/vehicle_manager.html", {"user": request.user})


class VehicleViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """Search and maintain customer vehicle records."""

    queryset = Vehicle.objects.select_related("vehicle_shape").prefetch_related(
        "current_rooms", "rental_sessions"
    )
    serializer_class = VehicleSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "guests.view_vehicle",
        "retrieve": "guests.view_vehicle",
        "create": "guests.add_vehicle",
        "update": "guests.change_vehicle",
        "partial_update": "guests.change_vehicle",
        "destroy": "guests.delete_vehicle",
    }
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "license_plate",
        "license_plate_normalized",
        "make",
        "model",
        "color",
        "vehicle_shape__name",
        "notes",
        "current_rooms__room_id",
        "current_rooms__room_number",
        "rental_sessions__room_id",
        "rental_sessions__status",
        "rental_sessions__notes",
    ]
    ordering_fields = [
        "created_at",
        "updated_at",
        "license_plate",
        "make",
        "model",
        "color",
        "vehicle_shape__name",
    ]
    ordering = ["-updated_at"]

    def filter_queryset(self, queryset: Any) -> Any:
        """Search vehicle identity fields plus current and historical room context."""
        filtered = super().filter_queryset(queryset)
        search = self.request.query_params.get("search")
        if search:
            normalized_search = _normalize_plate_search(search)
            if normalized_search:
                filtered = filtered | queryset.filter(
                    license_plate_normalized__icontains=normalized_search
                )
            return filtered.distinct()
        return filtered


class VehicleShapeViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore[type-arg]
    """Expose active admin-managed choices to front-desk forms."""

    serializer_class = VehicleShapeSerializer
    pagination_class = None
    permission_classes = [DjangoActionPermissions]
    default_permission = "guests.view_vehicleshape"
    permission_map = {
        "list": "guests.view_vehicleshape",
        "retrieve": "guests.view_vehicleshape",
    }
    queryset = VehicleShape.objects.filter(active=True).order_by("sort_order", "name")
