"""Comprehensive tests for user model using factory-boy fixtures."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.tests.factories import UserFactory

User = get_user_model()


class UserModelTest(TestCase):
    """Custom User model tests with factory-boy fixtures."""

    def test_create_user_via_factory(self) -> None:
        user = UserFactory()
        self.assertIsInstance(user, User)
        self.assertTrue(user.check_password("change_me"))  # default password

    def test_create_user_with_custom_password(self) -> None:
        user = UserFactory(password="custom_secret")
        self.assertTrue(user.check_password("custom_secret"))
        self.assertFalse(user.check_password("change_me"))

    def test_create_user_minimal(self) -> None:
        user = User.objects.create_user(username="minimal", password="test123")
        self.assertEqual(user.first_name, "")
        self.assertEqual(user.last_name, "")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_user_password_hashing(self) -> None:
        user = UserFactory()
        # Verify password is hashed (not stored as plaintext)
        raw_password = "change_me"
        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.check_password(raw_password))

    def test_user_email_uniqueness(self) -> None:
        User.objects.create_user(username="u1", email="u1@motel.com", password="p")
        with self.assertRaises(Exception):
            User.objects.create_user(username="u2", email="u1@motel.com", password="p")

    def test_user_role_field(self) -> None:
        user = User.objects.create_user(username="r1", password="p", role="admin")
        self.assertEqual(user.role, "admin")

    def test_get_role_display(self) -> None:
        user = User.objects.create_user(username="r2", password="p", role="cashier")
        self.assertIsNotNone(user.get_role_display())


class UserModelManagerTest(TestCase):
    """User manager and query tests."""

    def test_create_superuser(self) -> None:
        admin = User.objects.create_superuser(
            username="admin1", email="admin@motel.com", password="admin123"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)


class UserModelAuthBackendTest(TestCase):
    """Test MotelAuthBackend authentication."""

    def test_auth_backend_creates_user(self) -> None:
        from apps.users.backends import MotelAuthBackend

        User.objects.create_user(username="cashier", password="change_me")
        backend = MotelAuthBackend()
        user = backend.authenticate(username="cashier", password="change_me")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "cashier")

    def test_auth_backend_case_insensitive(self) -> None:
        from apps.users.backends import MotelAuthBackend

        backend = MotelAuthBackend()
        User.objects.create_user(username="testuser", password="pass123")
        user_upper = backend.authenticate(username="TESTUSER", password="pass123")
        self.assertIsNotNone(user_upper)
        self.assertEqual(user_upper.username, "testuser")

    def test_auth_backend_invalid_password(self) -> None:
        from apps.users.backends import MotelAuthBackend

        backend = MotelAuthBackend()
        User.objects.create_user(username="badpwd", password="correct")
        user = backend.authenticate(username="badpwd", password="wrong")
        self.assertIsNone(user)

    def test_auth_backend_nonexistent_user(self) -> None:
        from apps.users.backends import MotelAuthBackend

        backend = MotelAuthBackend()
        user = backend.authenticate(username="nonexistent", password="x")
        self.assertIsNone(user)

    def test_auth_backend_rejects_inactive_user(self) -> None:
        from apps.users.backends import MotelAuthBackend

        User.objects.create_user(
            username="inactive_user",
            email="inactive@test.example",
            password="pass123",
            is_active=False,
        )

        user = MotelAuthBackend().authenticate(
            username="inactive_user", password="pass123"
        )

        self.assertIsNone(user)
