"""PDF and CSV report generation for motel occupancy system.

Ported 1:1 from app/reports/generator.py (FastAPI) with framework-agnostic logic
unchanged. Uses reportlab to generate PDFs matching the manual paper format exactly.
"""

import csv
import logging
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates PDF and CSV reports — ported from app/reports/generator.py."""

    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir or settings.REPORT_ROOT)
        self.output_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # PDF helpers (port of _write_report)
    # ------------------------------------------------------------------

    def _write_pdf_report(  # type: ignore[no-untyped-def]
        self,
        title: str,
        sections: list[dict[str, Any]],
    ) -> Path:
        """Build a PDF report with table data."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            logger.warning("reportlab not installed")
            return self.output_dir / f"{datetime.utcnow().isoformat()}_report.pdf"

        day_str = datetime.utcnow().strftime("%Y-%m-%d")
        day_dir = self.output_dir / day_str  # type: ignore[operator]
        day_dir.mkdir(parents=True, exist_ok=True)
        filepath = day_dir / f"{day_str}_report.pdf"

        doc = SimpleDocTemplate(str(filepath), pagesize=letter)
        elements: list[Any] = []
        styles = getSampleStyleSheet()

        elements.append(
            Paragraph(title, ParagraphStyle("Title", fontSize=18, leading=22))
        )  # type: ignore[no-untyped-call]
        elements.append(Spacer(1, 12))

        for section in sections:
            heading = section.get("heading", "")
            if heading:
                elements.append(Paragraph(heading, styles["Heading2"]))  # type: ignore[attr-defined]

            data_list = section.get("data") or []
            if data_list:
                data = [list(row) for row in data_list]  # ensure all rows are lists
                if not data:
                    continue
                col_count = len(data[0])
                page_w = letter[0] - 2 * inch
                col_widths = [page_w / col_count] * col_count
                table = Table(data, colWidths=col_widths)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), "#eeeeee"),
                            ("GRID", (0, 0), (-1, -1), 1, "#cccccc"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                elements.append(table)
            elements.append(Spacer(1, 12))

        doc.build(elements)
        return filepath

    # ------------------------------------------------------------------
    # Public report methods
    # ------------------------------------------------------------------

    def generate_daily_occupancy(self, day: date | None = None) -> dict[str, str]:
        """Generate daily occupancy PDF + CSV reports."""
        if day is None:
            day = date.today()
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)

        from apps.occupancy.models import OccupancyEvent

        events = list(
            OccupancyEvent.objects.filter(  # type: ignore[attr-defined]
                timestamp__gte=start, timestamp__lt=end
            )
        )

        total_arrivals = sum(
            1 for e in events if e.event_type in ("occupied", "car_present")
        )  # type: ignore[attr-defined]
        total_departures = sum(
            1 for e in events if e.event_type in ("vacant", "car_absent")
        )  # type: ignore[attr-defined]

        pdf_path = self._write_pdf_report(
            title=f"Daily Occupancy Report — {day.isoformat()}",
            sections=[
                {
                    "heading": "Summary",
                    "data": [
                        ["Total Arrivals Today", str(total_arrivals)],
                        ["Total Departures Today", str(total_departures)],
                        [
                            "Reporting Period",
                            f"{start.strftime('%Y-%m-%d %H:%M')} to {end.strftime('%Y-%m-%d %H:%M')}",
                        ],
                    ],
                },
            ],
        )

        csv_path = self.output_dir / f"{day.isoformat()}_daily_occupancy.csv"
        with open(csv_path, "w", newline="") as f:  # type: ignore[operator]
            writer = csv.writer(f)
            writer.writerow(["date", "arrivals", "departures"])
            writer.writerow([day.isoformat(), total_arrivals, total_departures])

        return {"pdf": str(pdf_path), "csv": str(csv_path)}

    def generate_daily_sales(self, day: date | None = None) -> dict[str, str]:
        """Generate daily sales PDF + CSV reports."""
        if day is None:
            day = date.today()
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)

        from apps.revenue.models import OccupancySession

        sessions = list(
            OccupancySession.objects.filter(  # type: ignore[attr-defined]
                check_in__gte=start, check_in__lt=end
            )
        )

        pdf_path = self._write_pdf_report(
            title=f"Daily Sales Report — {day.isoformat()}",
            sections=[
                {
                    "heading": "Sessions Today",
                    "data": [
                        ["Start Time", "Room ID", "Status", "Source"],
                    ]
                    + [
                        [
                            s.check_in.isoformat()
                            if hasattr(s.check_in, "isoformat")
                            else str(s.check_in),
                            s.room_id,
                            s.status,
                            s.source,
                        ]
                        for s in sessions[:50]
                    ],
                },  # type: ignore[attr-defined]
            ],
        )

        csv_path = self.output_dir / f"{day.isoformat()}_daily_sales.csv"
        with open(csv_path, "w", newline="") as f:  # type: ignore[operator]
            writer = csv.writer(f)
            writer.writerow(
                ["session_id", "room_id", "check_in", "check_out", "status", "source"]
            )
            for s in sessions:
                co = (
                    s.check_out.isoformat()
                    if hasattr(s.check_out, "isoformat") and s.check_out
                    else ""
                )  # type: ignore[attr-defined]
                writer.writerow(
                    [
                        s.pk,
                        s.room_id,
                        s.check_in.isoformat()
                        if hasattr(s.check_in, "isoformat")
                        else str(s.check_in),
                        co,
                        s.status,
                        s.source,
                    ]
                )

        return {"pdf": str(pdf_path), "csv": str(csv_path)}

    def generate_exception_report(self, day: date | None = None) -> dict[str, str]:
        """Generate exception report for sensor issues."""
        if day is None:
            day = date.today()
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)

        from apps.occupancy.models import OccupancyEvent

        events = list(
            OccupancyEvent.objects.filter(  # type: ignore[attr-defined]
                timestamp__gte=start, timestamp__lt=end
            )
        )

        room_change_counts: dict[str, int] = {}
        sensor_errors: list[str] = []
        manual_overrides: list[dict[str, str]] = []

        for ev in events:
            rid = ev.room_id  # type: ignore[attr-defined]
            etype = ev.event_type  # type: ignore[attr-defined]
            room_change_counts[rid] = room_change_counts.get(rid, 0) + 1
            if etype == "sensor_error":
                sensor_errors.append(ev.notes or "")  # type: ignore[attr-defined]
            if etype == "manual_override":
                manual_overrides.append(
                    {
                        "room_id": rid,
                        "time": ev.timestamp.isoformat()
                        if hasattr(ev.timestamp, "isoformat")
                        else str(ev.timestamp),  # type: ignore[attr-defined]
                        "notes": ev.notes or "",  # type: ignore[attr-defined]
                    }
                )

        pdf_path = self._write_pdf_report(
            title=f"Exception Report — {day.isoformat()}",
            sections=[
                {
                    "heading": "Rooms with Excessive Changes (>3/day)",
                    "data": [
                        ["Room", "State Change Count"],
                    ]
                    + [[r, c] for r, c in room_change_counts.items() if c > 3],
                },
                {
                    "heading": "Sensor Errors",
                    "data": ([["Error Details"]] + [[e] for e in sensor_errors]),
                },
                {
                    "heading": "Manual Overrides",
                    "data": [
                        ["Room", "Time", "Notes"],
                    ]
                    + [[o["room_id"], o["time"], o["notes"]] for o in manual_overrides],
                },
            ],
        )

        csv_path = self.output_dir / f"{day.isoformat()}_exceptions.csv"
        with open(csv_path, "w", newline="") as f:  # type: ignore[operator]
            writer = csv.writer(f)
            writer.writerow(["type", "details"])
            for r, c in room_change_counts.items():
                if c > 3:
                    writer.writerow(["excessive_changes", f"{r}: {c} changes"])
            for e in sensor_errors:
                writer.writerow(["sensor_error", e])
            for o in manual_overrides:
                writer.writerow(["manual_override", f"{o['room_id']}: {o['notes']}"])

        return {"pdf": str(pdf_path), "csv": str(csv_path)}

    def generate_cuadre_pdf(  # type: ignore[no-untyped-def]
        self,
        date_str: str,
        shift_number: int,
        tiers: dict[str, Any],
        total_rooms: int,
        total_revenue: float,
    ) -> BytesIO:
        """Generate PDF report matching the manual Cuadre ATH paper format."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import (
                ParagraphStyle,
                getSampleStyleSheet,
            )
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError:
            buffer = BytesIO()
            buffer.write(b"%PDF-1.4\nPlaceholder Cuadre PDF")
            return buffer

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "CustomTitle", parent=styles["Heading1"], fontSize=18, spaceAfter=20
        )

        elements: list[Any] = []
        elements.append(Paragraph("Motel Occupancy - Cuadre Report", title_style))
        elements.append(
            Paragraph(f"Date: {date_str} | Shift: {shift_number}", styles["Normal"])
        )
        elements.append(Spacer(1, 20))

        headers = ["Tier", "Room Count", "Revenue"]
        rows = [headers]

        tier_labels = {
            "tier_1_bgo": "1 BGO ($40)",
            "tier_2_y0_dndein": "2 Y0 Dndein ($45)",
            "tier_3_boo": "3 BOO ($50)",
            "tier_4_buys": "4 BUYS ($70)",
            "tier_5_s0_luxury": "9.S0 ($100)",
        }

        for key, label in tier_labels.items():
            count = tiers.get(key, {}).get("count", 0)
            revenue = tiers.get(key, {}).get("revenue", 0.0)
            rows.append([label, str(count), f"${revenue:.2f}"])

        rows.append(["TOTAL", str(total_rooms), f"${total_revenue:.2f}"])

        table = Table(rows)
        table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 12),
                    ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 11),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#ffffcc")),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer


# Singleton for import convenience.
report_generator = ReportGenerator()
