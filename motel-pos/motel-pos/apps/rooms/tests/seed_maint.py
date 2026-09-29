"""Seed room amenities and sample maintenance logs."""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from decimal import Decimal
from datetime import date, timedelta
from apps.rooms.models import RoomAmenity, MaintenanceLog, Room, Amenity

print("=== Seeding Sample Maintenance Logs ===")
room_lookup = {
    "1BGO": "Room 101",
    "2Y0Dndein": "Room 102",
    "3BOO": "Room 201",
    "4BUYS": "Suite A",
    "9S0": "Luxury Suite",
}

samples = [
    {"room_id_cat": "1BGO", "category": "Plumbing", "description": "AC unit filter replacement",
     "recurring": True, "interval": 30, "last_done": None,
     "next_due": date.today() + timedelta(days=5), "est_cost": Decimal("25.00"),
     "assigned": "", "vendor": "", "status": "scheduled"},

    {"room_id_cat": "4BUYS", "category": "Electrical", "description": "Patio lighting inspection",
     "recurring": False, "interval": None,
     "last_done": date(2026, 5, 10),
     "next_due": date.today() + timedelta(days=-3), "est_cost": Decimal("75.00"),
     "assigned": "Carlos M.", "vendor": "", "status": "pending"},

    {"room_id_cat": "3BOO", "category": "Painting", "description": "Exterior touch-up near balcony",
     "recurring": False, "interval": None, "last_done": None,
     "next_due": date.today() + timedelta(days=14), "est_cost": Decimal("120.00"),
     "assigned": "Maria T.", "vendor": "paintpros@motel.com", "status": "in_progress"},

    {"room_id_cat": "9S0", "category": "Pool/Maintenance", "description": "Jacuzzi heater check",
     "recurring": True, "interval": 90, "last_done": None,
     "next_due": date.today() + timedelta(days=10), "est_cost": None,
     "assigned": "", "vendor": "", "status": "scheduled"},

    {"room_id_cat": "2Y0Dndein", "category": "Housekeeping", "description": "Carpet cleaning",
     "recurring": False, "interval": None,
     "last_done": date(2026, 3, 1),
     "next_due": None, "est_cost": Decimal("85.00"),
     "assigned": "", "vendor": "", "status": "completed"},
]

for s in samples:
    room = Room.objects.filter(room_id=s["room_id_cat"]).first()
    if not room:
        print(f"  SKIP Room not found for {s['room_id_cat']}")
        continue
    obj, created = MaintenanceLog.objects.get_or_create(
        room_id=room.room_id, category=s["category"], description=s["description"],
        defaults={
            "is_recurring": s["recurring"],
            "recurrence_interval_days": s["interval"],
            "last_performed": s["last_done"],
            "next_due": s["next_due"],
            "estimated_cost": s["est_cost"],
            "assigned_to": s["assigned"],
            "vendor_contact": s["vendor"],
            "status": s["status"],
        }
    )
    if created:
        print(f"  OK Maintenance for {room.room_number}: {s['category']} ({s['status']})")

from apps.rooms.models import MaintenanceLog, RoomAmenity
print(f"\nTotals — RoomAmenity: {RoomAmenity.objects.count()}, MaintenanceLog: {MaintenanceLog.objects.count()}")
