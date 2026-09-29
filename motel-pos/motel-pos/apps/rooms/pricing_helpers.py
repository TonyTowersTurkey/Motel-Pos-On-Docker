"""Pricing helpers for shift calculation and price details resolution."""

from datetime import date
from decimal import Decimal
from typing import Any

from apps.rooms.pricing import dynamic_pricing_engine
from apps.rooms.models import PricingTier


def resolve_price_with_details(tier_code: str, target_date: date) -> dict[str, Any]:
    """Return effective price plus the rule that was applied."""
    base = dynamic_pricing_engine._get_base_price(tier_code)  # type: ignore[attr-defined]
    active_rules = dynamic_pricing_engine._get_active_rules_for_date(tier_code, target_date)  # type: ignore[attr-defined]

    if not active_rules:
        return {
            "tier_code": tier_code,
            "date": target_date.isoformat(),
            "effective_price": float(base),
            "base_price": float(base),
            "rule_applied": None,
            "all_matching_prices": [],
        }

    winner = max(active_rules, key=lambda r: r.priority)  # type: ignore[arg-type]
    all_prices = [
        {
            "tier_code": r.tier_code,
            "name": r.name or r.rule_type,
            "price_override": float(r.price_override),
            "priority": r.priority,
        }
        for r in active_rules
    ]

    return {
        "tier_code": tier_code,
        "date": target_date.isoformat(),
        "effective_price": float(winner.price_override),  # type: ignore[union-attr]
        "base_price": float(base),
        "rule_applied": {
            "name": winner.name or winner.rule_type,  # type: ignore[union-attr]
            "rule_type": winner.rule_type,  # type: ignore[union-attr]
            "price_override": float(winner.price_override),  # type: ignore[attr-defined]
            "priority": winner.priority,  # type: ignore[attr-defined]
        },
        "all_matching_prices": all_prices,
    }


def calculate_shift_total(
    occupancy_counts: dict[str, int], target_date: date
) -> dict[str, Any]:
    """Calculate shift revenue from room occupancy counts.

    Args:
        occupancy_counts: {tier_code: count_of_occupied_rooms}
        target_date: Date to resolve prices for

    Returns:
        Dict with per-tier breakdown, subtotal, and ATH SUB-TOTAL.
    """
    tiers = PricingTier.objects.filter(active=True)
    details = []
    subtotal = Decimal("0.00")

    for tier in tiers:
        count = occupancy_counts.get(tier.code, 0)
        if count > 0:
            result = resolve_price_with_details(tier.code, target_date)
            line_total = Decimal(str(result["effective_price"])) * count
            subtotal += line_total
            details.append({
                "code": tier.code,
                "description": tier.description,
                "count": count,
                "price_per_night": result["effective_price"],
                "line_total": float(line_total),
                "rule_applied": result["rule_applied"],
            })

    barra = Decimal("0.00")
    ath_subtotal = subtotal + barra

    return {
        "date": target_date.isoformat(),
        "day_of_week": target_date.strftime("%A"),
        "per_tier": details,
        "subtotal": float(subtotal),
        "barra": float(barra),
        "ath_subtotal": float(ath_subtotal),
    }
