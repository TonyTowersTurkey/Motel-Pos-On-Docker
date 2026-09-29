"""Views for room management - DRF ViewSets and API views."""

from datetime import date, datetime, time, timedelta
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import DjangoActionPermissions
from apps.guests.models import Vehicle
from apps.occupancy.models import OccupancyEvent
from apps.rooms.models import (
    Amenity,
    MaintenanceLog,
    PricingTier,
    RentalSession,
    Room,
    RoomAmenity,
)
from apps.rooms.serializers import (
    AmenitySerializer,
    MaintenanceLogSerializer,
    PricingTierSerializer,
    RentalSessionSerializer,
    RoomAmenitySerializer,
    RoomSerializer,
)

RENTAL_SHIFT_WINDOWS = {
    1: (time(23, 0), time(7, 0)),
    2: (time(7, 0), time(15, 0)),
    3: (time(15, 0), time(23, 0)),
}
RENTAL_DURATION_HOURS = {8, 16, 24}


def _rental_shift_bounds(target_date: date, shift_number: int) -> tuple[Any, Any]:
    """Return half-open aware bounds for a shift assigned to target_date."""
    if shift_number not in RENTAL_SHIFT_WINDOWS:
        raise ValueError("shift must be 1, 2, or 3")
    start_time, end_time = RENTAL_SHIFT_WINDOWS[shift_number]
    start_date = target_date - timedelta(days=1) if shift_number == 1 else target_date
    start = datetime.combine(start_date, start_time)
    end = datetime.combine(target_date, end_time)
    current_tz = timezone.get_current_timezone()
    return timezone.make_aware(start, current_tz), timezone.make_aware(end, current_tz)


def _duration_hours(value: Any) -> int:
    """Normalize cashier duration input to an allowed 8-hour rental block."""
    try:
        hours = int(value or 8)
    except (TypeError, ValueError):
        hours = 8
    if hours not in RENTAL_DURATION_HOURS:
        raise ValueError("duration_hours must be 8, 16, or 24.")
    return hours


def _entry_time(value: Any) -> Any:
    """Normalize optional cashier entry timestamp into an aware datetime."""
    if not value:
        return timezone.now()
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValueError("entry_time must be a valid datetime.")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


class RoomViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for CRUD operations on rooms."""

    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_room",
        "retrieve": "rooms.view_room",
        "create": "rooms.add_room",
        "update": "rooms.change_room",
        "partial_update": "rooms.change_room",
        "destroy": "rooms.delete_room",
        "amenities": "rooms.view_roomamenity",
        "add_amenity": "rooms.add_roomamenity",
        "dashboard": "rooms.change_room",
        "override": "rooms.operate_room",
        "vehicle": "rooms.operate_room",
        "confirm_departure": "rooms.operate_room",
    }

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter rooms by optional query parameters."""
        qs = Room.objects.select_related("current_vehicle")
        request = self.request
        if request and hasattr(request, "query_params"):
            room_number = request.query_params.get("room_number")
            if room_number:
                qs = qs.filter(room_number=room_number)
            active = request.query_params.get("active")
            if active is not None:
                qs = qs.filter(active=active.lower() == "true")  # type: ignore[union-attr]
        return qs

    @action(detail=True, methods=["get"])
    def amenities(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """List all amenities assigned to a specific room."""
        try:
            room_amenities = RoomAmenity.objects.filter(room_id=pk)
        except Room.DoesNotExist:
            return Response(
                {"detail": "Room not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = RoomAmenitySerializer(room_amenities, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_amenity(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """Add an amenity to a specific room."""
        try:
            room = Room.objects.get(pk=pk)
        except Room.DoesNotExist:
            return Response(
                {"detail": "Room not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        amenity_id = request.data.get("amenity_id")
        if not amenity_id:
            return Response(
                {"detail": "amenity_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            RoomAmenity.objects.get_or_create(
                room_id=pk,
                amenity_id=amenity_id,
            )

        return Response(status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def dashboard(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Get a summary of all rooms for the dashboard view."""
        total = Room.objects.count()
        active_rooms = Room.objects.filter(active=True).count()
        available_rooms = (
            Room.objects.filter(active=True)
            .exclude(
                room_id__in=[
                    r.room_id for r in RentalSession.objects.filter(status="checked_in")
                ]
            )
            .count()
        )

        return Response(
            {
                "total_rooms": total,
                "active_rooms": active_rooms,
                "available_rooms": available_rooms,
            }
        )

    @action(detail=True, methods=["post"])
    def override(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """Apply a cashier manual room-state override."""
        room = self.get_object()
        override_action = request.data.get("action")
        user = request.data.get("user") or request.user.get_username()

        if not override_action:
            return Response(
                {"detail": "action is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.occupancy.services import occupancy_service

        try:
            result = occupancy_service.manual_override(
                room_id=room.room_id,
                action=override_action,
                user=user,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        room.refresh_from_db()
        return Response(
            {
                **result,
                "room": self.get_serializer(room).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def vehicle(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """Attach or clear the vehicle currently associated with a room."""
        room = self.get_object()
        clear_requested = bool(request.data.get("clear"))
        vehicle_id = request.data.get("vehicle_id")
        user = request.user.get_username() or "cashier"

        if clear_requested or vehicle_id in (None, ""):
            previous_vehicle = room.current_vehicle
            room.current_vehicle = None
            room.save(update_fields=["current_vehicle"])
            if previous_vehicle is not None:
                OccupancyEvent.objects.create(
                    room_id=room.room_id,
                    event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
                    confidence=1.0,
                    source=OccupancyEvent.Source.MANUAL_INPUT,
                    notes=f"{user} cleared vehicle {previous_vehicle} from room.",
                )
            return Response(self.get_serializer(room).data, status=status.HTTP_200_OK)

        try:
            vehicle = Vehicle.objects.get(pk=vehicle_id)
        except (TypeError, ValueError, Vehicle.DoesNotExist):
            return Response(
                {"detail": "Vehicle not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        previous_vehicle_id = room.current_vehicle_id
        room.current_vehicle = vehicle
        room.save(update_fields=["current_vehicle"])
        active_session = (
            RentalSession.objects.filter(
                room_id=room.room_id,
                status=RentalSession.Status.CHECKED_IN,
                end_time__isnull=True,
            )
            .order_by("-start_time")
            .first()
        )
        if active_session is not None and active_session.vehicle_id != vehicle.pk:
            active_session.vehicle = vehicle
            active_session.save(update_fields=["vehicle"])
        if previous_vehicle_id != vehicle.pk:
            OccupancyEvent.objects.create(
                room_id=room.room_id,
                event_type=OccupancyEvent.EventType.VEHICLE_ATTACHED,
                confidence=1.0,
                source=OccupancyEvent.Source.MANUAL_INPUT,
                notes=f"{user} attached vehicle {vehicle} to room.",
            )
        return Response(self.get_serializer(room).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="confirm-departure")
    def confirm_departure(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """Confirm that a vehicle left a vacant room and mark it dirty."""
        room = self.get_object()
        if room.current_state not in {"vacant", "manual_vacant"}:
            return Response(
                {"detail": "Only a vacant room can have its departure confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if room.current_vehicle is None:
            return Response(
                {"detail": "This room has no attached vehicle to confirm."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user.get_username() or "cashier"
        previous_vehicle = room.current_vehicle
        with transaction.atomic():
            room.current_vehicle = None
            room.current_state = "dirty"
            room.save(update_fields=["current_vehicle", "current_state"])
            OccupancyEvent.objects.create(
                room_id=room.room_id,
                event_type=OccupancyEvent.EventType.VEHICLE_CLEARED,
                confidence=1.0,
                source=OccupancyEvent.Source.MANUAL_INPUT,
                notes=(
                    f"{user} confirmed vehicle {previous_vehicle} will not return; "
                    "room marked dirty."
                ),
            )

        return Response(self.get_serializer(room).data, status=status.HTTP_200_OK)


class PricingTierViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for CRUD operations on pricing tiers."""

    queryset = PricingTier.objects.all()
    serializer_class = PricingTierSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_pricingtier",
        "retrieve": "rooms.view_pricingtier",
        "create": "rooms.add_pricingtier",
        "update": "rooms.change_pricingtier",
        "partial_update": "rooms.change_pricingtier",
        "destroy": "rooms.delete_pricingtier",
    }


class AmenityViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for CRUD operations on amenities."""

    queryset = Amenity.objects.all()
    serializer_class = AmenitySerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_amenity",
        "retrieve": "rooms.view_amenity",
        "create": "rooms.add_amenity",
        "update": "rooms.change_amenity",
        "partial_update": "rooms.change_amenity",
        "destroy": "rooms.delete_amenity",
    }


class RoomAmenityViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for managing room-amenity associations."""

    queryset = RoomAmenity.objects.all()
    serializer_class = RoomAmenitySerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_roomamenity",
        "retrieve": "rooms.view_roomamenity",
        "create": "rooms.add_roomamenity",
        "update": "rooms.change_roomamenity",
        "partial_update": "rooms.change_roomamenity",
        "destroy": "rooms.delete_roomamenity",
    }


class MaintenanceLogViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for CRUD operations on maintenance logs."""

    queryset = MaintenanceLog.objects.none()  # type: ignore[attr-defined]
    serializer_class = MaintenanceLogSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_maintenancelog",
        "retrieve": "rooms.view_maintenancelog",
        "create": "rooms.add_maintenancelog",
        "update": "rooms.change_maintenancelog",
        "partial_update": "rooms.change_maintenancelog",
        "destroy": "rooms.delete_maintenancelog",
        "upcoming": "rooms.view_maintenancelog",
    }

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter maintenance logs by optional query parameters."""
        qs = MaintenanceLog.objects.all()
        room_id = self.request.query_params.get("room_id") if self.request else None  # type: ignore[attr-defined]
        if room_id:
            qs = qs.filter(room_id=room_id)
        status_filter = (
            self.request.query_params.get("status") if self.request else None
        )  # type: ignore[attr-defined]
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=False, methods=["get"])
    def upcoming(self, request) -> Response:  # type: ignore[no-untyped-def]
        """List maintenance items due today or past-due."""
        today = timezone.now().date()
        upcoming_maintenance = MaintenanceLog.objects.filter(
            next_due__lte=today,
            status__in=["pending", "scheduled"],
        ).order_by("next_due")
        serializer = MaintenanceLogSerializer(upcoming_maintenance, many=True)
        return Response(serializer.data)


class RentalSessionViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for manual rental sessions used by cashier and manager screens."""

    queryset = RentalSession.objects.all()
    serializer_class = RentalSessionSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_rentalsession",
        "retrieve": "rooms.view_rentalsession",
        "create": "rooms.add_rentalsession",
        "update": "rooms.change_rentalsession",
        "partial_update": "rooms.change_rentalsession",
        "destroy": "rooms.delete_rentalsession",
        "set_duration": "rooms.extend_rentalsession",
    }

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter rental sessions for shift views and room detail screens."""
        qs = RentalSession.objects.select_related("vehicle").all()
        request = self.request
        if request and hasattr(request, "query_params"):
            room_id = request.query_params.get("room_id")
            if room_id:
                qs = qs.filter(room_id=room_id)
            status_filter = request.query_params.get("status")
            if status_filter:
                qs = qs.filter(status=status_filter)
            date_param = request.query_params.get("date")
            shift_param = request.query_params.get("shift")
            start_date_param = request.query_params.get("start_date")
            end_date_param = request.query_params.get("end_date")
            if start_date_param or end_date_param:
                try:
                    first_day = date.fromisoformat(start_date_param or "")
                    last_day = date.fromisoformat(end_date_param or "")
                    if first_day > last_day:
                        raise ValueError
                    start, _ = _rental_shift_bounds(first_day, 1)
                    _, end = _rental_shift_bounds(last_day, 3)
                except (TypeError, ValueError):
                    return qs.none()
                qs = qs.filter(start_time__gte=start, start_time__lt=end)
            elif date_param and shift_param:
                try:
                    target_date = date.fromisoformat(date_param)
                    if shift_param == "all":
                        start, _ = _rental_shift_bounds(target_date, 1)
                        _, end = _rental_shift_bounds(target_date, 3)
                    else:
                        shift_number = int(shift_param)
                        start, end = _rental_shift_bounds(target_date, shift_number)
                except (TypeError, ValueError):
                    return qs.none()
                qs = qs.filter(start_time__gte=start, start_time__lt=end)
            elif date_param:
                qs = qs.filter(start_time__date=date_param)

            ordering = request.query_params.get("ordering")
            allowed_ordering = {
                "session_id",
                "-session_id",
                "room_id",
                "-room_id",
                "start_time",
                "-start_time",
                "end_time",
                "-end_time",
                "exit_time",
                "-exit_time",
                "status",
                "-status",
            }
            if ordering in allowed_ordering:
                if ordering == "start_time":
                    return qs.order_by("start_time", "session_id")
                if ordering == "-start_time":
                    return qs.order_by("-start_time", "-session_id")
                return qs.order_by(ordering)
        return qs.order_by("start_time", "session_id")

    def create(self, request, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
        """Create a manual cashier rental with a default 8-hour planned duration."""
        data = request.data.copy()
        try:
            hours = _duration_hours(data.get("duration_hours"))
            start_time = _entry_time(data.get("entry_time") or data.get("start_time"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        room_number = data.get("room_number")
        if room_number and not data.get("room_id"):
            room = Room.objects.filter(room_number=str(room_number)).first()
            if room is None:
                room = Room.objects.filter(room_id=str(room_number)).first()
            if room is None:
                return Response(
                    {"detail": f"Room not found: {room_number}"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            data["room_id"] = room.room_id

        data["start_time"] = start_time.isoformat()
        data.setdefault("end_time", (start_time + timedelta(hours=hours)).isoformat())
        data.setdefault("status", RentalSession.Status.CHECKED_IN)
        data.setdefault("source", "cashier")
        data.setdefault("reviewed_by", request.user.get_username() or "cashier")

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        self._sync_room_for_session(session)
        headers = self.get_success_headers(serializer.data)
        return Response(
            self.get_serializer(session).data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    @action(detail=True, methods=["post"], url_path="set-duration")
    def set_duration(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """Set a stay to 8, 16, or 24 hours from the original rental time."""
        session = self.get_object()
        try:
            hours = _duration_hours(request.data.get("duration_hours"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        session.end_time = session.start_time + timedelta(hours=hours)
        session.save(update_fields=["end_time"])
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    def _sync_room_for_session(self, session: RentalSession) -> None:
        """Mark the room as manually occupied and carry vehicle context forward."""
        room = Room.objects.filter(room_id=session.room_id).first()
        if room is None:
            return
        room.current_state = "occupied"
        update_fields = ["current_state"]
        if session.vehicle_id is not None:
            room.current_vehicle = session.vehicle
            update_fields.append("current_vehicle")
        room.save(update_fields=update_fields)


# --- Frontend template views ---


def _require_manager_or_admin(user: Any) -> None:
    """Raise unless the signed-in user can use manager screens."""
    if not user.has_perm("rooms.change_room"):
        raise PermissionDenied("Manager access required.")


def dashboard_view(request):  # type: ignore[no-untyped-def]
    """Send each signed-in motel role to its primary workspace."""
    is_cashier = request.user.is_authenticated and not request.user.has_perm(
        "rooms.change_room"
    )
    if is_cashier:
        return redirect("revenue_cashier")
    return redirect("rooms_manager")


@login_required
@ensure_csrf_cookie
def manager_view(request) -> render:  # type: ignore[return]
    """Serve the manager dashboard template."""
    _require_manager_or_admin(request.user)
    today = date.today()
    context: dict[str, Any] = {
        "debug": False,
        "today": today,
        "default_room": "101",
        "new_room_default": "102",
        "default_username": "manager",
    }
    if request.user.is_authenticated:
        context["user"] = request.user
    return render(request, "rooms/manager.html", context)


@login_required
@ensure_csrf_cookie
def room_config_view(request) -> render:  # type: ignore[return]
    """Serve the manager room configuration template."""
    _require_manager_or_admin(request.user)
    context: dict[str, Any] = {
        "debug": False,
        "default_username": "manager",
    }
    if request.user.is_authenticated:
        context["user"] = request.user
    return render(request, "rooms/room_config.html", context)


# === Dynamic Pricing Rule ViewSet ===

class DynamicPricingRuleViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for CRUD operations on dynamic pricing rules."""

    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "rooms.view_dynamicpricingrule",
        "retrieve": "rooms.view_dynamicpricingrule",
        "create": "rooms.add_dynamicpricingrule",
        "update": "rooms.change_dynamicpricingrule",
        "partial_update": "rooms.change_dynamicpricingrule",
        "destroy": "rooms.delete_dynamicpricingrule",
        "active_rules": "rooms.view_dynamicpricingrule",
        "tier_summary": "rooms.view_dynamicpricingrule",
    }

    def get_serializer_class(self) -> Any:  # type: ignore[override]
        from apps.rooms.serializers import DynamicPricingRuleSerializer
        return DynamicPricingRuleSerializer

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter rules by optional query parameters."""
        from apps.rooms.models import DynamicPricingRule
        qs = DynamicPricingRule.objects.all().order_by("-priority", "start_date")
        request = self.request

        tier_code = (
            request.query_params.get("tier_code") if request else None  # type: ignore[attr-defined]
        )
        if tier_code:
            qs = qs.filter(tier_code=tier_code)

        rule_type = (
            request.query_params.get("rule_type") if request else None  # type: ignore[attr-defined]
        )
        if rule_type:
            qs = qs.filter(rule_type=rule_type)

        is_active = (
            request.query_params.get("is_active") if request else None  # type: ignore[attr-defined]
        )
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")  # type: ignore[union-attr]

        return qs

    @action(detail=False, methods=["get"])
    def active_rules(self, request) -> Response:  # type: ignore[no-untyped-def]
        """List all currently active rules for today's date."""
        from django.utils import timezone

        from apps.rooms.models import DynamicPricingRule

        today = timezone.now().date()
        active = []
        for rule in DynamicPricingRule.objects.filter(is_active=True):
            if rule.is_date_in_window(today) or (
                rule.rule_type == "day_of_week" and rule.matches_day(today.weekday())
            ):
                active.append(rule)
        serializer = DynamicPricingRuleSerializer(active, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def tier_summary(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Group active rules by tier for dashboard display."""
        from django.utils import timezone

        from apps.rooms.models import DynamicPricingRule

        today = timezone.now().date()
        tiers: dict[str, list] = {}
        for rule in DynamicPricingRule.objects.filter(is_active=True):
            is_rule_active = rule.is_date_in_window(today) or (
                rule.rule_type == "day_of_week" and rule.matches_day(today.weekday())
            )
            if not is_rule_active:
                continue
            tier = tiers.setdefault(rule.tier_code, [])
            tier.append({
                "id": rule.id,
                "name": rule.name or rule.rule_type,
                "rule_type": rule.rule_type,
                "price_override": float(rule.price_override),
                "priority": rule.priority,
            })
        return Response(tiers)
