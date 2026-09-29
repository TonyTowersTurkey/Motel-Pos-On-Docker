"""Factory-boy factories for room-related models."""

import datetime
from decimal import Decimal

import factory.django

from apps.rooms.models import (
    Amenity,
    MaintenanceLog,
    PricingTier,
    RentalSession,
    Room,
    RoomAmenity,
    DynamicPricingRule,
)


class RoomFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for Room model."""

    class Meta:
        model = Room

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    room_number = factory.Sequence(lambda n: str(100 + n))
    sensor_id = factory.Sequence(lambda n: f"sensor_{100 + n}")
    active = True
    notes = "Test room"
    pricing_tier_code = "1 BGO"
    max_occupants = 2
    amenities_snapshot = ""


class PricingTierFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for PricingTier model."""

    class Meta:
        model = PricingTier

    code = factory.Sequence(lambda n: f"TIER_{n}")
    price_per_night = Decimal("40.00")
    description = "Test tier"
    active = True


class AmenityFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for Amenity model."""

    class Meta:
        model = Amenity

    name = factory.Sequence(lambda n: f"amenity_{n}")
    display_name = factory.Sequence(lambda n: f"Amenity {n}")
    icon_class = "fa-icon"
    price_surcharge = Decimal("5.00")


class RoomAmenityFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for RoomAmenity model."""

    class Meta:
        model = RoomAmenity

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    amenity_id = factory.Sequence(lambda n: n + 1)
    status = RoomAmenity.AmenityStatus.ACTIVE
    notes = "Assigned amenity"


class MaintenanceLogFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for MaintenanceLog model."""

    class Meta:
        model = MaintenanceLog

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    category = "HVAC"
    description = "Maintenance test"
    is_recurring = False
    recurrence_interval_days = None
    next_due = factory.LazyFunction(
        lambda: datetime.date.today() + datetime.timedelta(days=30)
    )
    estimated_cost = Decimal("150.00")
    actual_cost = None
    assigned_to = "maintenance_team"
    vendor_contact = ""
    status = MaintenanceLog.Status.PENDING
    completion_notes = ""


class RentalSessionFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    """Factory for RentalSession model."""

    class Meta:
        model = RentalSession

    room_id = factory.Sequence(lambda n: f"room_{100 + n}")
    start_time = factory.LazyFunction(lambda: datetime.datetime(2026, 6, 15))
    status = RentalSession.Status.CONFIRMED
    source = "web"
    reviewed_by = "manager_1"
    notes = "Test session"


class DynamicPricingRuleFactory(factory.django.DjangoModelFactory):
    """Factory for DynamicPricingRule model."""

    class Meta:
        model = DynamicPricingRule  # type: ignore[name-defined]

    tier_code = "1 BGO"
    name = factory.Sequence(lambda n: f"Rule {n}")
    rule_type = DynamicPricingRule.RuleType.SPECIAL  # type: ignore[attr-defined]
    start_date = factory.LazyFunction(lambda: datetime.date(2026, 7, 4))
    end_date = factory.LazyFunction(lambda: datetime.date(2026, 7, 5))
    day_of_week = ""
    price_override = Decimal("55.00")
    description = "Test rule"
    is_active = True
    priority = 100

