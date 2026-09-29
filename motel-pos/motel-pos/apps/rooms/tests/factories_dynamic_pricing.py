"""Factory for DynamicPricingRule."""

import datetime
from decimal import Decimal

import factory.django

from apps.rooms.models import DynamicPricingRule


class DynamicPricingRuleFactory(factory.django.DjangoModelFactory):
    """Factory for DynamicPricingRule model."""

    class Meta:
        model = DynamicPricingRule

    tier_code = "1 BGO"
    name = factory.Sequence(lambda n: f"Rule {n}")
    rule_type = DynamicPricingRule.RuleType.SPECIAL
    start_date = factory.LazyFunction(lambda: datetime.date(2026, 7, 4))
    end_date = factory.LazyFunction(lambda: datetime.date(2026, 7, 5))
    day_of_week = ""
    price_override = Decimal("55.00")
    description = "Test rule"
    is_active = True
    priority = 100
