"""Seed data for YESS MOTEL — pricing tiers, amenities, and sample rooms.

Run via: DJANGO_SETTINGS_MODULE=config.settings python -c "from apps.rooms.seed import run_seed; run_seed()"
"""

import django

django.setup()

from decimal import Decimal

from apps.rooms.models import Amenity, PricingTier, Room


def run_seed():
    """Seed pricing tiers, amenities, and sample rooms."""
    seeded = {"tiers": set(), "amenities": set()}

    # ── Pricing Tiers ──────────────────────────────────────────────
    tiers: list[tuple[str, Decimal, str]] = [
        ("1 BGO", Decimal("40.00"), "Standard room"),
        ("2 Y0 Dndein", Decimal("45.00"), "Basic Plus"),
        ("3 BOO", Decimal("50.00"), "Premium"),
        ("4 BUYS", Decimal("70.00"), "Suite"),
        ("9.S0", Decimal("100.00"), "Luxury Suite"),
    ]
    for code, price, desc in tiers:
        obj, created = PricingTier.objects.get_or_create(
            code=code,
            defaults={"price_per_night": price, "description": desc},
        )
        if created:
            print(f"  ✅ Tier: {obj}")
        seeded["tiers"].add(code)

    # ── Amenities ──────────────────────────────────────────────────
    amenities: list[tuple[str, str, str, Decimal]] = [
        ("tv", "TV", "fa-tv", Decimal("0.00")),
        ("ac", "Air Conditioning", "fa-snowflake", Decimal("0.00")),
        ("pool", "Pool View", "fa-swimming-pool", Decimal("5.00")),
        ("jacuzzi", "Jacuzzi Access", "fa-bath", Decimal("10.00")),
        ("speaker", "Bluetooth Speaker", "fa-volume-up", Decimal("2.00")),
    ]
    for name, display, icon, surcharge in amenities:
        obj, created = Amenity.objects.get_or_create(
            name=name,
            defaults={
                "display_name": display,
                "icon_class": icon,
                "price_surcharge": surcharge,
            },
        )
        if created:
            print(f"  ✅ Amenity: {obj}")
        seeded["amenities"].add(name)

    # ── Sample Rooms (8 rooms from photo) ─────────────────────────
    room_defs: list[tuple[str, str, str, str, int]] = [
        ("1 BGO", "Room 101", "sensor-room-101", "", 2),
        ("2 Y0 Dndein", "Room 102", "sensor-room-102", "", 2),
        ("3 BOO", "Room 201", "sensor-room-201", "", 3),
        ("4 BUYS", "Suite A", "sensor-suite-a", "", 4),
        ("9.S0", "Luxury Suite", "sensor-luxury-suite", "", 4),
        ("1 BGO", "Room 103", "sensor-room-103", "", 2),
        ("2 Y0 Dndein", "Room 104", "sensor-room-104", "", 2),
        ("3 BOO", "Room 202", "sensor-room-202", "", 3),
    ]
    for index, (code, number, sensor_id, notes, occupants) in enumerate(room_defs):
        rid = "".join(character for character in number if character.isdigit()) or str(900 + index)
        obj, created = Room.objects.get_or_create(
            room_id=rid,
            defaults={
                "room_number": number,
                "sensor_id": sensor_id,
                "pricing_tier_code": code,
                "max_occupants": occupants,
                "active": True,
                "notes": notes or f"Seeded during migration. Tier: {code}",
            },
        )
        if created:
            print(f"  ✅ Room: {obj}")

    total_tiers = PricingTier.objects.count()
    total_amenities = Amenity.objects.count()
    total_rooms = Room.objects.count()
    print(
        f"\n📊 Totals — Tiers: {total_tiers}, Amenities: {total_amenities}, Rooms: {total_rooms}"
    )


if __name__ == "__main__":
    run_seed()
