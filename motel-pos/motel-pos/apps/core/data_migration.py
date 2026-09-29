"""Data migration: old SQLite (FastAPI) → new Django ORM schema.

Reads from `data/motel_occupancy.db` and writes to the active Django database
(using whatever backend is configured in DJANGO_SETTINGS_MODULE).

Run via:
    cd motel-occupancy/motel_django && DJANGO_SETTINGS_MODULE=config.settings .venv/bin/python apps/core/data_migration.py
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime

# Ensure Django is bootstrapped before any model imports.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from decimal import Decimal

from django.db import transaction

from apps.occupancy.models import (  # noqa: E402
    AuditLog,
    OccupancyEvent,
    SensorReading,
)
from apps.revenue.models import OccupancySession, ShiftLedger  # noqa: E402

# --- Import target models (Django ORM) ---
from apps.rooms.models import (
    Amenity,
    MaintenanceLog,
    PricingTier,
    Room,
    RoomAmenity,
)
from apps.users.models import User  # noqa: E402

# --- Source DB path ---
# Walk up: apps/core/ -> apps/ -> motel_django/ -> motel-occupancy/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # apps/core
_APPS_DIR = os.path.dirname(_SCRIPT_DIR)  # apps
_PROJECT_DIR = os.path.dirname(_APPS_DIR)  # motel_django
_PARENT_DIR = os.path.dirname(_PROJECT_DIR)  # motel-occupancy

OLD_DB = os.path.join(_PARENT_DIR, "data", "motel_occupancy.db")


def _read_rows(table: str) -> list[dict]:
    """Read all rows from the source SQLite database."""
    import sqlite3

    conn = sqlite3.connect(OLD_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    exists = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        conn.close()
        return []
    rows = cur.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()
    col_names = [d[0] for d in cur.description]
    return [dict(zip(col_names, row)) for row in rows]


# --- Migration helpers ---


def _dt_from_old(val) -> datetime | None:
    """Convert old DB timestamps to timezone-aware datetime."""
    if val is None:
        return None
    if isinstance(val, str):
        val = val.replace(" ", "T", 1)
        if val.endswith("Z"):
            val = val[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(val).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            pass
    if isinstance(val, date) and not isinstance(val, datetime):
        return datetime.combine(val, datetime.min.time(), tzinfo=UTC)
    if isinstance(val, datetime) and val.tzinfo is None:
        return val.replace(tzinfo=UTC)
    return val


def _f_to_d(val) -> Decimal | None:
    """Convert float to Decimal for Django fields."""
    if val is None:
        return None
    return Decimal(str(float(val)))


def _i_or_none(val, default=0):
    """Int conversion with None guard."""
    if val is None:
        return default
    return int(val)


# --- Per-model migration functions ---


def migrate_rooms() -> dict[str, int]:
    old_rows = _read_rows("rooms")
    count = 0
    for row in old_rows:
        defaults = {
            "room_number": row["room_number"],
            "sensor_id": row["sensor_id"],
            "active": bool(row["active"]),
            "notes": row.get("notes") or "",
            "pricing_tier_code": row.get("pricing_tier_code") or "",
            "max_occupants": _i_or_none(row.get("max_occupants"), 1),
            "amenities_snapshot": row.get("amenities_snapshot") or "",
            "current_state": "vacant",
        }
        obj, created = Room.objects.update_or_create(
            room_id=row["room_id"], defaults=defaults
        )
        count += 1 if created else 0
    return {"rooms_migrated": count}


def migrate_pricing_tiers() -> dict[str, int]:
    old_rows = _read_rows("pricing_tiers")
    count = 0
    for row in old_rows:
        defaults = {
            "code": row["code"],
            "price_per_night": _f_to_d(row.get("price_per_night")) or Decimal("0.00"),
            "description": row.get("description") or "",
            "active": bool(row.get("active", True)),
        }
        obj, created = PricingTier.objects.update_or_create(
            code=row["code"], defaults=defaults
        )
        count += 1 if created else 0
    return {"pricing_tiers_migrated": count}


def migrate_amenities() -> dict[str, int]:
    old_rows = _read_rows("amenities")
    count = 0
    for row in old_rows:
        defaults = {
            "name": row["name"],
            "display_name": row.get("display_name") or "",
            "icon_class": row.get("icon_class") or "",
            "price_surcharge": _f_to_d(row.get("price_surcharge")) or Decimal("0.00"),
        }
        obj, created = Amenity.objects.update_or_create(
            name=row["name"], defaults=defaults
        )
        count += 1 if created else 0
    return {"amenities_migrated": count}


def migrate_room_amenities() -> dict[str, int]:
    old_rows = _read_rows("room_amenities")
    count = 0
    for row in old_rows:
        defaults = {
            "status": row.get("status") or "active",
            "notes": row.get("notes") or "",
        }
        obj, created = RoomAmenity.objects.update_or_create(
            room_id=row["room_id"],
            amenity_id=row["amenity_id"],
            defaults=defaults,
        )
        count += 1 if created else 0
    return {"room_amenities_migrated": count}


def migrate_maintenance_log() -> dict[str, int]:
    old_rows = _read_rows("maintenance_log")
    count = 0
    for row in old_rows:
        defaults = {
            "category": row.get("category") or "",
            "description": row.get("description") or "",
            "is_recurring": bool(row.get("is_recurring", False)),
            "recurrence_interval_days": _i_or_none(row.get("recurrence_interval_days")),
            "last_performed": (
                _dt_from_old(row["last_performed"]).date()
                if row.get("last_performed")
                else None
            ),
            "next_due": (
                _dt_from_old(row["next_due"]).date() if row.get("next_due") else None
            ),
            "estimated_cost": _f_to_d(row.get("estimated_cost")),
            "actual_cost": _f_to_d(row.get("actual_cost")),
            "assigned_to": row.get("assigned_to") or "",
            "vendor_contact": row.get("vendor_contact") or "",
            "status": row.get("status") or "pending",
            "completion_notes": row.get("completion_notes") or "",
        }
        pk = row["id"] if "id" in row else None
        obj, created = MaintenanceLog.objects.update_or_create(
            pk=pk,
            defaults=defaults,
        )
        if not created and obj.pk is None:
            obj.save()
        count += 1
    return {"maintenance_log_migrated": count}


def migrate_occupancy_events() -> dict[str, int]:
    old_rows = _read_rows("occupancy_events")
    count = 0
    TYPE_MAP = {
        "occupied": OccupancyEvent.EventType.ARRIVAL,
        "vacant": OccupancyEvent.EventType.DEPARTURE,
        "manual_override": OccupancyEvent.EventType.MANUAL_OVERRIDE,
        "arrival": OccupancyEvent.EventType.ARRIVAL,
        "departure": OccupancyEvent.EventType.DEPARTURE,
        "check_in": OccupancyEvent.EventType.CHECK_IN,
        "check_out": OccupancyEvent.EventType.CHECK_OUT,
    }
    for row in old_rows:
        event_type_raw = str(row.get("event_type", ""))
        mapped_type = TYPE_MAP.get(event_type_raw, event_type_raw)
        defaults = {
            "event_type": mapped_type,
            "confidence": float(row.get("confidence", 1.0)),
            "source": row.get("source") or "sensor_auto",
            "notes": row.get("notes") or "",
            "timestamp": _dt_from_old(row["timestamp"]),
        }
        obj, created = OccupancyEvent.objects.update_or_create(
            event_id=row["event_id"], defaults=defaults
        )
        count += 1 if created else 0
    return {"occupancy_events_migrated": count}


def migrate_sensor_readings() -> dict[str, int]:
    old_rows = _read_rows("sensor_readings")
    count = 0
    for row in old_rows:
        defaults = {
            "room_id": row["room_id"],
            "timestamp": _dt_from_old(row["timestamp"]),
            "distance_mm": int(row["distance_mm"])
            if row.get("distance_mm") is not None
            else 0,
            "presence": row.get("presence") or "",
            "illuminance": _i_or_none(row.get("illuminance")),
            "battery_level": float(row["battery_level"])
            if row.get("battery_level") is not None
            else None,
            "signal_strength_dbm": _i_or_none(row.get("signal_strength_dbm")),
            "raw_payload": row.get("raw_payload") or "",
        }
        obj, created = SensorReading.objects.update_or_create(
            reading_id=row["reading_id"], defaults=defaults
        )
        count += 1 if created else 0
    return {"sensor_readings_migrated": count}


def migrate_audit_log() -> dict[str, int]:
    old_rows = _read_rows("audit_log")
    count = 0
    for row in old_rows:
        defaults = {
            "timestamp": _dt_from_old(row["timestamp"]),
            "user": row.get("user") or "",
            "action": row.get("action") or "",
            "object_type": row.get("object_type") or "",
            "object_id": _i_or_none(row.get("object_id")),
            "previous_value": row.get("previous_value") or "",
            "new_value": row.get("new_value") or "",
        }
        obj, created = AuditLog.objects.update_or_create(
            audit_id=row["audit_id"], defaults=defaults
        )
        count += 1 if created else 0
    return {"audit_log_migrated": count}


def migrate_occupancy_sessions() -> dict[str, int]:
    old_rows = _read_rows("occupancy_sessions")
    count = 0
    SOURCE_MAP = {
        "sensor_auto": OccupancySession.Source.SENSOR_AUTO,
        "manual_override": OccupancySession.Source.MANUAL_OVERRIDE,
        "front_desk": OccupancySession.Source.FRONT_DESK,
    }
    STATUS_MAP = {
        "active": OccupancySession.Status.ACTIVE,
        "checked_out": OccupancySession.Status.CHECKED_OUT,
        "cancelled": OccupancySession.Status.CANCELLED,
    }
    for row in old_rows:
        defaults = {
            "room_id": row["room_id"],
            "guest_name": row.get("guest_name") or "",
            "phone": row.get("phone") or "",
            "license_plate": row.get("license_plate") or "",
            "check_in": _dt_from_old(row["check_in"]),
            "check_out": _dt_from_old(row["check_out"]),
            "room_type_code": row.get("room_type_code") or "",
            "price_per_night": _f_to_d(row.get("price_per_night")),
            "amenities_charges": _f_to_d(row.get("amenities_charges"))
            or Decimal("0.00"),
            "estimated_revenue": _f_to_d(row.get("estimated_revenue")),
            "actual_revenue": _f_to_d(row.get("actual_revenue")),
            "source": SOURCE_MAP.get(
                row.get("source", ""), OccupancySession.Source.SENSOR_AUTO
            ),
            "status": STATUS_MAP.get(
                row.get("status", "active"), OccupancySession.Status.ACTIVE
            ),
            "notes": row.get("notes") or "",
        }
        obj, created = OccupancySession.objects.update_or_create(
            id=row["id"], defaults=defaults
        )
        count += 1 if created else 0
    return {"occupancy_sessions_migrated": count}


def migrate_shift_ledgers() -> dict[str, int]:
    old_rows = _read_rows("shift_ledger")
    count = 0
    for row in old_rows:
        defaults = {
            "shift_number": _i_or_none(row.get("shift_number"), 1),
            "tier_1_bgo_count": _i_or_none(row.get("tier_1_bgo_count"), 0),
            "tier_2_y0_dndein_count": _i_or_none(row.get("tier_2_y0_dndein_count"), 0),
            "tier_3_boo_count": _i_or_none(row.get("tier_3_boo_count"), 0),
            "tier_4_buys_count": _i_or_none(row.get("tier_4_buys_count"), 0),
            "tier_5_s0_luxury_count": _i_or_none(row.get("tier_5_s0_luxury_count"), 0),
            "tier_1_bgo_revenue": _f_to_d(row.get("tier_1_bgo_revenue"))
            or Decimal("0.00"),
            "tier_2_y0_dndein_revenue": _f_to_d(row.get("tier_2_y0_dndein_revenue"))
            or Decimal("0.00"),
            "tier_3_boo_revenue": _f_to_d(row.get("tier_3_boo_revenue"))
            or Decimal("0.00"),
            "tier_4_buys_revenue": _f_to_d(row.get("tier_4_buys_revenue"))
            or Decimal("0.00"),
            "tier_5_s0_luxury_revenue": _f_to_d(row.get("tier_5_s0_luxury_revenue"))
            or Decimal("0.00"),
            "subtotal": _f_to_d(row.get("subtotal")) or Decimal("0.00"),
            "barra_amount": _f_to_d(row.get("barra_amount")) or Decimal("0.00"),
            "ath_subtotal": _f_to_d(row.get("ath_subtotal")) or Decimal("0.00"),
            "logged_by": row.get("logged_by") or "",
            "verified_by": row.get("verified_by") or "",
            "notes": row.get("notes") or "",
        }
        # Try pk first
        # date column from old DB is TEXT (YYYY-MM-DD), not DateField
        d_str = row.get("date") or ""
        if isinstance(d_str, str):
            try:
                from datetime import date as _date_cls

                d = _date_cls.fromisoformat(d_str)
            except (ValueError, TypeError):
                d = None
        else:
            d = row.get("date")

        # Use date+shift_number as unique lookup instead of id
        obj, created = ShiftLedger.objects.update_or_create(
            date=d,
            shift_number=_i_or_none(row.get("shift_number"), 1),
            defaults=defaults,
        )
        if created:
            count += 1
            continue
        # Fallback: date + shift_number
        d_raw = row.get("date")
        if isinstance(d_raw, str):
            try:
                d = date.fromisoformat(d_raw)
            except (ValueError, TypeError):
                d = None
        else:
            d = _dt_from_old(d_raw).date() if d_raw else None
        if d is not None:
            _, created2 = ShiftLedger.objects.update_or_create(
                date=d,
                shift_number=_i_or_none(row.get("shift_number"), 1),
                defaults=defaults,
            )
            if created2 and not created:
                count += 1
    return {"shift_ledgers_migrated": count}


def migrate_default_users() -> dict[str, int]:

    DEFAULT_USERS = [
        ("manager", "manager", "Manager"),
        ("cashier", "cashier", "Cashier"),
    ]
    count = 0
    for username, pwd, name in DEFAULT_USERS:
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(
                username=username,
                password=pwd,
                email="",
                first_name=name,
                role=User.Role.MANAGER if username == "manager" else User.Role.CASHIER,
            )
            count += 1
    return {"default_users_created": count}


def run_migration() -> dict[str, int]:
    """Run all migrations in a single transaction."""
    print("=" * 60)
    print("Data Migration: Old SQLite → Django ORM")
    print(f"Source DB: {OLD_DB}")
    print(f"Target DB: {django.conf.settings.DATABASES['default']['NAME']}")
    print("=" * 60)

    if not os.path.exists(OLD_DB):
        print(f"ERROR: Source DB not found at {OLD_DB}")
        return {}

    results = {}
    with transaction.atomic():
        results |= migrate_pricing_tiers()
        results |= migrate_amenities()
        results |= migrate_room_amenities()
        results |= migrate_rooms()
        results |= migrate_maintenance_log()
        results |= migrate_occupancy_events()
        results |= migrate_sensor_readings()
        results |= migrate_audit_log()
        results |= migrate_occupancy_sessions()
        results |= migrate_shift_ledgers()

    # Users outside main transaction (auth tables may not be ready)
    try:
        results |= migrate_default_users()
    except Exception as e:
        print(f"WARNING: Default users migration failed: {e}")
        results["default_users_created"] = 0

    total = sum(v for v in results.values())
    print("=" * 60)
    print("Migration Summary:")
    for key, val in results.items():
        print(f"  {key}: {val}")
    print(f"Total records migrated: {total}")
    print("=" * 60)
    return results


if __name__ == "__main__":
    run_migration()
