"""Tests for user serializers."""

from django.test import TestCase

from apps.users.serializers import (
    LoginSerializer,
    PasswordChangeSerializer,
    UserSerializer,
)
from apps.users.tests.factories import UserFactory


class UserSerializerTest(TestCase):
    """Tests for UserSerializer."""

    def test_serializer_roundtrip(self) -> None:
        user = UserFactory()
        data = UserSerializer(user).data
        self.assertEqual(data["username"], user.username)
        self.assertIn("role", data)
        self.assertTrue(data["capabilities"]["cashier_access"])
        self.assertFalse(data["capabilities"]["manager_access"])

    def test_capabilities_follow_permissions_not_role_label(self) -> None:
        user = UserFactory(role="cashier")
        manager = UserFactory(role="manager")
        user.groups.set(manager.groups.all())
        user = type(user).objects.get(pk=user.pk)

        capabilities = UserSerializer(user).data["capabilities"]

        self.assertTrue(capabilities["manager_access"])
        self.assertTrue(capabilities["generate_reports"])

    def test_create_user_serializer(self) -> None:
        data = {
            "username": "newuser",
            "password": "secure_pass_123",
            "email": "newuser@motel.com",
            "first_name": "New",
            "last_name": "User",
        }
        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertTrue(user.check_password("secure_pass_123"))

    def test_create_user_no_raw_password(self) -> None:
        data = {"username": "n", "email": "n@m.com"}
        serializer = UserSerializer(data=data)
        # password field is required in create
        self.assertFalse(serializer.is_valid())


class LoginSerializerTest(TestCase):
    """Tests for LoginSerializer."""

    def test_login_serializer_valid(self) -> None:
        data = {"username": "testuser", "password": "password123"}
        serializer = LoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_login_serializer_empty_fields(self) -> None:
        data = {"username": "", "password": ""}
        serializer = LoginSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class PasswordChangeSerializerTest(TestCase):
    """Tests for PasswordChangeSerializer."""

    def setUp(self) -> None:
        self.user = UserFactory(password="old_password")

    def test_password_change_valid(self) -> None:
        # Test uses DRF's APIRequestFactory to provide proper request context
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user
        data = {
            "old_password": "old_password",
            "new_password1": "new_secure_pass",
            "new_password2": "new_secure_pass",
        }
        serializer = PasswordChangeSerializer(data=data, context={"request": request})
        self.assertTrue(serializer.is_valid())

    def test_password_change_wrong_old_password(self) -> None:
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user
        data = {
            "old_password": "wrong_password",
            "new_password1": "new_secure_pass",
            "new_password2": "new_secure_pass",
        }
        serializer = PasswordChangeSerializer(data=data, context={"request": request})
        self.assertFalse(serializer.is_valid())
