"""Factory-boy factories for revenue-related models."""

from datetime import datetime, timedelta

import factory.django

from apps.revenue.models import OccupancySession, ShiftLedger


class OccupancySessionFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for OccupancySession model."""

    class Meta:
        model = OccupancySession

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    guest_name = factory.Faker("name")
    phone = factory.Faker("phone_number")
    license_plate = factory.Faker("license_plate")
    check_in = factory.LazyFunction(datetime.utcnow)
    room_type_code = "1 BGO"
    price_per_night = factory.Faker(
        "pydecimal", left_digits=2, right_digits=2, positive=True
    )
    amenities_charges = factory.Faker(
        "pydecimal", left_digits=1, right_digits=2, positive=True
    )
    source = OccupancySession.Source.SENSOR_AUTO
    status = OccupancySession.Status.ACTIVE


class ShiftLedgerFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for ShiftLedger model."""

    class Meta:
        model = ShiftLedger

    date = factory.LazyFunction(lambda: datetime.utcnow().date() + timedelta(days=30))
    shift_number = 1
    tier_1_bgo_count = 2
    tier_2_y0_dndein_count = 1
    tier_3_boo_count = 1
    tier_4_buys_count = 0
    tier_5_s0_luxury_count = 0
