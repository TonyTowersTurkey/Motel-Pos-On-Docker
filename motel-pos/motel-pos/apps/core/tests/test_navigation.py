"""Role and responsive behavior for the shared POS navigation shell."""

import re

from django.test import TestCase

from apps.users.tests.factories import UserFactory


def sidebar_html(response) -> str:  # type: ignore[no-untyped-def]
    """Extract the shared navigation element from rendered HTML."""
    match = re.search(
        r'<aside class="pos-sidebar".*?</aside>',
        response.content.decode("utf-8"),
        flags=re.DOTALL,
    )
    return match.group(0) if match else ""


class PosNavigationTest(TestCase):
    def test_cashier_only_sees_cashier_navigation(self) -> None:
        cashier = UserFactory(username="sidebar_cashier", role="cashier")
        self.client.force_login(cashier)

        response = self.client.get("/cashier/")
        sidebar = sidebar_html(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cashier POS", sidebar)
        self.assertNotIn("Manager Dashboard", sidebar)
        self.assertNotIn("Room Configuration", sidebar)
        self.assertNotIn(">Vehicles<", sidebar)
        self.assertNotIn("Maintenance", sidebar)
        self.assertNotIn("Administration", sidebar)

    def test_manager_sees_cashier_and_manager_navigation(self) -> None:
        manager = UserFactory(username="sidebar_manager", role="manager")
        self.client.force_login(manager)

        response = self.client.get("/manager/")
        sidebar = sidebar_html(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cashier POS", sidebar)
        self.assertIn("Manager Dashboard", sidebar)
        self.assertIn("Room Configuration", sidebar)
        self.assertIn("Vehicles", sidebar)
        self.assertIn("Maintenance", sidebar)
        self.assertNotIn("Administration", sidebar)

    def test_admin_sees_admin_navigation(self) -> None:
        admin = UserFactory(
            username="sidebar_admin", role="admin", is_staff=True, is_superuser=True
        )
        self.client.force_login(admin)

        sidebar = sidebar_html(self.client.get("/manager/"))

        self.assertIn("Administration", sidebar)

    def test_manager_can_open_cashier_view(self) -> None:
        manager = UserFactory(username="manager_cashier_access", role="manager")
        self.client.force_login(manager)

        self.assertEqual(self.client.get("/cashier/").status_code, 200)

    def test_shell_contains_mobile_drawer_controls(self) -> None:
        cashier = UserFactory(username="sidebar_mobile", role="cashier")
        self.client.force_login(cashier)

        response = self.client.get("/cashier/")

        self.assertContains(response, "data-pos-nav-open")
        self.assertContains(response, "data-pos-nav-close")
        self.assertContains(response, "pos-sidebar-overlay")
        self.assertContains(response, "@media (max-width:1024px)")
