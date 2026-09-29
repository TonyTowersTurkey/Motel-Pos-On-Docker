from django.test import TestCase

from apps.users.tests.factories import UserFactory


class MaintenanceFrontendViewTests(TestCase):
    def setUp(self):
        self.manager = UserFactory(username="maintenance_page_manager", role="manager")
        self.client.force_login(self.manager)

    def test_maintenance_pages_render(self):
        pages = [
            ('/maintenance/', 'Maintenance Dashboard'),
            ('/maintenance/work-to-do/', 'Work To Be Done'),
            ('/maintenance/work-orders/new/', 'New Work Order'),
            ('/maintenance/planned/', 'Planned Maintenance'),
            ('/maintenance/planned/calendar/', 'PM Calendar Preview'),
            ('/maintenance/rooms/', 'Maintenance Rooms'),
        ]
        for path, marker in pages:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, marker)

    def test_dashboard_uses_mock_data(self):
        response = self.client.get('/maintenance/')
        self.assertContains(response, 'Broken toilet')
        self.assertContains(response, 'Open Work Orders')
        self.assertContains(response, 'Add Work Order')
        self.assertContains(response, 'openNewWorkOrderDialog')
        self.assertContains(response, 'submitNewWorkOrder')

    def test_planned_uses_mock_data(self):
        response = self.client.get('/maintenance/planned/')
        self.assertContains(response, 'Clean Air Filters')
        self.assertContains(response, 'Yearly')

    def test_dialog_payload_is_present(self):
        response = self.client.get('/maintenance/')
        self.assertContains(response, 'workOrderDialog')
        self.assertContains(response, 'newWorkOrderDialog')
        self.assertContains(response, 'openNewWorkOrderDialog')
        self.assertContains(response, 'submitNewWorkOrder')
        self.assertContains(response, 'Toilet cracked and leaking at base')

    def test_ad_hoc_page_uses_shared_dialog(self):
        response = self.client.get('/maintenance/work-orders/new/')
        self.assertContains(response, 'openNewWorkOrderDialog')
        self.assertContains(response, 'submitNewWorkOrder')
        self.assertContains(response, 'same modal')

    def test_maintenance_requires_login_and_manager_role(self):
        self.client.logout()
        anonymous = self.client.get('/maintenance/')
        self.assertEqual(anonymous.status_code, 302)
        self.assertTrue(anonymous['Location'].startswith('/login/'))

        cashier = UserFactory(username="maintenance_page_cashier", role="cashier")
        self.client.force_login(cashier)
        self.assertEqual(self.client.get('/maintenance/').status_code, 403)
