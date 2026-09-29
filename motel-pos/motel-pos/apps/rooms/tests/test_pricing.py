"""Tests for dynamic pricing engine."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.test import TestCase, override_settings

from apps.rooms.models import DynamicPricingRule, PricingTier, Room
from apps.rooms.pricing import DynamicPricingEngine
from apps.rooms.tests.factories import (
    DynamicPricingRuleFactory,
    PricingTierFactory,
    RoomFactory,
)


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class DynamicPricingModelTest(TestCase):
    """Tests for the DynamicPricingRule model."""

    def test_create_minimal_rule(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 7, 1),
            price_override=Decimal("55.00"),
        )
        self.assertEqual(rule.tier_code, "1 BGO")
        self.assertTrue(rule.is_active)
        self.assertIsNone(rule.end_date)
        self.assertEqual(rule.priority, 100)

    def test_rule_str(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="3 BOO",
            name="Verano",
            rule_type=DynamicPricingRule.RuleType.SEASONAL,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            price_override=Decimal("65.00"),
        )
        self.assertIn("Verano", str(rule))
        self.assertIn("$65.00", str(rule))

    def test_rule_str_with_day_of_week(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Friday Premium",
            rule_type=DynamicPricingRule.RuleType.DAY_OF_WEEK,
            start_date=date(2026, 1, 1),
            day_of_week="fri",
            price_override=Decimal("50.00"),
        )
        self.assertIn("fri", str(rule))

    def test_is_date_in_window_special(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 7, 3),
            end_date=date(2026, 7, 5),
            price_override=Decimal("55.00"),
        )
        self.assertTrue(rule.is_date_in_window(date(2026, 7, 4)))
        self.assertFalse(rule.is_date_in_window(date(2026, 7, 2)))
        self.assertFalse(rule.is_date_in_window(date(2026, 7, 6)))

    def test_is_date_in_window_inactive(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            is_active=False,
            start_date=date(2026, 7, 1),
            price_override=Decimal("55.00"),
        )
        self.assertFalse(rule.is_date_in_window(date(2026, 7, 4)))

    def test_matches_day(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="3 BOO",
            start_date=date(2026, 1, 1),
            day_of_week="sat",
            price_override=Decimal("60.00"),
        )
        self.assertTrue(rule.matches_day(5))   # Saturday
        self.assertFalse(rule.matches_day(0))  # Monday

    def test_no_dow_returns_false(self):
        rule = DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            start_date=date(2026, 1, 1),
            price_override=Decimal("50.00"),
        )
        self.assertFalse(rule.matches_day(5))

    def test_unique_constraint(self):
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            rule_type=DynamicPricingRule.RuleType.DAY_OF_WEEK,
            start_date=date(2026, 1, 1),
            day_of_week="fri",
            price_override=Decimal("50.00"),
        )
        with self.assertRaises(Exception):
            DynamicPricingRule.objects.create(
                tier_code="1 BGO",
                rule_type=DynamicPricingRule.RuleType.DAY_OF_WEEK,
                start_date=date(2026, 7, 1),
                day_of_week="fri",
                price_override=Decimal("55.00"),
            )

    def test_ordering_by_priority(self):
        DynamicPricingRule.objects.create(
            tier_code="1 BGO", priority=50, start_date=date(2026, 1, 1),
            rule_type=DynamicPricingRule.RuleType.SPECIAL, price_override=Decimal("40.00"),
        )
        DynamicPricingRule.objects.create(
            tier_code="1 BGO", priority=200, start_date=date(2026, 1, 1),
            rule_type=DynamicPricingRule.RuleType.SPECIAL, price_override=Decimal("80.00"),
        )
        ordered = list(DynamicPricingRule.objects.filter(tier_code="1 BGO"))
        self.assertEqual(ordered[0].priority, 200)


class DynamicPricingEngineTest(TestCase):
    """Tests for the pricing engine resolution logic."""

    def setUp(self):
        # Clean slate
        DynamicPricingRule.objects.all().delete()
        PricingTier.objects.all().delete()

        # Create base tiers
        PricingTier.objects.create(code="1 BGO", price_per_night=Decimal("40.00"), description="Standard")
        PricingTier.objects.create(code="3 BOO", price_per_night=Decimal("50.00"), description="Premium")

    def test_base_price_no_rules(self):
        engine = DynamicPricingEngine()
        price = engine.resolve_price("1 BGO", date(2026, 7, 4))
        self.assertEqual(price, Decimal("40.00"))

    def test_special_override_wins(self):
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Independence Day",
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 7, 4),
            end_date=date(2026, 7, 4),
            price_override=Decimal("55.00"),
        )
        engine = DynamicPricingEngine()
        # On the special date: $55
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 4)), Decimal("55.00"))
        # Off the special date: base price
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 3)), Decimal("40.00"))

    def test_higher_priority_wins(self):
        DynamicPricingRule.objects.create(
            tier_code="3 BOO",
            name="Low priority",
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 7, 4),
            price_override=Decimal("55.00"),
            priority=100,
        )
        DynamicPricingRule.objects.create(
            tier_code="3 BOO",
            name="High priority",
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 7, 4),
            price_override=Decimal("75.00"),
            priority=200,
        )
        engine = DynamicPricingEngine()
        self.assertEqual(engine.resolve_price("3 BOO", date(2026, 7, 4)), Decimal("75.00"))

    def test_seasonal_override(self):
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Summer Season",
            rule_type=DynamicPricingRule.RuleType.SEASONAL,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 8, 31),
            price_override=Decimal("50.00"),
        )
        engine = DynamicPricingEngine()
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 4)), Decimal("50.00"))
        # Outside season: base price
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 1, 1)), Decimal("40.00"))

    def test_day_of_week_override(self):
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Friday Premium",
            rule_type=DynamicPricingRule.RuleType.DAY_OF_WEEK,
            start_date=date(2026, 1, 1),
            day_of_week="fri",
            price_override=Decimal("55.00"),
        )
        engine = DynamicPricingEngine()
        # July 4, 2026 is a Saturday (weekday 5)
        sat_date = date(2026, 7, 4)
        # July 3, 2026 is Friday (weekday 4)
        fri_date = date(2026, 7, 3)
        self.assertEqual(engine.resolve_price("1 BGO", sat_date), Decimal("40.00"))  # No Sat rule
        self.assertEqual(engine.resolve_price("1 BGO", fri_date), Decimal("55.00"))   # Fri = $55

    def test_seasonal_with_dow_filter(self):
        """Seasonal window + specific DoW = only that day in the window."""
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Summer Fridays",
            rule_type=DynamicPricingRule.RuleType.SEASONAL,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            day_of_week="fri",
            price_override=Decimal("55.00"),
        )
        engine = DynamicPricingEngine()
        # July 4 (Sat) — no DoW match → base price
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 4)), Decimal("40.00"))
        # July 3 (Fri) — within window + matches DoW
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 3)), Decimal("55.00"))

    def test_seasonal_no_dow_all_days(self):
        """Seasonal without DoW = all days in the window."""
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Summer Season All Days",
            rule_type=DynamicPricingRule.RuleType.SEASONAL,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            price_override=Decimal("50.00"),
        )
        engine = DynamicPricingEngine()
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 1)), Decimal("50.00"))
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 4)), Decimal("50.00"))
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 31)), Decimal("50.00"))

    def test_resolved_price_for_room(self):
        room = RoomFactory(room_id="test_42", pricing_tier_code="3 BOO")
        PricingTier.objects.filter(code="3 BOO").update(price_per_night=Decimal("50.00"))

        DynamicPricingRule.objects.create(
            tier_code="3 BOO",
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 7, 4),
            price_override=Decimal("80.00"),
        )
        engine = DynamicPricingEngine()
        self.assertEqual(engine.resolve_price_for_room("test_42", date(2026, 7, 4)), Decimal("80.00"))

    def test_nonexistent_tier_fallback(self):
        engine = DynamicPricingEngine()
        price = engine.resolve_price("99 ZZZ", date(2026, 7, 4))
        self.assertEqual(price, Decimal("40.00"))  # default fallback

    def test_open_ended_seasonal(self):
        """Seasonal with NULL end_date should match all dates after start."""
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Permanent Increase",
            rule_type=DynamicPricingRule.RuleType.SEASONAL,
            start_date=date(2026, 7, 1),
            price_override=Decimal("55.00"),
        )
        engine = DynamicPricingEngine()
        self.assertEqual(engine.resolve_price("1 BGO", date(2026, 7, 4)), Decimal("55.00"))
        self.assertEqual(engine.resolve_price("1 BGO", date(2027, 12, 31)), Decimal("55.00"))

    def test_get_seasonal_summary(self):
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Summer",
            rule_type=DynamicPricingRule.RuleType.SEASONAL,
            start_date=date(2026, 6, 1),
            price_override=Decimal("50.00"),
        )
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            name="Friday Premium",
            rule_type=DynamicPricingRule.RuleType.DAY_OF_WEEK,
            start_date=date(2026, 1, 1),
            day_of_week="fri",
            price_override=Decimal("55.00"),
        )
        DynamicPricingRule.objects.create(
            tier_code="1 BGO",
            is_active=False,
            rule_type=DynamicPricingRule.RuleType.SPECIAL,
            start_date=date(2026, 1, 1),
            price_override=Decimal("35.00"),
        )
        engine = DynamicPricingEngine()
        summary = engine.get_seasonal_summary("1 BGO")
        self.assertEqual(len(summary), 2)  # Only active rules returned
