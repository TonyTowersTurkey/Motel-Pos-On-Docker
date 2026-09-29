"""Serializers for revenue models."""

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.revenue.models import OccupancySession, ShiftLedger


class OccupancySessionSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for occupancy session (guest stay) records."""

    class Meta:
        model = OccupancySession
        fields = [
            "id",
            "room_id",
            "guest_name",
            "phone",
            "license_plate",
            "check_in",
            "check_out",
            "room_type_code",
            "price_per_night",
            "amenities_charges",
            "estimated_revenue",
            "actual_revenue",
            "source",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]

    def validate_license_plate(self, value: str) -> str:
        """Return plate characters in their canonical display casing."""
        return value.upper()


class ShiftLedgerSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """Serializer for shift ledger entries."""

    class Meta:
        model = ShiftLedger
        fields = [
            "id",
            "date",
            "shift_number",
            "tier_1_bgo_count",
            "tier_2_y0_dndein_count",
            "tier_3_boo_count",
            "tier_4_buys_count",
            "tier_5_s0_luxury_count",
            "tier_1_bgo_revenue",
            "tier_2_y0_dndein_revenue",
            "tier_3_boo_revenue",
            "tier_4_buys_revenue",
            "tier_5_s0_luxury_revenue",
            "subtotal",
            "barra_amount",
            "ath_subtotal",
            "logged_by",
            "verified_by",
            "notes",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Ensure totals are consistent on save."""
        tier_revenues = [
            attrs.get("tier_1_bgo_revenue", Decimal("0.00")),
            attrs.get("tier_2_y0_dndein_revenue", Decimal("0.00")),
            attrs.get("tier_3_boo_revenue", Decimal("0.00")),
            attrs.get("tier_4_buys_revenue", Decimal("0.00")),
            attrs.get("tier_5_s0_luxury_revenue", Decimal("0.00")),
        ]
        attrs["subtotal"] = sum(r for r in tier_revenues if r is not None)  # type: ignore[arg-type]
        return attrs
