"""Role-aware landing behavior for the POS root URL."""

from django.test import TestCase

from apps.users.tests.factories import UserFactory


class RoleLandingPageTest(TestCase):
    def test_cashier_root_redirects_to_cashier_pos(self) -> None:
        cashier = UserFactory(username="landing_cashier", role="cashier")
        self.client.force_login(cashier)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            "/cashier/",
            fetch_redirect_response=False,
        )

    def test_manager_root_redirects_to_manager_dashboard(self) -> None:
        manager = UserFactory(username="landing_manager", role="manager")
        self.client.force_login(manager)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            "/manager/",
            fetch_redirect_response=False,
        )

    def test_admin_root_redirects_to_manager_dashboard(self) -> None:
        admin = UserFactory(username="landing_admin", role="admin")
        self.client.force_login(admin)

        response = self.client.get("/")

        self.assertRedirects(
            response,
            "/manager/",
            fetch_redirect_response=False,
        )
