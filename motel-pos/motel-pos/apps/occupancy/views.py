"""Occupancy history, audit views, and the Room Pulse receiver."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, ClassVar

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.permissions import DjangoActionPermissions
from apps.occupancy.models import AuditLog, OccupancyEvent
from apps.occupancy.serializers import (
    AuditLogSerializer,
    OccupancyEventSerializer,
    RoomPulseWebhookSerializer,
)
from apps.occupancy.services import occupancy_service

if TYPE_CHECKING:
    from rest_framework.request import Request


class RoomPulseWebhookView(APIView):
    """Receive authenticated, idempotent Room Pulse 1.0 snapshots."""

    authentication_classes: ClassVar[tuple] = ()
    permission_classes: ClassVar[tuple] = (AllowAny,)
    throttle_classes: ClassVar[tuple] = (ScopedRateThrottle,)
    throttle_scope = "room_pulse"

    @staticmethod
    def _bearer_token(request: Request) -> str | None:
        authorization = request.headers.get("Authorization", "")
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":  # noqa: PLR2004
            return None
        return parts[1]

    def post(self, request: Request) -> Response:
        """Authenticate, validate, and durably apply a complete snapshot."""
        if (
            settings.ROOM_PULSE_REQUIRE_HTTPS
            and not settings.DEBUG
            and not request.is_secure()
        ):
            return Response(
                {"detail": "HTTPS is required for this webhook."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        configured_token = settings.ROOM_PULSE_WEBHOOK_TOKEN
        if not configured_token and not settings.DEBUG:
            return Response(
                {"detail": "Room Pulse webhook is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if configured_token:
            provided_token = self._bearer_token(request)
            if provided_token is None or not secrets.compare_digest(
                provided_token, configured_token
            ):
                response = Response(
                    {"detail": "Invalid webhook credentials."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
                response["WWW-Authenticate"] = "Bearer"
                return response

        serializer = RoomPulseWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        header_event_id = request.headers.get("X-Room-Pulse-Event", "")
        body_event_id = str(serializer.validated_data["event_id"])
        if not secrets.compare_digest(header_event_id.lower(), body_event_id.lower()):
            return Response(
                {"X-Room-Pulse-Event": "Must match the body event_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = occupancy_service.ingest_room_pulse_snapshot(
            serializer.validated_data,
            dict(request.data),
        )
        return Response(result, status=status.HTTP_200_OK)


class OccupancyEventViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for occupancy event history."""

    queryset = OccupancyEvent.objects.all()
    serializer_class = OccupancyEventSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "occupancy.view_occupancyevent",
        "retrieve": "occupancy.view_occupancyevent",
        "create": "occupancy.add_occupancyevent",
        "update": "occupancy.change_occupancyevent",
        "partial_update": "occupancy.change_occupancyevent",
        "destroy": "occupancy.delete_occupancyevent",
    }

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter events by optional query parameters."""
        qs = OccupancyEvent.objects.all().order_by("-timestamp")
        room_id = self.request.query_params.get("room_id") if self.request else None  # type: ignore[attr-defined]
        if room_id:
            qs = qs.filter(room_id=room_id)
        event_type = (
            self.request.query_params.get("event_type") if self.request else None
        )  # type: ignore[attr-defined]
        if event_type:
            event_types = [
                value.strip()
                for value in event_type.split(",")
                if value.strip()
            ]
            qs = qs.filter(event_type__in=event_types)
        return qs


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):  # type: ignore[type-arg]
    """ReadOnly ViewSet for audit logs (manager/admin only)."""

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [DjangoActionPermissions]
    default_permission = "occupancy.view_auditlog"
    permission_map = {
        "list": "occupancy.view_auditlog",
        "retrieve": "occupancy.view_auditlog",
    }
