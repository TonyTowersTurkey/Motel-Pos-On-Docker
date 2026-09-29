from django.db import migrations, models


def seed_pricing_tiers(apps, schema_editor):
    PricingTier = apps.get_model("rooms", "PricingTier")
    tiers = [
        ("1 BGO", 40.0, "Standard room"),
        ("2 Y0 Dndein", 45.0, "Basic Plus"),
        ("3 BOO", 50.0, "Premium"),
        ("4 BUYS", 70.0, "Suite"),
        ("9.S0", 100.0, "Luxury Suite"),
    ]
    for code, price, desc in tiers:
        PricingTier.objects.get_or_create(
            code=code, defaults={"price_per_night": price, "description": desc}
        )


def seed_amenities(apps, schema_editor):
    Amenity = apps.get_model("rooms", "Amenity")
    amenities = [
        ("TV", "TV", 0.0, ""),
        ("AC", "Air Conditioning", 0.0, ""),
        ("Pool", "Pool Access", 5.0, "fas fa-swimming-pool"),
        ("Jacuzzi", "Jacuzzi Access", 10.0, "fas fa-hot-tub"),
        ("Speaker", "Bluetooth Speaker", 2.0, "fas fa-volume-up"),
        ("MiniBar", "Mini Bar", 8.0, "fas fa-wine-bottle"),
    ]
    for name, display, surcharge, icon in amenities:
        Amenity.objects.get_or_create(
            name=name,
            defaults={"display_name": display, "price_surcharge": surcharge, "icon_class": icon},
        )


def seed_rooms(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    rooms = [
        ("room_101", "101", 2, "1 BGO"),
        ("room_102", "102", 2, "1 BGO"),
        ("room_103", "103", 2, "2 Y0 Dndein"),
        ("room_104", "104", 3, "3 BOO"),
        ("room_105", "105", 4, "4 BUYS"),
    ]
    for rid, rnum, maxocc, tier in rooms:
        Room.objects.get_or_create(
            room_id=rid, defaults={
                "room_number": rnum, "sensor_id": f"sensor_{rid}",
                "active": True, "max_occupants": maxocc,
                "pricing_tier_code": tier,
            }
        )


class Migration(migrations.Migration):
    dependencies = [("rooms", "0002_room_current_state")]

    operations = [
        migrations.RunPython(seed_pricing_tiers),
        migrations.RunPython(seed_amenities),
        migrations.RunPython(seed_rooms),
    ]
