"""Seed room amenities and sample maintenance logs."""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from decimal import Decimal
from datetime import date, timedelta
from apps.rooms.models import RoomAmenity, MaintenanceLog

print("=== Seeding Room-Amenity Associations ===")
# Assign default amenities to all rooms
room_amenity_map = {
    "1BGO": ["tv", "ac"],
    "2Y0Dndein": ["tv", "ac", "pool"],
    "3BOO": ["tv", "ac", "pool"],
    "4BUYS": ["tv", "ac", "jacuzzi", "pool", "speaker"],
    "9S0": ["tv", "ac", "jacuzzi", "pool", "speaker"],
}

# For the 5 rooms we have
rooms = list(RoomAmenity._meta.model.objects.model.__module__)  # placeholder — just use Room directly
from apps.rooms.models import Room

for room in Room.objects.filter(active=True):
    tier_base = room.pricing_tier_code or ""
    base_key = tier_base.replace(" ", "").replace(".", "")
    if base_key == "1BGO":
        amenity_names = ["tv", "ac"]
    elif base_key == "2Y0Dndein":
        amenity_names = ["tv", "ac", "pool"]
    elif base_key == "3BOO":
        amenity_names = ["tv", "ac", "pool"]
    elif base_key == "4BUYS":
        amenity_names = ["tv", "ac", "jacuzzi", "pool", "speaker"]
    elif base_key == "9S0":
        amenity_names = ["tv", "ac", "jacuzzi", "pool", "speaker"]
    else:
        amenity_names = ["tv", "ac"]

    from apps.rooms.models import Amenity
    for name in amenity_names:
        try:
            am = Amenity.objects.get(name=name)
            obj, created = RoomAmenity.objects.get_or_create(
                room_id=room.room_id, amenity_id=am.id,
                defaults={"status": "active"},
            )
            if created:
                print(f"  OK {room.room_number}: {name}")
        except Amenity.DoesNotExist:
            pass

print("\n=== Seeding Sample Maintenance Logs ===")
# Create sample maintenance items
sample_maintenance = [
    ("1BGO", "Plumbing", "AC unit filter replacement", True, 30, None, date.today() + timedelta(days=5), Decimal("25.00"), None, "", "", "scheduled"),
    ("4BUYS", "Electrical", "Patio lighting inspection", False, None, date(2026, 5, 10), date.today() + timedelta(days=-3), Decimal("75.00"), "Carlos M.", "", "pending"),
    ("3BOO", "Painting", "Exterior touch-up near balcony", False, None, None, date.today() + timedelta(days=14), Decimal("120.00"), "Maria T.", "paintpros@motel.com", "in_progress"),
    ("9S0", "Pool/Maintenance", "Jacuzzi heater check", True, 90, None, date.today() + timedelta(days=10), None, "", "", "scheduled"),
    ("2Y0Dndein", "Housekeeping", "Carpet cleaning", False, None, date(2026, 3, 1), None, Decimal("85.00"), "", "", "completed"),
]

for room_id_cat, category, description, recurring, interval, last_done, next_due, est_cost, assigned, vendor, status in sample_maintenance:
    room = Room.objects.filter(room_number__in=["Room 101","Room 102","Room 201","Suite A","Luxury Suite"]).filter(
        room_id=room_id_cat
    ).first()
    if not room:
        print(f"  SKIP Room not found for {room_id_cat}")
        continue
    obj, created = MaintenanceLog.objects.get_or_create(
        room_id=room.room_id, category=category, description=description,
        defaults={
            "is_recurring": recurring,
            "recurrence_interval_days": interval,
            "last_performed": last_done,
            "next_due": next_due if next_due else None,
            "estimated_cost": est_cost,
            "assigned_to": assigned,
            "vendor_contact": vendor,
            "status": status,
        }
    )
    if created:
        print(f"  OK Maintenance for {room.room_number}: {category} ({status})")

from apps.rooms.models import RoomAmenity, MaintenanceLog
print(f"\nTotals — RoomAmenity: {RoomAmenity.objects.count()}, MaintenanceLog: {MaintenanceLog.objects.count()}")
