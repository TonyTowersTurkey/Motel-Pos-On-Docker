"""Tests for revenue engine services (pure logic tests, no DB needed where possible)."""

from datetime import date, datetime

from django.test import TestCase

from apps.revenue.models import ShiftLedger


class TierPriceTest(TestCase):
    """Tests for the tier_price() utility function."""

    def test_all_tier_prices(self) -> None:
        from apps.revenue.services import tier_price

        self.assertEqual(tier_price("1 BGO"), 40.0)
        self.assertEqual(tier_price("2 Y0 Dndein"), 45.0)
        self.assertEqual(tier_price("3 BOO"), 50.0)
        self.assertEqual(tier_price("4 BUYS"), 70.0)
        self.assertEqual(tier_price("9.S0"), 100.0)

    def test_unknown_tier_returns_zero(self) -> None:
        from apps.revenue.services import tier_price

        self.assertEqual(tier_price("UNKNOWN"), 0.0)


class TierKeyToColumnTest(TestCase):
    """Tests for tier_key_to_sql_column() helper."""

    def test_bgo(self) -> None:
        from apps.revenue.services import tier_key_to_sql_column

        self.assertEqual(tier_key_to_sql_column("1 BGO"), "tier_1_bgo_count")

    def test_y0(self) -> None:
        from apps.revenue.services import tier_key_to_sql_column

        self.assertEqual(
            tier_key_to_sql_column("2 Y0 Dndein"), "tier_2_y0_dndein_count"
        )

    def test_s0(self) -> None:
        from apps.revenue.services import tier_key_to_sql_column

        self.assertEqual(tier_key_to_sql_column("9.S0"), "tier_5_s0_luxury_count")

    def test_unknown_returns_none(self) -> None:
        from apps.revenue.services import tier_key_to_sql_column

        self.assertIsNone(tier_key_to_sql_column("NOPE"))


class CuadreDateFormattingTest(TestCase):
    """Tests for date formatting utilities used in Cuadre reports."""

    def test_format_cuadre_date(self) -> None:
        from apps.revenue.services import format_cuadre_date

        d = datetime(2026, 1, 5)
        result = format_cuadre_date(d)
        self.assertIn("ENERO", result)

        d = datetime(2026, 7, 20)
        result = format_cuadre_date(d)
        self.assertIn("JULIO", result)

    def test_format_shift_date(self) -> None:
        from apps.revenue.services import format_shift_date

        d = datetime(2026, 3, 15)
        result = format_shift_date(d)
        self.assertIn("MARZO", result)


class RevenueEngineCuadreTextTest(TestCase):
    """Tests for revenue engine Cuadre text generation."""

    def test_generate_cuadre_text_structure(self) -> None:
        from apps.revenue.services import revenue_engine

        today = datetime.now().date()
        text = revenue_engine.generate_cuadre_text(today, 1)
        self.assertIsInstance(text, str)
        # Should have header with Cuadre format
        self.assertIn("Cuadre", text)
        self.assertIn("TURNO 1", text)
        self.assertIn("Desglose de Depositos", text)
        self.assertIn("Subtotal", text)
        self.assertIn("ATH SUB-TOTAL", text)


class RevenueEngineSaveShiftLedgerTest(TestCase):
    """Tests for idempotent shift-ledger persistence."""

    def test_save_shift_ledger_updates_existing_row(self) -> None:
        from apps.revenue.services import revenue_engine

        day = date(2026, 6, 18)
        first_ledger = {
            "tier_counts": {
                "1 BGO": 1,
                "2 Y0 Dndein": 0,
                "3 BOO": 0,
                "4 BUYS": 0,
                "9.S0": 0,
            },
            "tier_revenues": {
                "1 BGO": 40.0,
                "2 Y0 Dndein": 0.0,
                "3 BOO": 0.0,
                "4 BUYS": 0.0,
                "9.S0": 0.0,
            },
            "subtotal": 40.0,
            "barra_amount": 0.0,
            "ath_subtotal": 40.0,
        }
        second_ledger = {
            "tier_counts": {
                "1 BGO": 2,
                "2 Y0 Dndein": 1,
                "3 BOO": 0,
                "4 BUYS": 0,
                "9.S0": 0,
            },
            "tier_revenues": {
                "1 BGO": 80.0,
                "2 Y0 Dndein": 45.0,
                "3 BOO": 0.0,
                "4 BUYS": 0.0,
                "9.S0": 0.0,
            },
            "subtotal": 125.0,
            "barra_amount": 0.0,
            "ath_subtotal": 125.0,
        }

        first_pk = revenue_engine.save_shift_ledger(day, 2, first_ledger)
        second_pk = revenue_engine.save_shift_ledger(day, 2, second_ledger)

        self.assertEqual(first_pk, second_pk)
        self.assertEqual(
            ShiftLedger.objects.filter(date=day, shift_number=2).count(), 1
        )
        ledger = ShiftLedger.objects.get(date=day, shift_number=2)
        self.assertEqual(ledger.tier_1_bgo_count, 2)
        self.assertEqual(ledger.tier_2_y0_dndein_count, 1)
        self.assertEqual(float(ledger.subtotal), 125.0)
        self.assertEqual(float(ledger.ath_subtotal), 125.0)


class ReportGeneratorTest(TestCase):
    """Tests for ReportGenerator PDF/CSV report output."""

    def test_report_generator_singleton(self) -> None:
        from apps.revenue.reports import report_generator

        self.assertIsNotNone(report_generator)
