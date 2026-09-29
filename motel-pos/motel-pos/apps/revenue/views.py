"""Views for the revenue app - occupancy sessions, shift ledgers, and cashier portal."""

import logging
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import CanGenerateManagementReports, DjangoActionPermissions
from apps.revenue.models import OccupancySession, ShiftLedger
from apps.revenue.serializers import OccupancySessionSerializer, ShiftLedgerSerializer
from apps.rooms.models import Room

logger = logging.getLogger(__name__)

SHIFT_WINDOWS = {
    1: (time(23, 0), time(7, 0)),
    2: (time(7, 0), time(15, 0)),
    3: (time(15, 0), time(23, 0)),
}

TIER_LABELS = {
    "tier_1_bgo": "1 BGO",
    "tier_2_y0_dndein": "2 Y0 Dndein",
    "tier_3_boo": "3 BOO",
    "tier_4_buys": "4 BUYS",
    "tier_5_s0_luxury": "9.S0",
}


def _ledger_tier_data(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Translate ledger tier codes into the cashier-facing tier payload."""
    tier_counts = ledger.get("tier_counts", {})
    tier_revenues = ledger.get("tier_revenues", {})
    return {
        key: {
            "count": tier_counts.get(code, 0),
            "revenue": tier_revenues.get(code, 0.0),
        }
        for key, code in TIER_LABELS.items()
    }


def _shift_ledger_defaults(ledger: dict[str, Any]) -> dict[str, Any]:
    """Build persistence fields for a saved shift ledger."""
    tier_counts = ledger.get("tier_counts", {})
    tier_revenues = ledger.get("tier_revenues", {})
    return {
        "tier_1_bgo_count": int(tier_counts.get("1 BGO", 0)),
        "tier_2_y0_dndein_count": int(tier_counts.get("2 Y0 Dndein", 0)),
        "tier_3_boo_count": int(tier_counts.get("3 BOO", 0)),
        "tier_4_buys_count": int(tier_counts.get("4 BUYS", 0)),
        "tier_5_s0_luxury_count": int(tier_counts.get("9.S0", 0)),
        "tier_1_bgo_revenue": Decimal(str(tier_revenues.get("1 BGO", 0.0))),
        "tier_2_y0_dndein_revenue": Decimal(str(tier_revenues.get("2 Y0 Dndein", 0.0))),
        "tier_3_boo_revenue": Decimal(str(tier_revenues.get("3 BOO", 0.0))),
        "tier_4_buys_revenue": Decimal(str(tier_revenues.get("4 BUYS", 0.0))),
        "tier_5_s0_luxury_revenue": Decimal(str(tier_revenues.get("9.S0", 0.0))),
        "subtotal": Decimal(str(ledger.get("subtotal", 0))),
        "ath_subtotal": Decimal(str(ledger.get("ath_subtotal", 0))),
        "notes": f"Auto-generated from frontend cuadre on {timezone.now().isoformat()}",
    }


def _shift_bounds(target_date: date, shift_number: int) -> tuple[Any, Any]:
    """Return half-open aware bounds for a shift assigned to target_date."""
    if shift_number not in SHIFT_WINDOWS:
        raise ValueError("shift must be 1, 2, or 3")

    start_time, end_time = SHIFT_WINDOWS[shift_number]
    if shift_number == 1:
        start_date = target_date - timedelta(days=1)
        end_date = target_date
    else:
        start_date = target_date
        end_date = target_date

    start = datetime.combine(start_date, start_time)
    end = datetime.combine(end_date, end_time)
    current_tz = timezone.get_current_timezone()
    return timezone.make_aware(start, current_tz), timezone.make_aware(end, current_tz)


def _session_sale_amount(session: OccupancySession, room_prices: dict[str, int]) -> Decimal:
    """Resolve the best available sale amount for old and new occupancy rows."""
    for attr in ("actual_revenue", "estimated_revenue", "price_per_night"):
        value = getattr(session, attr, None)
        if value is not None:
            return Decimal(str(value))
    return Decimal(str(room_prices.get(session.room_id, 0)))


def _room_type_label(session: OccupancySession, room_prices: dict[str, int]) -> str:
    """Group daily sales by explicit room type, then price bucket as fallback."""
    if session.room_type_code:
        return session.room_type_code
    price = _session_sale_amount(session, room_prices)
    return f"${price:.2f}"


def _serialize_sale(session: OccupancySession, room_prices: dict[str, int]) -> dict[str, Any]:
    sale_amount = _session_sale_amount(session, room_prices)
    return {
        "id": session.pk,
        "room_id": session.room_id,
        "entry_time": session.check_in.isoformat() if session.check_in else None,
        "exit_time": session.check_out.isoformat() if session.check_out else None,
        "room_type": _room_type_label(session, room_prices),
        "payment_method": "Unspecified",
        "sale_amount": float(sale_amount),
    }


def _sales_between(start: Any, end: Any) -> Any:
    """Return checked-out sessions whose sale closed inside [start, end)."""
    return OccupancySession.objects.filter(
        status=OccupancySession.Status.CHECKED_OUT,
        check_out__gte=start,
        check_out__lt=end,
    ).order_by("check_out", "room_id")


def cashier_login_view(request) -> render:  # type: ignore[return]
    """Render the cashier login shell for legacy cashier entry points."""
    next_url = request.GET.get("next") or "/cashier/"
    if request.user.is_authenticated:
        return redirect(next_url)

    today = timezone.localdate()
    context: dict[str, Any] = {
        "debug": False,
        "today": today,
        "default_room": "101",
        "new_room_default": "102",
        "default_username": os.environ.get("MOTEL_CASHIER_USERNAME", ""),
        "login_only": True,
        "next_url": next_url,
        "user": request.user,
    }
    return render(request, "revenue/cashier.html", context)


def _require_cashier_or_above(user: Any) -> None:
    """Restrict the operational POS page to recognized motel roles."""
    if not user.has_perm("rooms.view_room"):
        raise PermissionDenied("Cashier access required.")


@login_required
@ensure_csrf_cookie
def cashier_view(request) -> render:  # type: ignore[return]
    """Serve the authenticated cashier portal template."""
    _require_cashier_or_above(request.user)
    today = timezone.localdate()
    context: dict[str, Any] = {
        "debug": False,
        "today": today,
        "default_room": "101",
        "new_room_default": "102",
        "default_username": os.environ.get("MOTEL_CASHIER_USERNAME", ""),
        "login_only": False,
        "next_url": "/cashier/",
        "user": request.user,
    }
    return render(request, "revenue/cashier.html", context)


class OccupancySessionViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """Manager/admin API for raw occupancy session records."""

    queryset = OccupancySession.objects.all()
    serializer_class = OccupancySessionSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "revenue.view_occupancysession",
        "retrieve": "revenue.view_occupancysession",
        "create": "revenue.add_occupancysession",
        "update": "revenue.change_occupancysession",
        "partial_update": "revenue.change_occupancysession",
        "destroy": "revenue.delete_occupancysession",
        "checkout": "revenue.change_occupancysession",
    }

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter sessions by optional query parameters."""
        qs = OccupancySession.objects.all().order_by("-check_in")
        room_id = self.request.query_params.get("room_id") if self.request else None  # type: ignore[attr-defined]
        if room_id:
            qs = qs.filter(room_id=room_id)
        status_filter = (
            self.request.query_params.get("status") if self.request else None
        )  # type: ignore[attr-defined]
        if status_filter:
            qs = qs.filter(status=status_filter)
        date_filter = self.request.query_params.get("date") if self.request else None  # type: ignore[attr-defined]
        if date_filter:
            from django.db.models import Q

            qs = qs.filter(
                Q(check_in__date=date_filter) | Q(check_out__date=date_filter),
            )
        return qs

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None) -> Response:  # type: ignore[no-untyped-def]
        """Check out a guest and finalize revenue calculation."""
        session = self.get_object()
        if session.status == "checked_out":
            return Response(
                {"detail": "Session already checked out"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            session.check_out = timezone.now()  # type: ignore[union-attr]
            session.status = "checked_out"  # type: ignore[attr-defined]
            session.save(update_fields=["check_out", "status", "updated_at"])

        logger.info("Guest checked out from room %s (session #%s)", session.room_id, pk)

        return Response(OccupancySessionSerializer(session).data)


class ShiftLedgerViewSet(viewsets.ModelViewSet):  # type: ignore[type-arg]
    """ViewSet for shift ledger entries."""

    queryset = ShiftLedger.objects.all()
    serializer_class = ShiftLedgerSerializer
    permission_classes = [DjangoActionPermissions]
    permission_map = {
        "list": "revenue.view_shiftledger",
        "retrieve": "revenue.view_shiftledger",
        "create": "revenue.add_shiftledger",
        "update": "revenue.change_shiftledger",
        "partial_update": "revenue.change_shiftledger",
        "destroy": "revenue.delete_shiftledger",
        "daily_summary": "revenue.generate_management_reports",
        "generate_report": "revenue.generate_management_reports",
        "cuadre": "revenue.view_shift_reports",
        "cuadre_pdf": "revenue.view_shift_reports",
        "summary": "revenue.view_shift_reports",
        "sales_summary": "revenue.view_shift_reports",
        "generate_shift": "revenue.generate_shift",
    }

    def get_queryset(self) -> Any:  # type: ignore[override]
        """Filter ledgers by optional query parameters."""
        qs = ShiftLedger.objects.order_by("-date", "-shift_number")
        date_filter = self.request.query_params.get("date") if self.request else None  # type: ignore[attr-defined]
        if date_filter:
            qs = qs.filter(date=date_filter)
        return qs

    @action(detail=False, methods=["get"])
    def daily_summary(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Get today's shift ledger summary."""
        from django.db.models import Sum
        from django.utils import timezone

        today = timezone.now().date()

        total_rooms = OccupancySession.objects.filter(
            check_in__date=today,
            status=OccupancySession.Status.ACTIVE,  # type: ignore[attr-defined]
        ).count()

        total_revenue = (
            OccupancySession.objects.aggregate(
                total=Sum("actual_revenue"),
            )["total"]
            or 0.0
        )

        return Response(
            {
                "date": today.isoformat(),
                "total_sessions": total_rooms,
                "total_revenue": float(total_revenue),
            }
        )

    @action(detail=False, methods=["get"], url_path="cuadre/(?P<date_str>[^/]+)")
    def cuadre_pdf(self, request, date_str=None) -> HttpResponse:  # type: ignore[no-untyped-def]
        """Generate Cuadre ATH PDF report for a given date.

        Args:
            date_str: Date in YYYY-MM-DD format.

        Returns:
            PDF file as HTTP response.
        """
        try:
            target_date = date.fromisoformat(date_str)  # type: ignore[union-attr]
        except (ValueError, AttributeError):
            return Response(
                {"detail": f"Invalid date format: {date_str}. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shift_param = request.query_params.get("shift", "1")  # type: ignore[union-attr]
        try:
            shift_number = int(shift_param)
        except (ValueError, TypeError):
            return Response(
                {"detail": f"Invalid shift number: {shift_param}. Use 1, 2, or 3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift_number not in (1, 2, 3):
            return Response(
                {"detail": f"Invalid shift number: {shift_number}. Use 1, 2, or 3."},
                status=status.HTTP_400_BAD_REQUEST,
            )


        from apps.revenue.services import revenue_engine

        ledger = revenue_engine.compute_shift_for_day(
            target_date,
            shift_number=shift_number,
        )

        tier_labels = {
            "tier_1_bgo": "1 BGO ($40)",
            "tier_2_y0_dndein": "2 Y0 Dndein ($45)",
            "tier_3_boo": "3 BOO ($50)",
            "tier_4_buys": "4 BUYS ($70)",
            "tier_5_s0_luxury": "9.S0 ($100)",
        }

        tiers: dict[str, Any] = {}
        for key in tier_labels:
            count_col = {
                "tier_1_bgo": "tier_1_bgo_count",
                "tier_2_y0_dndein": "tier_2_y0_dndein_count",
                "tier_3_boo": "tier_3_boo_count",
                "tier_4_buys": "tier_4_buys_count",
                "tier_5_s0_luxury": "tier_5_s0_luxury_count",
            }[key]
            rev_col = {
                "tier_1_bgo": "tier_1_bgo_revenue",
                "tier_2_y0_dndein": "tier_2_y0_dndein_revenue",
                "tier_3_boo": "tier_3_boo_revenue",
                "tier_4_buys": "tier_4_buys_revenue",
                "tier_5_s0_luxury": "tier_5_s0_luxury_revenue",
            }[key]
            tiers[key] = {
                "count": ledger["tier_counts"].get(key.replace("_revenue", ""), 0),
                "revenue": ledger["tier_revenues"].get(
                    key.replace("_revenue", ""), 0.0
                ),
            }

        pdf_buffer = revenue_engine.generate_cuadre_text_pdf(
            date_str=date_str,
            shift_number=ledger["shift_number"],
            tiers=_ledger_tier_data(ledger),
            total_rooms=int(ledger.get("active_rooms_count", 0)),
            total_revenue=float(ledger.get("ath_subtotal", 0.0)),
        )

        return HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")

    @action(detail=False, methods=["get"])
    def generate_report(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Generate and download various reports.

        Query params:
            type: 'daily_occupancy', 'daily_sales', or 'exception'
            date: YYYY-MM-DD (defaults to today)

        Returns:
            JSON with pdf and csv file paths, or PDF/CSV blob download.
        """
        report_type = request.query_params.get("type", "daily_occupancy")  # type: ignore[union-attr]
        date_param = request.query_params.get("date")  # type: ignore[union-attr]

        try:
            day = date.fromisoformat(date_param) if date_param else date.today()
        except (ValueError, AttributeError):
            return Response(
                {"detail": f"Invalid date format: {date_param}. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.revenue.reports import report_generator

        if report_type == "daily_occupancy":
            result = report_generator.generate_daily_occupancy(day)
        elif report_type == "daily_sales":
            result = report_generator.generate_daily_sales(day)
        elif report_type == "exception":
            result = report_generator.generate_exception_report(day)
        else:
            return Response(
                {
                    "detail": f"Unknown report type: {report_type}. Valid: daily_occupancy, daily_sales, exception."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If download requested, return file blob instead of JSON paths
        download = request.query_params.get("download", "false")  # type: ignore[union-attr]
        if download == "true":
            pdf_path = result["pdf"]
            with open(pdf_path, "rb") as f:
                response = HttpResponse(f.read(), content_type="application/pdf")
                response["Content-Disposition"] = (
                    f'attachment; filename="{day.isoformat()}_report.pdf"'
                )
                return response

        return Response(result)

    @action(detail=False, methods=["get"], url_path="cuadre")
    def cuadre(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Generate Cuadre data as JSON for the cashier frontend.

        Query params:
            date: YYYY-MM-DD (defaults to today).
            shift: int 1, 2, or 3.

        Returns:
            JSON dict with ledger summary, tier counts/revenues, and cuadre_text.
        """
        date_param = request.query_params.get("date")  # type: ignore[union-attr]
        try:
            target_date = (
                date.fromisoformat(date_param) if date_param else timezone.now().date()
            )  # type: ignore[union-attr]
        except (ValueError, AttributeError):
            return Response(
                {"detail": f"Invalid date format: {date_param}. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shift_num_str = request.query_params.get("shift", "1")  # type: ignore[union-attr]
        try:
            shift_number = int(shift_num_str)
        except (ValueError, TypeError):
            return Response(
                {"detail": f"Invalid shift number: {shift_num_str}. Use 1, 2, or 3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.revenue.services import revenue_engine

        ledger = revenue_engine.compute_shift_for_day(  # type: ignore[assignment]
            target_date,
            shift_number=shift_number,
        )

        tier_labels = {
            "tier_1_bgo": "1 BGO",
            "tier_2_y0_dndein": "2 Y0 Dndein",
            "tier_3_boo": "3 BOO",
            "tier_4_buys": "4 BUYS",
            "tier_5_s0_luxury": "9.S0",
        }

        tier_data: dict[str, Any] = {}
        for key in tier_labels:
            count_col = {
                "tier_1_bgo": "tier_1_bgo_count",
                "tier_2_y0_dndein": "tier_2_y0_dndein_count",
                "tier_3_boo": "tier_3_boo_count",
                "tier_4_buys": "tier_4_buys_count",
                "tier_5_s0_luxury": "tier_5_s0_luxury_count",
            }[key]
            rev_col = {
                "tier_1_bgo": "tier_1_bgo_revenue",
                "tier_2_y0_dndein": "tier_2_y0_dndein_revenue",
                "tier_3_boo": "tier_3_boo_revenue",
                "tier_4_buys": "tier_4_buys_revenue",
                "tier_5_s0_luxury": "tier_5_s0_luxury_revenue",
            }[key]
            tier_data[key] = {
                "count": ledger["tier_counts"].get(key.replace("_revenue", ""), 0),
                "revenue": ledger["tier_revenues"].get(
                    key.replace("_revenue", ""), 0.0
                ),
            }

        pdf_buffer = revenue_engine.generate_cuadre_text_pdf(
            date_str=target_date.isoformat(),
            shift_number=ledger["shift_number"],
            tiers=_ledger_tier_data(ledger),
            total_rooms=int(ledger.get("active_rooms_count", 0)),
            total_revenue=float(ledger.get("ath_subtotal", 0.0)),
        )

        return Response(
            {
                "ledger": ledger,
                "cuadre_text": pdf_buffer.getvalue().decode("utf-8", errors="replace"),
                "date": target_date.isoformat(),
                "shift_number": shift_number,
            }
        )

    @action(detail=False, methods=["get"])
    def summary(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Return revenue summary data for the cashier Revenue Summary tab."""
        start_param = request.query_params.get("start_date")  # type: ignore[union-attr]
        end_param = request.query_params.get("end_date")  # type: ignore[union-attr]
        today = timezone.now().date()

        try:
            start_date = date.fromisoformat(start_param) if start_param else today
            end_date = date.fromisoformat(end_param) if end_param else today
        except (ValueError, AttributeError):
            return Response(
                {
                    "detail": (
                        "Invalid date range. Use start_date and end_date in "
                        "YYYY-MM-DD format."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_date > end_date:
            return Response(
                {"detail": "start_date must be before or equal to end_date."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.revenue.services import revenue_engine

        return Response(
            revenue_engine.get_revenue_summary(
                start_date.isoformat(),
                end_date.isoformat(),
            )
        )

    @action(detail=False, methods=["get"], url_path="sales-summary")
    def sales_summary(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Return cashier sales views for fixed motel shifts, days, and weeks.

        Shift 1 belongs to the date it ends on:
        23:00 previous day through 06:59 target day.
        """
        view = request.query_params.get("view", "shift")  # type: ignore[union-attr]
        date_param = request.query_params.get("date")  # type: ignore[union-attr]
        try:
            target_date = (
                date.fromisoformat(date_param) if date_param else timezone.localdate()
            )
        except (ValueError, AttributeError):
            return Response(
                {"detail": f"Invalid date format: {date_param}. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        room_prices = dict(
            Room.objects.values_list("room_id", "price")  # type: ignore[name-defined]
        )

        if view == "shift":
            shift_param = request.query_params.get("shift", "1")  # type: ignore[union-attr]
            try:
                shift_number = int(shift_param)
                start, end = _shift_bounds(target_date, shift_number)
            except (ValueError, TypeError):
                return Response(
                    {"detail": f"Invalid shift: {shift_param}. Use 1, 2, or 3."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            sales = [
                _serialize_sale(session, room_prices)
                for session in _sales_between(start, end)
            ]
            return Response(
                {
                    "view": "shift",
                    "date": target_date.isoformat(),
                    "shift": shift_number,
                    "shift_label": f"Shift {shift_number}",
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "sales": sales,
                    "rooms_sold": len(sales),
                    "sales_total": round(sum(sale["sale_amount"] for sale in sales), 2),
                    "payment_total": round(sum(sale["sale_amount"] for sale in sales), 2),
                }
            )

        if view == "day":
            shift_rows = []
            day_total = Decimal("0.00")
            room_types: dict[str, dict[str, Any]] = defaultdict(
                lambda: {
                    "room_type": "",
                    "shift_1_count": 0,
                    "shift_1_total": Decimal("0.00"),
                    "shift_2_count": 0,
                    "shift_2_total": Decimal("0.00"),
                    "shift_3_count": 0,
                    "shift_3_total": Decimal("0.00"),
                    "count": 0,
                    "sales_total": Decimal("0.00"),
                }
            )
            for shift_number in (1, 2, 3):
                start, end = _shift_bounds(target_date, shift_number)
                sessions = list(_sales_between(start, end))
                shift_total = Decimal("0.00")
                for session in sessions:
                    amount = _session_sale_amount(session, room_prices)
                    room_type = _room_type_label(session, room_prices)
                    room_types[room_type]["room_type"] = room_type
                    room_types[room_type][f"shift_{shift_number}_count"] += 1
                    room_types[room_type][f"shift_{shift_number}_total"] += amount
                    room_types[room_type]["count"] += 1
                    room_types[room_type]["sales_total"] += amount
                    shift_total += amount
                day_total += shift_total
                shift_rows.append(
                    {
                        "shift": shift_number,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "rooms_sold": len(sessions),
                        "sales_total": float(shift_total),
                    }
                )

            room_type_rows = []
            for row in room_types.values():
                room_type_rows.append(
                    {
                        key: float(value) if isinstance(value, Decimal) else value
                        for key, value in row.items()
                    }
                )
            room_type_rows.sort(key=lambda row: str(row["room_type"]))
            return Response(
                {
                    "view": "day",
                    "date": target_date.isoformat(),
                    "shifts": shift_rows,
                    "room_types": room_type_rows,
                    "rooms_sold": sum(row["rooms_sold"] for row in shift_rows),
                    "sales_total": float(day_total),
                    "payment_total": float(day_total),
                }
            )

        if view == "week":
            week_start = target_date - timedelta(days=target_date.weekday())
            days = []
            week_total = Decimal("0.00")
            for offset in range(7):
                day = week_start + timedelta(days=offset)
                day_total = Decimal("0.00")
                rooms_sold = 0
                for shift_number in (1, 2, 3):
                    start, end = _shift_bounds(day, shift_number)
                    sessions = list(_sales_between(start, end))
                    rooms_sold += len(sessions)
                    day_total += sum(
                        (_session_sale_amount(session, room_prices) for session in sessions),
                        Decimal("0.00"),
                    )
                week_total += day_total
                days.append(
                    {
                        "date": day.isoformat(),
                        "rooms_sold": rooms_sold,
                        "sales_total": float(day_total),
                    }
                )
            return Response(
                {
                    "view": "week",
                    "date": target_date.isoformat(),
                    "week_start": week_start.isoformat(),
                    "week_end": (week_start + timedelta(days=6)).isoformat(),
                    "days": days,
                    "rooms_sold": sum(day["rooms_sold"] for day in days),
                    "sales_total": float(week_total),
                    "payment_total": float(week_total),
                }
            )

        return Response(
            {"detail": f"Unknown view: {view}. Use shift, day, or week."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["post"])
    def generate_shift(self, request) -> Response:  # type: ignore[no-untyped-def]
        """Save a shift ledger from frontend-generated cuadre data.

        Body (JSON):
            date: YYYY-MM-DD
            shift: int 1, 2, or 3

        Returns:
            dict with success status and saved ledger summary.
        """
        body = request.data
        date_param = body.get("date")
        shift_num = body.get("shift", 1)

        if not date_param:
            return Response(
                {"detail": "date is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = date.fromisoformat(date_param)  # type: ignore[assignment]
        except (ValueError, AttributeError):
            return Response(
                {"detail": f"Invalid date format: {date_param}. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            shift_number = int(shift_num)
        except (ValueError, TypeError):
            return Response(
                {"detail": f"Invalid shift: {shift_num}. Must be integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift_number not in (1, 2, 3):
            return Response(
                {'detail': f'Invalid shift: {shift_number}. Use 1, 2, or 3.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.revenue.services import revenue_engine

        ledger = revenue_engine.compute_shift_for_day(
            target_date,
            shift_number=shift_number,
        )

        with transaction.atomic():
            shift_ledger, created = ShiftLedger.objects.update_or_create(
                date=target_date,
                shift_number=shift_number,
                defaults=_shift_ledger_defaults(ledger),
            )

        logger.info(
            "Shift ledger saved: date=%s shift=%d",
            target_date,
            shift_number,
        )

        return Response(
            {
                "success": True,
                "date": target_date.isoformat(),
                "shift_number": shift_number,
                "subtotal": float(shift_ledger.subtotal),
                "ath_subtotal": float(shift_ledger.ath_subtotal),
                "saved_state": "created" if created else "updated",
                "shift_ledger_id": shift_ledger.pk,
            }
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, CanGenerateManagementReports])
def generate_report_view(
    request,
    report_type: str | None = None,
) -> Response:  # type: ignore[no-untyped-def]
    """Generate cashier reports and return JSON unless download is requested."""
    requested_type = report_type or request.data.get("type", "daily_occupancy")
    report_aliases = {"exceptions": "exception"}
    normalized_type = report_aliases.get(requested_type, requested_type)
    date_param = request.data.get("date")

    try:
        day = date.fromisoformat(date_param) if date_param else date.today()
    except (ValueError, AttributeError):
        return Response(
            {"detail": f"Invalid date format: {date_param}. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from apps.revenue.reports import report_generator

    if normalized_type == "daily_occupancy":
        result = report_generator.generate_daily_occupancy(day)
    elif normalized_type == "daily_sales":
        result = report_generator.generate_daily_sales(day)
    elif normalized_type == "exception":
        result = report_generator.generate_exception_report(day)
    else:
        return Response(
            {
                "detail": (
                    f"Unknown report type: {requested_type}. "
                    "Valid: daily_occupancy, daily_sales, exceptions."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    file_status = {
        name: {"path": path, "basename": os.path.basename(path)}
        for name, path in result.items()
        if path
    }
    existing_files = {
        name: meta["basename"]
        for name, meta in file_status.items()
        if os.path.isfile(meta["path"])
    }
    missing_files = [
        name for name in file_status if name not in existing_files
    ]

    download = request.query_params.get("download", "false") == "true"
    if download:
        pdf_path = result.get("pdf")
        if not pdf_path or "pdf" not in existing_files:
            return Response(
                {"detail": f"Report PDF not found for type={normalized_type}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        with open(pdf_path, "rb") as fh:
            response = HttpResponse(fh.read(), content_type="application/pdf")
            response["Content-Disposition"] = (
                f'inline; filename="{day.isoformat()}_{normalized_type}.pdf"'
            )
            return response

    if not existing_files:
        return Response(
            {"detail": f"Report files not found for type={normalized_type}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    payload = {
        "success": True,
        "report_type": normalized_type,
        "date": day.isoformat(),
        "files": existing_files,
    }
    if missing_files:
        payload["missing_files"] = missing_files
    return Response(payload)
