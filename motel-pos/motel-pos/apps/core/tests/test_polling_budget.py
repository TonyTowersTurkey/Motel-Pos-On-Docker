"""Ensure dashboards use one server-push stream instead of API polling."""

from django.test import TestCase

from apps.users.tests.factories import UserFactory


class DashboardSSETest(TestCase):
    def test_cashier_uses_server_sent_updates_without_polling(self) -> None:
        cashier = UserFactory(username="polling_cashier", role="cashier")
        self.client.force_login(cashier)

        response = self.client.get("/cashier/")

        self.assertContains(response, "new EventSource('/api/events/stream/')")
        self.assertContains(response, "if (roomsLoading) return;")
        self.assertContains(response, "'motel:dashboard-update'")
        self.assertNotContains(response, "setInterval(loadRooms")

    def test_manager_uses_server_sent_updates_without_polling(self) -> None:
        manager = UserFactory(username="polling_manager", role="manager")
        self.client.force_login(manager)

        response = self.client.get("/manager/")

        self.assertContains(response, "new EventSource('/api/events/stream/')")
        self.assertContains(response, "if (loadAllPromise) return loadAllPromise;")
        self.assertContains(response, "'motel:dashboard-update'")
        self.assertNotContains(response, "setInterval(() => { loadAll()")
