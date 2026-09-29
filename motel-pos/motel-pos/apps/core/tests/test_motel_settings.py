"""Tests for the singleton Django Admin operational settings page."""

from django.test import TestCase

from apps.core.models import MotelSettings
from apps.users.tests.factories import UserFactory


class MotelSettingsAdminTest(TestCase):
    def test_default_settings_record_uses_pos_hands_on_mode(self) -> None:
        settings = MotelSettings.objects.get(pk=1)

        self.assertEqual(
            settings.operating_mode,
            MotelSettings.OperatingMode.POS_HANDS_ON_MODE,
        )

    def test_admin_can_select_audit_mode(self) -> None:
        admin = UserFactory(
            username="settings_admin",
            role="admin",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.post(
            "/admin/core/motelsettings/1/change/",
            {
                "operating_mode": MotelSettings.OperatingMode.AUDIT_MODE,
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        settings = MotelSettings.objects.get(pk=1)
        self.assertEqual(
            settings.operating_mode,
            MotelSettings.OperatingMode.AUDIT_MODE,
        )
        self.assertEqual(settings.updated_by, admin)

    def test_admin_settings_page_does_not_allow_add_or_delete(self) -> None:
        admin = UserFactory(
            username="settings_admin_controls",
            role="admin",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.get("/admin/core/motelsettings/1/change/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Save as new")
        self.assertNotContains(response, "Delete")
