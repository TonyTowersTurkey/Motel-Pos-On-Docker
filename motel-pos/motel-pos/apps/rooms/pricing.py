"""Dynamic pricing engine for Yess Motel POS.

Supports multi-rate pricing by season and day-of-week on top of base
PricingTier values. Resolution order:
  1. Exact date match (special override, highest priority)
  2. Day-of-week match within an active seasonal window
  3. Base tier price_per_night (fallback)

Usage:
    from apps.rooms.pricing import DynamicPricingEngine
    engine = DynamicPricingEngine()
    price = engine.resolve_price("1 BGO", date(2026, 7, 4))  # $55.00
"""

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Q
from apps.rooms.models import DynamicPricingRule, PricingTier


class DynamicPricingEngine:
    """Resolves effective price per night for a given tier + date."""

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def resolve_price(self, tier_code: str, target_date: date) -> Decimal:
        """Return the effective price for *tier_code* on *target_date*.

        Resolution order:
          1. Base tier ``price_per_night``
          2. Active DynamicPricingRule with highest priority that matches
        """
        base = self._get_base_price(tier_code)

        active_rules = self._get_active_rules_for_date(tier_code, target_date)
        if not active_rules:
            return base

        # Pick the rule with the highest priority (most specific wins by design)
        winner = max(active_rules, key=lambda r: r.priority)  # type: ignore[arg-type]
        return Decimal(str(winner.price_override))

    def resolve_price_for_room(self, room_id: str, target_date: date) -> Decimal:
        """Resolve effective price for a specific room on *target_date*.

        Looks up the room's pricing_tier_code and delegates to resolve_price.
        """
        from apps.rooms.models import Room

        try:
            room = Room.objects.get(room_id=room_id)  # type: ignore[attr-defined]
        except Room.DoesNotExist:  # type: ignore[attr-defined]
            return self._get_base_price("1 BGO")
        return self.resolve_price(room.pricing_tier_code or "1 BGO", target_date)

    def get_seasonal_summary(self, tier_code: str) -> list[dict[str, Any]]:
        """Return all active rules for a tier, sorted by start date."""
        rules = DynamicPricingRule.objects.filter(  # type: ignore[attr-defined]
            Q(tier_code=tier_code, is_active=True, start_date__isnull=False)
        ).order_by("start_date")
        return [
            {
                "id": r.id,
                "name": r.name or r.rule_type,
                "rule_type": r.rule_type,
                "tier_code": r.tier_code,
                "start_date": r.start_date.isoformat() if r.start_date else None,  # type: ignore[union-attr]
                "end_date": r.end_date.isoformat() if r.end_date else None,  # type: ignore[union-attr]
                "day_of_week": r.day_of_week,
                "price_override": float(r.price_override),
                "description": r.description,
                "priority": r.priority,
            }
            for r in rules
        ]

    def is_date_in_season(self, tier_code: str, target_date: date) -> bool:
        """Check if any active seasonal rule covers *target_date* for *tier_code*."""
        return (
            DynamicPricingRule.objects.filter(  # type: ignore[attr-defined]
                Q(tier_code=tier_code, is_active=True, start_date__isnull=False)
            )
            .extra(where=[f"start_date <= '{target_date}'"])
            .exists()
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get_base_price(self, tier_code: str) -> Decimal:
        """Return base price_per_night for *tier_code*, or 40.00 as default."""
        try:
            tier = PricingTier.objects.get(code=tier_code, active=True)  # type: ignore[attr-defined]
            return Decimal(str(tier.price_per_night))
        except PricingTier.DoesNotExist:  # type: ignore[attr-defined]
            return Decimal("40.00")

    def _get_active_rules_for_date(
        self, tier_code: str, target_date: date
    ) -> list[DynamicPricingRule]:
        """Return all active rules matching *tier_code* on *target_date*.

        A rule matches if:
          - rule_type == SPECIAL and start_date <= target_date <= end_date
          - rule_type == SEASONAL and start_date <= target_date (end is optional)
          - day_of_week matches Python weekday of target_date AND date is within the window
        """
        from apps.rooms.models import DayOfWeek

        dow_map: dict[int, str] = {
            0: "mon", 1: "tue", 2: "wed", 3: "thu",
            4: "fri", 5: "sat", 6: "sun",
        }
        target_dow = dow_map.get(target_date.weekday(), "")

        base_filter = Q(
            tier_code=tier_code,
            is_active=True,
            start_date__isnull=False,
        )

        # Collect matching rule IDs by type
        special_rules = DynamicPricingRule.objects.filter(  # type: ignore[attr-defined]
            base_filter &
            Q(rule_type=DynamicPricingRule.RuleType.SPECIAL) &
            Q(start_date__lte=target_date)
        ).extra(where=["end_date IS NULL OR end_date >= %s"], params=[target_date])

        seasonal_all_rules = DynamicPricingRule.objects.filter(  # type: ignore[attr-defined]
            base_filter &
            Q(rule_type=DynamicPricingRule.RuleType.SEASONAL) &
            Q(start_date__lte=target_date)
        ).extra(where=["end_date IS NULL OR end_date >= %s"], params=[target_date])

        doall_rules = DynamicPricingRule.objects.filter(  # type: ignore[attr-defined]
            base_filter &
            Q(rule_type=DynamicPricingRule.RuleType.DAY_OF_WEEK) &
            Q(start_date__lte=target_date)
        ).extra(where=["end_date IS NULL OR end_date >= %s"], params=[target_date])

        matches: list[DynamicPricingRule] = list(special_rules)

        # Seasonal rules apply if they cover the date and either have no DoW restriction
        # or match the specific day
        for rule in seasonal_all_rules:
            if not rule.day_of_week:
                matches.append(rule)
            elif rule.day_of_week.lower() == target_dow:
                matches.append(rule)

        # Day-of-week rules only apply if they match the specific weekday
        for rule in doall_rules:
            if rule.day_of_week and rule.day_of_week.lower() == target_dow:
                matches.append(rule)

        return matches


# Singleton
dynamic_pricing_engine = DynamicPricingEngine()
