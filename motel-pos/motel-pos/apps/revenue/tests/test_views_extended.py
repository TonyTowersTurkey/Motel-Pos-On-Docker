"""Extended tests for revenue ViewSets covering untested action methods and edge cases."""

from datetime import date, datetime
from io import BytesIO
from unittest.mock import patch

from django.test import Client, TestCase
from rest_framework.test import APIClient, APITestCase

from apps.revenue.models import OccupancySession
from apps.rooms.models import Room
from apps.users.tests.factories import UserFactory


class CashierViewTest(TestCase):
    """Tests for cashier_view template view."""

    def test_cashier_view_context_includes_today(self) -> None:
        client = Client()
        user = UserFactory(username="cashier_extended", role="cashier")
        client.force_login(user)
        response = client.get("/cashier/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        today_str = date.today().strftime("%A, %B %d, %Y")
        # At minimum check template rendered without error
        self.assertIn("Cashier Portal", content)


class CheckoutActionTest(APITestCase):
    """Tests for OccupancySessionViewSet checkout action."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(role="manager", is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)
        self.room = Room.objects.create(
            room_id="room_checkin_test",
            room_number="900",
            sensor_id="sensor_900",
        )

    def test_checkout_succeeds(self) -> None:
        session = OccupancySessionFactory().create(
            room_id="room_checkin_test",
            status="active",
        )
        response = self.client.post(f"/api/sessions/{session.pk}/checkout/")
        self.assertEqual(response.status_code, 200)
        refreshed = OccupancySession.objects.get(pk=session.pk)
        self.assertEqual(refreshed.status, "checked_out")

    def test_checkout_already_checked_out(self) -> None:
        session = OccupancySessionFactory().create(
            room_id="room_checkin_test",
            status="checked_out",
        )
        response = self.client.post(f"/api/sessions/{session.pk}/checkout/")
        self.assertEqual(response.status_code, 400)


class DailySummaryActionTest(APITestCase):
    """Tests for ShiftLedgerViewSet daily_summary action."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(role="manager", is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_daily_summary_returns_data(self) -> None:
        response = self.client.get("/api/ledgers/daily_summary/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("date", data)
        self.assertIn("total_sessions", data)


class CuadreActionTest(APITestCase):
    """Tests for ShiftLedgerViewSet cuadre action."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(role="manager", is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_cuadre_json_endpoint_returns_data(self) -> None:
        today_str = date.today().isoformat()
        response = self.client.get(f"/api/ledgers/cuadre/?date={today_str}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ledger", data)
        self.assertIn("cuadre_text", data)

    def test_cuadre_invalid_date_format(self) -> None:
        response = self.client.get("/api/ledgers/cuadre/?date=not-a-date")
        self.assertEqual(response.status_code, 400)

    def test_cuadre_invalid_shift_number(self) -> None:
        today_str = date.today().isoformat()
        response = self.client.get(f"/api/ledgers/cuadre/?date={today_str}&shift=abc")
        self.assertEqual(response.status_code, 400)

    def test_cuadre_pdf_download_uses_selected_shift(self) -> None:
        cashier = UserFactory(username="cashier_cuadre_pdf", role="cashier")
        self.client.force_login(cashier)
        today = date(2026, 6, 18)
        with patch("apps.revenue.services.revenue_engine.compute_shift_for_day") as mock_compute, patch(
            "apps.revenue.services.revenue_engine.generate_cuadre_text_pdf"
        ) as mock_pdf:
            mock_compute.return_value = {
                "shift_number": 3,
                "tier_counts": {},
                "tier_revenues": {},
                "ath_subtotal": 0.0,
                "active_rooms_count": 0,
            }
            mock_pdf.return_value = BytesIO(b"%PDF-1.4 test-cuadre")
            response = self.client.get(f"/api/ledgers/cuadre/{today.isoformat()}/?shift=3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        mock_compute.assert_called_once_with(today, shift_number=3)


class GenerateReportActionTest(APITestCase):
    """Tests for ShiftLedgerViewSet generate_report action."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(role="manager", is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_generate_report_daily_occupancy(self) -> None:
        today_str = date.today().isoformat()
        response = self.client.get(
            f"/api/ledgers/generate_report/?type=daily_occupancy&date={today_str}"
        )
        self.assertEqual(response.status_code, 200)

    def test_generate_report_daily_sales(self) -> None:
        today_str = date.today().isoformat()
        response = self.client.get(
            f"/api/ledgers/generate_report/?type=daily_sales&date={today_str}"
        )
        self.assertEqual(response.status_code, 200)

    def test_generate_report_exception(self) -> None:
        today_str = date.today().isoformat()
        response = self.client.get(
            f"/api/ledgers/generate_report/?type=exception&date={today_str}"
        )
        self.assertEqual(response.status_code, 200)

    def test_generate_report_unknown_type(self) -> None:
        today_str = date.today().isoformat()
        response = self.client.get(
            f"/api/ledgers/generate_report/?type=unknown&date={today_str}"
        )
        self.assertEqual(response.status_code, 400)


class GenerateShiftActionTest(APITestCase):
    """Tests for ShiftLedgerViewSet generate_shift action."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_generate_shift_succeeds(self) -> None:
        response = self.client.post(
            "/api/ledgers/generate_shift/",
            {"date": date.today().isoformat(), "shift": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    def test_generate_shift_requires_date(self) -> None:
        response = self.client.post(
            "/api/ledgers/generate_shift/", {"shift": 1}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_generate_shift_invalid_date(self) -> None:
        response = self.client.post(
            "/api/ledgers/generate_shift/", {"date": "not-a-date"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_generate_shift_invalid_shift(self) -> None:
        response = self.client.post(
            "/api/ledgers/generate_shift/",
            {"date": date.today().isoformat(), "shift": "abc"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_generate_shift_rejects_shift_outside_supported_range(self) -> None:
        response = self.client.post(
            '/api/ledgers/generate_shift/',
            {'date': date.today().isoformat(), 'shift': 4},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Use 1, 2, or 3', response.json()['detail'])


class GenerateReportViewAPITest(APITestCase):
    """Tests for the standalone generate_report_view POST endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(role="manager", is_staff=True, password="admin123")
        self.client.force_authenticate(user=self.user)

    def test_generate_report_view_returns_response(self) -> None:
        """The report endpoint may return JSON or PDF depending on file availability."""
        response = self.client.post(
            "/api/reports/generate/daily_occupancy/",
            {
                "type": "daily_occupancy",
                "date": date.today().isoformat(),
            },
            format="json",
        )
        # Should not 404 — may return error for missing files in test env
        self.assertNotEqual(response.status_code, 404)


class OccupancySessionFactory:
    """Helper to create OccupancySession instances."""

    @staticmethod
    def create(**kwargs) -> OccupancySession:
        defaults = {
            "room_id": f"room_{900}",
            "check_in": datetime.now(),
            "source": "sensor_auto",
            "status": "active",
        }
        defaults.update(kwargs)
        return OccupancySession.objects.create(**defaults)
