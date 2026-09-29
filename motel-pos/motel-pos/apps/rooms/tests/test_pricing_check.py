"""Manual pricing-engine diagnostic.

Run directly with ``python apps/rooms/tests/test_pricing_check.py``. Keeping all
database work inside ``main`` prevents this diagnostic from breaking pytest
collection.
"""

import os
from datetime import date

import django


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    from apps.rooms.models import PricingTier  # noqa: PLC0415
    from apps.rooms.pricing import dynamic_pricing_engine  # noqa: PLC0415

    today = date.today()
    print(f"Today: {today} weekday={today.strftime('%A')}")
    for tier in PricingTier.objects.filter(active=True):
        price = dynamic_pricing_engine.resolve_price(tier.code, today)
        base = float(tier.price_per_night)
        summary = dynamic_pricing_engine.get_seasonal_summary(tier.code)
        active_rules = [item["name"] for item in summary]
        print(f"  {tier.code}: ${price:.2f} (base: ${base:.2f}) rules={active_rules}")

    print()
    dates = [
        ("Sat July 4", date(2026, 7, 4)),
        ("Fri July 3", date(2026, 7, 3)),
        ("Mon Jan 15", date(2026, 1, 15)),
    ]
    for label, target_date in dates:
        print(f"--- {label} ({target_date.strftime('%A')}) ---")
        for tier in PricingTier.objects.filter(active=True):
            price = dynamic_pricing_engine.resolve_price(tier.code, target_date)
            print(f"  {tier.code}: ${price:.2f}")


if __name__ == "__main__":
    main()
