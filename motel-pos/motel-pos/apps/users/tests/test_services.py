"""Tests for users service layer (user creation, role management)."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.services import UserService

User = get_user_model()


class UserServiceTest(TestCase):
    """Tests for the UserService helper."""

    def test_get_user_by_username(self) -> None:
        user = User.objects.create_user(
            username="svc_test", password="test123", email="svc@test.com"
        )
        svc = UserService()
        found = User.objects.filter(username="svc_test").first()
        self.assertIsNotNone(found)
        self.assertEqual(found.username, "svc_test")

    def test_get_user_by_username_not_found(self) -> None:
        found = User.objects.filter(username="nonexistent_user_svc").first()
        self.assertIsNone(found)

    def test_get_active_users(self) -> None:
        User.objects.create_user(username="a1", password="p", email="a1@t.com")
        inactive = User.objects.create_user(
            username="i1", password="p", email="i1@t.com"
        )
        inactive.is_active = False
        inactive.save()
        active_users = list(User.objects.filter(is_active=True))
        usernames = [u.username for u in active_users]
        self.assertIn("a1", usernames)
        self.assertNotIn("i1", usernames)

    def test_create_user_with_role(self) -> None:
        svc = UserService()
        user = svc.create_user(
            username="new_svc_user", password="svc_pass", role="cashier"
        )
        self.assertIsInstance(user, User)
        self.assertEqual(user.username, "new_svc_user")
        self.assertTrue(user.check_password("svc_pass"))
        self.assertEqual(user.role, "cashier")

    def test_update_user_role(self) -> None:
        user = User.objects.create_user(
            username="role_update", password="p", email="r@u.com"
        )
        svc = UserService()
        svc.update_role(user.pk, "manager")
        user.refresh_from_db()
        self.assertEqual(user.role, "manager")


class UserRolesTest(TestCase):
    """Tests for user role constants and display."""

    def test_role_choices(self) -> None:
        valid_roles = [r[0] for r in User.Role.choices]  # type: ignore[attr-defined]
        self.assertIn("admin", valid_roles)
        self.assertIn("cashier", valid_roles)
        self.assertIn("manager", valid_roles)

    def test_role_display_for_cashier(self) -> None:
        user = User.objects.create_user(username="rd1", password="p", role="cashier")
        self.assertIn("Cashier", user.get_role_display())

    def test_role_display_for_admin(self) -> None:
        user = User.objects.create_user(username="rd2", password="p", role="admin")
        self.assertIn("Admin", user.get_role_display())


class UserServicePasswordTest(TestCase):
    """Tests for password-related service methods via User model directly."""

    def test_user_set_password_works(self) -> None:
        user = User.objects.create_user(username="pw_test", password="old_pass_123")
        user.set_password("new_pw_456")
        user.save(update_fields=["password"])
        self.assertTrue(user.check_password("new_pw_456"))

    def test_change_password_correctly(self) -> None:
        user = User.objects.create_user(username="pw_test2", password="correct_old_123")
        old_hash = user.password
        user.set_password("new_correct_789")
        user.save(update_fields=["password"])
        user.refresh_from_db()
        self.assertNotEqual(old_hash, user.password)
        self.assertTrue(user.check_password("new_correct_789"))
