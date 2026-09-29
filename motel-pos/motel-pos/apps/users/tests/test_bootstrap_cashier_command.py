"""Tests for the cashier bootstrap management command."""

import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class BootstrapCashierCommandTest(TestCase):
    """Verify the cashier bootstrap path is safe and usable."""

    def test_command_creates_cashier_and_is_idempotent(self) -> None:
        call_command(
            "bootstrap_cashier",
            username="cashier",
            password="cashier_pw",
            stdout=StringIO(),
        )
        call_command(
            "bootstrap_cashier",
            username="cashier",
            password="cashier_pw",
            stdout=StringIO(),
        )

        users = User.objects.filter(username="cashier")
        self.assertEqual(users.count(), 1)
        cashier = users.get()
        self.assertEqual(cashier.role, "cashier")
        self.assertTrue(cashier.is_active)
        self.assertTrue(cashier.check_password("cashier_pw"))

    def test_command_requires_explicit_password_when_env_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesMessage(
                CommandError,
                "Cashier password must be provided via --password or MOTEL_CASHIER_PASSWORD.",
            ):
                call_command("bootstrap_cashier", username="cashier", stdout=StringIO())

    def test_existing_password_is_only_reset_when_requested(self) -> None:
        User.objects.create_user(
            username='cashier',
            password='old_password',
            email='old_cashier@example.test',
            role='manager',
        )

        call_command(
            'bootstrap_cashier',
            username='cashier',
            stdout=StringIO(),
        )
        cashier = User.objects.get(username='cashier')
        self.assertTrue(cashier.check_password('old_password'))
        self.assertEqual(cashier.role, 'cashier')
        self.assertEqual(cashier.email, 'old_cashier@example.test')

        call_command(
            'bootstrap_cashier',
            username='cashier',
            password='new_password',
            stdout=StringIO(),
        )
        cashier.refresh_from_db()
        self.assertTrue(cashier.check_password('old_password'))
        self.assertEqual(cashier.role, 'cashier')
        self.assertEqual(cashier.email, 'old_cashier@example.test')

        call_command(
            'bootstrap_cashier',
            username='cashier',
            password='new_password',
            email='new_cashier@example.test',
            reset_password=True,
            stdout=StringIO(),
        )
        cashier.refresh_from_db()
        self.assertTrue(cashier.check_password('new_password'))
        self.assertEqual(cashier.email, 'new_cashier@example.test')

    def test_existing_cashier_loses_elevated_flags_on_rerun(self) -> None:
        User.objects.create_user(
            username="cashier",
            password="old_password",
            email="cashier@example.test",
            role="cashier",
            is_staff=True,
            is_superuser=True,
        )

        call_command(
            "bootstrap_cashier",
            username="cashier",
            password="new_password",
            stdout=StringIO(),
        )

        cashier = User.objects.get(username="cashier")
        self.assertTrue(cashier.check_password("old_password"))
        self.assertFalse(cashier.is_staff)
        self.assertFalse(cashier.is_superuser)


    def test_bootstrapped_cashier_can_get_jwt_tokens(self) -> None:
        call_command(
            "bootstrap_cashier",
            username="cashier",
            password="cashier_pw",
            stdout=StringIO(),
        )

        response = APIClient().post(
            "/api/auth/login/",
            {"username": "cashier", "password": "cashier_pw"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'cashier')
        self.assertEqual(response.data['user']['role'], 'cashier')


class BootstrapMotelUsersCommandTest(TestCase):
    """Verify the role bootstrap path is repeatable and usable."""

    def test_command_creates_standard_roles_and_is_idempotent(self) -> None:
        call_command(
            "bootstrap_motel_users",
            cashier_username="cashier",
            cashier_password="cashier_pw",
            cashier_email="cashier@example.test",
            manager_username="manager",
            manager_password="manager_pw",
            manager_email="manager@example.test",
            admin_username="admin",
            admin_password="admin_pw",
            admin_email="admin@example.test",
            stdout=StringIO(),
        )
        call_command(
            "bootstrap_motel_users",
            cashier_username="cashier",
            cashier_password="cashier_pw",
            cashier_email="cashier@example.test",
            manager_username="manager",
            manager_password="manager_pw",
            manager_email="manager@example.test",
            admin_username="admin",
            admin_password="admin_pw",
            admin_email="admin@example.test",
            stdout=StringIO(),
        )

        self.assertEqual(User.objects.count(), 3)
        cashier = User.objects.get(username="cashier")
        manager = User.objects.get(username="manager")
        admin = User.objects.get(username="admin")

        self.assertEqual(cashier.role, "cashier")
        self.assertEqual(manager.role, "manager")
        self.assertEqual(admin.role, "admin")
        self.assertFalse(cashier.is_staff)
        self.assertFalse(manager.is_staff)
        self.assertTrue(admin.is_staff)
        self.assertTrue(cashier.check_password("cashier_pw"))
        self.assertTrue(manager.check_password("manager_pw"))
        self.assertTrue(admin.check_password("admin_pw"))

    def test_existing_passwords_are_only_reset_when_requested(self) -> None:
        User.objects.create_user(
            username="cashier",
            password="old_cashier_pw",
            email="old_cashier@example.test",
            role="manager",
        )
        User.objects.create_user(
            username="manager",
            password="old_manager_pw",
            email="old_manager@example.test",
            role="cashier",
        )
        User.objects.create_user(
            username="admin",
            password="old_admin_pw",
            email="old_admin@example.test",
            role="cashier",
        )

        call_command(
            "bootstrap_motel_users",
            cashier_username="cashier",
            cashier_password="new_cashier_pw",
            manager_username="manager",
            manager_password="new_manager_pw",
            admin_username="admin",
            admin_password="new_admin_pw",
            stdout=StringIO(),
        )

        cashier = User.objects.get(username="cashier")
        manager = User.objects.get(username="manager")
        admin = User.objects.get(username="admin")
        self.assertTrue(cashier.check_password("old_cashier_pw"))
        self.assertTrue(manager.check_password("old_manager_pw"))
        self.assertTrue(admin.check_password("old_admin_pw"))
        self.assertEqual(cashier.role, "cashier")
        self.assertEqual(manager.role, "manager")
        self.assertEqual(admin.role, "admin")
        self.assertEqual(cashier.email, "old_cashier@example.test")
        self.assertEqual(manager.email, "old_manager@example.test")
        self.assertEqual(admin.email, "old_admin@example.test")
        self.assertTrue(admin.is_staff)

        call_command(
            "bootstrap_motel_users",
            cashier_username="cashier",
            cashier_password="new_cashier_pw",
            cashier_email="new_cashier@example.test",
            manager_username="manager",
            manager_password="new_manager_pw",
            manager_email="new_manager@example.test",
            admin_username="admin",
            admin_password="new_admin_pw",
            admin_email="new_admin@example.test",
            reset_password=True,
            stdout=StringIO(),
        )

        cashier.refresh_from_db()
        manager.refresh_from_db()
        admin.refresh_from_db()
        self.assertTrue(cashier.check_password("new_cashier_pw"))
        self.assertTrue(manager.check_password("new_manager_pw"))
        self.assertTrue(admin.check_password("new_admin_pw"))
        self.assertEqual(cashier.email, "new_cashier@example.test")
        self.assertEqual(manager.email, "new_manager@example.test")
        self.assertEqual(admin.email, "new_admin@example.test")

    def test_bootstrapped_roles_can_get_jwt_tokens(self) -> None:
        call_command(
            "bootstrap_motel_users",
            cashier_username="cashier",
            cashier_password="cashier_pw",
            cashier_email="cashier@example.test",
            manager_username="manager",
            manager_password="manager_pw",
            manager_email="manager@example.test",
            admin_username="admin",
            admin_password="admin_pw",
            admin_email="admin@example.test",
            stdout=StringIO(),
        )

        for username, password, role in (
            ("cashier", "cashier_pw", "cashier"),
            ("manager", "manager_pw", "manager"),
            ("admin", "admin_pw", "admin"),
        ):
            response = APIClient().post(
                "/api/auth/login/",
                {"username": username, "password": password},
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("access", response.data)
            self.assertEqual(response.data["user"]["role"], role)
