"""Revenue service layer — occupancy sessions, shift ledger generation, Cuadre matching.

Ported 1:1 from app/revenue.py (FastAPI). Only the ORM access changed; all business
logic, tier definitions, Spanish month/day names, and Cuadre text formatting are
identical to the original.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any

from apps.occupancy.models import OccupancyEvent
from apps.revenue.models import OccupancySession, ShiftLedger
from apps.rooms.models import Room
from apps.rooms.pricing import DynamicPricingEngine

# ---------------------------------------------------------------------------
# Canonical pricing tiers (exact copy of app/revenue.py TIER_MAP)
# ---------------------------------------------------------------------------

TIER_MAP: dict[str, dict[str, Any]] = {
    "1 BGO": {
        "price": 40.0,
        "count_col": "tier_1_bgo_count",
        "rev_col": "tier_1_bgo_revenue",
    },
    "2 Y0 Dndein": {
        "price": 45.0,
        "count_col": "tier_2_y0_dndein_count",
        "rev_col": "tier_2_y0_dndein_revenue",
    },
    "3 BOO": {
        "price": 50.0,
        "count_col": "tier_3_boo_count",
        "rev_col": "tier_3_boo_revenue",
    },
    "4 BUYS": {
        "price": 70.0,
        "count_col": "tier_4_buys_count",
        "rev_col": "tier_4_buys_revenue",
    },
    "9.S0": {
        "price": 100.0,
        "count_col": "tier_5_s0_luxury_count",
        "rev_col": "tier_5_s0_luxury_revenue",
    },
}

TIER_ORDER: list[str] = ["1 BGO", "2 Y0 Dndein", "3 BOO", "4 BUYS", "9.S0"]


# ---------------------------------------------------------------------------
# Spanish month/day names (exact copy from original)
# ---------------------------------------------------------------------------

SP_MONTHS: dict[str, str] = {
    "January": "ENERO",
    "February": "FEBRERO",
    "March": "MARZO",
    "April": "ABRIL",
    "May": "MAYO",
    "June": "JUNIO",
    "July": "JULIO",
    "August": "AGOSTO",
    "September": "SEPTIEMBRE",
    "October": "OCTUBRE",
    "November": "NOVIEMBRE",
    "December": "DICIEMBRE",
}

SP_DAYS: dict[int, str] = {
    0: "LUNES",
    1: "MARTES",
    2: "MIERCOLES",
    3: "JUEVES",
    4: "VIERNES",
    5: "SABADO",
    6: "DOMINGO",
}


# ---------------------------------------------------------------------------
# Helper functions (exact copy from original)
# ---------------------------------------------------------------------------


def tier_key_to_sql_column(tier_code: str) -> str | None:
    """Convert a pricing tier code to the corresponding count column name."""
    return TIER_MAP.get(tier_code, {}).get("count_col", None)


def tier_price(tier_code: str) -> float:
    """Get price for a tier code."""
    return TIER_MAP.get(tier_code, {}).get("price", 0.0)


def format_cuadre_date(d: datetime) -> str:
    """Format date like paper reports: MARTES 02-ENERO-2026."""
    day_name = SP_DAYS[d.weekday()]
    month_name = SP_MONTHS[d.strftime("%B")]
    return f"{day_name} {d.day:02d}-{month_name}-{d.year}"


def format_shift_date(d: datetime) -> str:
    """Format date like: 02-ENERO-2026."""
    month_name = SP_MONTHS[d.strftime("%B")]
    return f"{d.day:02d}-{month_name}-{d.year}"


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Revenue engine (port of RevenueEngine from app/revenue.py)
# ---------------------------------------------------------------------------


class RevenueEngine:
    """Computes occupancy sessions, shift ledgers from room states.

    Ported from app/revenue.py. Replaced SQLAlchemy raw SQL with Django ORM
    where possible; the aggregation logic is identical.
    """

    # ---- session detection ------------------------------------------------

    def detect_sessions_for_day(self, day: date) -> list[dict[str, Any]]:
        """Detect open occupancy sessions for a given calendar day.

        A session starts on 'occupied' or 'car_present' and ends on the
        corresponding 'vacant' or 'car_absent'.  If no close event exists
        the session is still active (ongoing).

        Returns list of dicts: {room_id, start_time, end_time, tier_code, price}
        """
        start_dt = datetime(day.year, day.month, day.day)
        end_dt = start_dt + timedelta(days=1)

        events = OccupancyEvent.objects.filter(
            timestamp__gte=start_dt, timestamp__lt=end_dt
        ).order_by("room_id", "timestamp")  # type: ignore[attr-defined]

        events_list = list(events)
        events_by_room: dict[str, list[Any]] = {}
        for ev in events_list:
            rid = ev.room_id
            events_by_room.setdefault(rid, []).append(ev)

        sessions: list[dict[str, Any]] = []
        for room_id in sorted(events_by_room.keys()):
            evts = events_by_room[room_id]
            pending_open: dict[str, Any] | None = None
            for ev in evts:
                etype = ev.event_type
                if etype in ("occupied", "car_present", "possible_arrival"):
                    pending_open = {
                        "start_time": ev.timestamp,
                        "event_type": etype,
                    }
                elif (
                    etype in ("vacant", "car_absent", "possible_departure")
                    and pending_open
                ):
                    sessions.append(
                        {
                            "room_id": room_id,
                            "start_time": pending_open["start_time"],
                            "end_time": ev.timestamp,
                            "source": etype,
                        }
                    )
                    pending_open = None
                elif (
                    etype in ("vacant", "car_absent", "possible_departure")
                    and not pending_open
                ):
                    pass  # standalone vacate — nothing to close

            if pending_open:
                sessions.append(
                    {
                        "room_id": room_id,
                        "start_time": pending_open["start_time"],
                        "end_time": None,
                        "source": pending_open["event_type"],
                    }
                )

        # Attach pricing from rooms table (exact copy of original logic)
        all_rooms = Room.objects.filter(active=True).values_list(
            "room_id", "pricing_tier_code"
        )  # type: ignore[attr-defined]
        room_tiers = {rid: code or "1 BGO" for rid, code in all_rooms}

        for s in sessions:
            tc = room_tiers.get(s["room_id"], "1 BGO")
            s["tier_code"] = tc
            s["price"] = tier_price(tc)

        return sessions

    def get_room_tier(self, room_id: str) -> str:
        """Get the pricing tier code for a room."""
        try:
            room = Room.objects.get(room_id=room_id)  # type: ignore[attr-defined]
            if room.pricing_tier_code:
                return room.pricing_tier_code
        except Room.DoesNotExist:  # type: ignore[attr-defined]
            pass
        return "1 BGO"

    # ---- shift ledger generation (exact copy of original logic) ----------

    def _resolve_tier_price(self, tier_code: str, target_date: date) -> float:
        """Resolve the effective price for a tier code on a given date using dynamic pricing.

        Falls back to TIER_MAP base price when no dynamic rule applies.
        """
        engine = DynamicPricingEngine()
        dynamic_price = engine.resolve_price(tier_code, target_date)
        return float(dynamic_price) if dynamic_price is not None else TIER_MAP.get(tier_code, {}).get("price", 0.0)

    def compute_shift_for_day(self, day: date, shift_number: int = 1) -> dict[str, Any]:
        """Compute a full shift ledger for a given day (matches paper Cuadre format)."""
        sessions = self.detect_sessions_for_day(day)

        tier_counts: dict[str, int] = dict.fromkeys(TIER_ORDER, 0)

        # Method 1: use detected sessions from today
        for s in sessions:
            tc = s.get("tier_code", "1 BGO")
            if tc in tier_counts:
                tier_counts[tc] += 1

        # Also count rooms that are currently occupied from latest events
        latest_events = {}
        all_events = OccupancyEvent.objects.filter(  # type: ignore[attr-defined]
            event_type__in=("occupied", "car_present", "manual_occupied")
        ).order_by("room_id", "-timestamp")
        for ev in all_events:
            if ev.room_id not in latest_events:
                latest_events[ev.room_id] = ev.event_type

        active_rooms: dict[str, str] = {}
        rooms_qs = Room.objects.filter(active=True).values_list(
            "room_id", "pricing_tier_code"
        )  # type: ignore[attr-defined]
        for rid, code in rooms_qs:
            if rid in latest_events:
                tc = code or "1 BGO"
                active_rooms[rid] = tc
                if tc in tier_counts:
                    tier_counts[tc] += 1

        # Calculate revenues per tier (exact copy)
        subtotal = 0.0
        tier_revenues: dict[str, float] = dict.fromkeys(TIER_ORDER, 0.0)
        for code in TIER_ORDER:
            count = tier_counts.get(code, 0)
            price = self._resolve_tier_price(code, day)
            revenue = count * price
            tier_revenues[code] = revenue
            subtotal += revenue

        barra = 0.0
        ath_subtotal = subtotal + barra

        return {
            "date": day.isoformat(),
            "shift_number": shift_number,
            "tier_counts": tier_counts,
            "tier_revenues": tier_revenues,
            "subtotal": round(subtotal, 2),
            "barra_amount": round(barra, 2),
            "ath_subtotal": round(ath_subtotal, 2),
            "sessions_count": len(sessions),
            "active_rooms_count": len(active_rooms),
        }

    def save_shift_ledger(
        self, day: date, shift_number: int, ledger: dict[str, Any]
    ) -> int:
        """Save computed shift ledger to the database, updating existing rows."""
        tier_data = {
            "tier_1_bgo_count": ledger["tier_counts"].get("1 BGO", 0),
            "tier_2_y0_dndein_count": ledger["tier_counts"].get("2 Y0 Dndein", 0),
            "tier_3_boo_count": ledger["tier_counts"].get("3 BOO", 0),
            "tier_4_buys_count": ledger["tier_counts"].get("4 BUYS", 0),
            "tier_5_s0_luxury_count": ledger["tier_counts"].get("9.S0", 0),
            "tier_1_bgo_revenue": Decimal(
                str(ledger["tier_revenues"].get("1 BGO", 0.0))
            ),
            "tier_2_y0_dndein_revenue": Decimal(
                str(ledger["tier_revenues"].get("2 Y0 Dndein", 0.0))
            ),
            "tier_3_boo_revenue": Decimal(
                str(ledger["tier_revenues"].get("3 BOO", 0.0))
            ),
            "tier_4_buys_revenue": Decimal(
                str(ledger["tier_revenues"].get("4 BUYS", 0.0))
            ),
            "tier_5_s0_luxury_revenue": Decimal(
                str(ledger["tier_revenues"].get("9.S0", 0.0))
            ),
        }

        ledger_entry, _created = ShiftLedger.objects.update_or_create(
            date=day,
            shift_number=shift_number,
            defaults={
                **tier_data,
                "subtotal": Decimal(str(ledger["subtotal"])),
                "barra_amount": Decimal(str(ledger["barra_amount"])),
                "ath_subtotal": Decimal(str(ledger["ath_subtotal"])),
            },
        )

        return ledger_entry.pk  # type: ignore[no-any-return]

    def get_shift_ledgers(  # type: ignore[no-untyped-def]
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        shift_number: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query saved shift ledgers with filters."""
        qs = ShiftLedger.objects.all()  # type: ignore[attr-defined]

        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        if shift_number is not None:
            qs = qs.filter(shift_number=shift_number)

        results = []
        for entry in qs.order_by("-date", "-shift_number"):  # type: ignore[no-untyped-call]
            results.append(
                {
                    "id": entry.pk,
                    "date": entry.date.isoformat()
                    if hasattr(entry.date, "isoformat")
                    else str(entry.date),
                    "shift_number": entry.shift_number,
                    "tier_1_bgo_count": entry.tier_1_bgo_count,
                    "tier_2_y0_dndein_count": entry.tier_2_y0_dndein_count,
                    "tier_3_boo_count": entry.tier_3_boo_count,
                    "tier_4_buys_count": entry.tier_4_buys_count,
                    "tier_5_s0_luxury_count": entry.tier_5_s0_luxury_count,
                    "tier_1_bgo_revenue": float(entry.tier_1_bgo_revenue),
                    "tier_2_y0_dndein_revenue": float(entry.tier_2_y0_dndein_revenue),
                    "tier_3_boo_revenue": float(entry.tier_3_boo_revenue),
                    "tier_4_buys_revenue": float(entry.tier_4_buys_revenue),
                    "tier_5_s0_luxury_revenue": float(entry.tier_5_s0_luxury_revenue),
                    "subtotal": float(entry.subtotal),
                    "barra_amount": float(entry.barra_amount),
                    "ath_subtotal": float(entry.ath_subtotal),
                    "logged_by": entry.logged_by,
                    "verified_by": entry.verified_by,
                    "notes": entry.notes,
                }
            )
        return results

    def get_revenue_summary(  # type: ignore[no-untyped-def]
        self,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """Get revenue summary grouped by date for a range."""
        entries = list(
            ShiftLedger.objects.filter(  # type: ignore[attr-defined]
                date__gte=start_date, date__lte=end_date
            ).order_by("date", "shift_number")
        )

        days: dict[str, dict[str, Any]] = {}
        for entry in entries:
            d_str = (
                entry.date.isoformat()
                if hasattr(entry.date, "isoformat")
                else str(entry.date)
            )  # type: ignore[attr-defined]
            if d_str not in days:
                days[d_str] = {
                    "date": d_str,
                    "shifts": [],
                    "daily_subtotal": 0.0,
                    "daily_barra": 0.0,
                    "daily_total": 0.0,
                }
            days[d_str]["shifts"].append(
                {
                    "shift_number": entry.shift_number,
                    "subtotal": float(entry.subtotal),
                    "barra_amount": float(entry.barra_amount),
                    "ath_subtotal": float(entry.ath_subtotal),
                }
            )
            days[d_str]["daily_subtotal"] += float(entry.subtotal)
            days[d_str]["daily_barra"] += float(entry.barra_amount)
            days[d_str]["daily_total"] += float(entry.ath_subtotal)

        return {
            "start": start_date,
            "end": end_date,
            "days": list(days.values()),
        }

    # ---- Cuadre PDF text (exact paper format match) ---------------------

    def generate_cuadre_text(self, day: date, shift_number: int = 1) -> str:
        """Generate exact paper Cuadre format text for a given shift."""
        ledger = self.compute_shift_for_day(day, shift_number)

        dt = datetime.strptime(ledger["date"], "%Y-%m-%d")
        lines = []
        date_str = format_cuadre_date(dt)
        shift_label = "TURNO 1" if shift_number == 1 else "TURNO 2"

        lines.append(f"{date_str} {shift_label} Cuadre ATH Batch Total")
        lines.append("")
        lines.append("Desglose de Depositos:")

        for code in TIER_ORDER:
            count = ledger["tier_counts"].get(code, 0)
            price = TIER_MAP[code]["price"]
            rev = ledger["tier_revenues"].get(code, 0.0)
            if count > 0:
                lines.append(f"{code}   {count} cuartos × ${price:.2f} = ${rev:.2f}")

        lines.append("")
        lines.append(f"Subtotal = ${ledger['subtotal']:.2f}")
        lines.append(f"Barra = ${ledger['barra_amount']:.2f}")
        lines.append(f"ATH SUB-TOTAL = ${ledger['ath_subtotal']:.2f}")
        lines.append("")

        total_rooms = Room.objects.filter(active=True).count()  # type: ignore[attr-defined]
        occupied_count = len(
            [s for s in self.detect_sessions_for_day(day) if s.get("end_time") is None]
        )

        lines.append(
            f"Hoy ({shift_label}) Ventas: ${ledger['ath_subtotal']:.2f} | {ledger['sessions_count']}"
        )
        lines.append(f"T.Recibida #   {total_rooms}")
        lines.append(f"T.Recibida T  {total_rooms}")
        lines.append(f"T.Usada #      {occupied_count}")
        lines.append(f"T.Entregada #  {total_rooms - occupied_count}")
        lines.append("")
        lines.append("Firma: [Manager Name]")
        lines.append(f"FECHA: {format_shift_date(dt)}")

        return "\n".join(lines)

    def get_active_sessions(self, day: date | None = None) -> list[dict[str, Any]]:
        """Get currently active (ongoing) sessions."""
        if day is None:
            day = date.today()
        sessions = self.detect_sessions_for_day(day)
        return [s for s in sessions if s.get("end_time") is None]

    def create_occupancy_session(
        self,
        room_id: str,
        event_type: str,
        source: str = "sensor_auto",
        check_in_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create an occupancy session record from a state change event."""
        tier_code = self.get_room_tier(room_id)
        from django.utils import timezone

        now = check_in_at or timezone.now()
        price = (
            float(self._resolve_tier_price(tier_code, now.date()))
            if hasattr(self, "_resolve_tier_price")
            else tier_price(tier_code)
        )
        session = OccupancySession.objects.create(  # type: ignore[attr-defined]
            room_id=room_id,
            check_in=now,
            room_type_code=tier_code,
            price_per_night=Decimal(str(price)),
            estimated_revenue=Decimal(str(price)),
            source=source,
            status=OccupancySession.Status.ACTIVE,  # type: ignore[attr-defined]
        )

        return {
            "session_id": session.pk,
            "room_id": room_id,
            "tier_code": tier_code,
            "price": price,
            "estimated_revenue": price,
            "source": source,
        }

    def close_occupancy_session(
        self,
        session_id: int,
        check_out_at: datetime | None = None,
        bill_in_eight_hour_blocks: bool = False,
    ) -> dict[str, Any]:
        """Mark an occupancy session as checked_out."""
        try:
            session = OccupancySession.objects.get(pk=session_id)  # type: ignore[attr-defined]
        except OccupancySession.DoesNotExist:  # type: ignore[attr-defined]
            return {"error": "Session not found"}

        from django.utils import timezone

        now = check_out_at or timezone.now()
        session.check_out = now  # type: ignore[union-attr]
        session.status = OccupancySession.Status.CHECKED_OUT  # type: ignore[attr-defined]
        session.save(update_fields=["check_out", "status"])

        duration_hours = max(1, (now - session.check_in).total_seconds() / 3600)
        if bill_in_eight_hour_blocks:
            billed_blocks = (
                3 if duration_hours > 16 else (2 if duration_hours > 8 else 1)
            )
            actual_revenue = round(
                float(session.price_per_night or Decimal("40.0")) * billed_blocks,
                2,
            )
        else:
            billed_blocks = None
            price_per_hour = float(session.price_per_night or Decimal("40.0")) / 24.0
            actual_revenue = round(price_per_hour * max(duration_hours, 1), 2)

        session.actual_revenue = Decimal(str(actual_revenue))  # type: ignore[assignment]
        session.save(update_fields=["actual_revenue"])

        return {
            "session_id": session_id,
            "actual_revenue": actual_revenue,
            "duration_hours": round(duration_hours, 1),
            "billed_duration_hours": billed_blocks * 8 if billed_blocks else None,
        }

    def generate_cuadre_text_pdf(  # type: ignore[no-untyped-def]
        self,
        date_str: str,
        shift_number: int,
        tiers: dict[str, Any],
        total_rooms: int,
        total_revenue: float,
    ) -> BytesIO:
        """Generate Cuadre ATH PDF matching paper format.

        Delegates to ReportGenerator.generate_cuadre_pdf and returns a BytesIO buffer.
        """
        from apps.revenue.reports import report_generator

        return report_generator.generate_cuadre_pdf(
            date_str=date_str,
            shift_number=shift_number,
            tiers=tiers,
            total_rooms=total_rooms,
            total_revenue=total_revenue,
        )


# Singleton for import convenience.
revenue_engine = RevenueEngine()
