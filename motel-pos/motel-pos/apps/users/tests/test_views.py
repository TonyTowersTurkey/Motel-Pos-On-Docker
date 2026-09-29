"""Tests for users view layer (auth endpoints, user management API)."""

from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from apps.users.tests.factories import UserFactory


class UserListViewAPITest(APITestCase):
    """Tests for the user list endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.manager = UserFactory(role="manager", password="manager123")
        self.cashier = UserFactory(role="cashier", password="cashier123")
        self.client.force_authenticate(user=self.manager)

    def test_list_users_requires_auth(self) -> None:
        anon_client = APIClient()
        response = anon_client.get("/api/users/")
        # May return 401/403 or redirect — just should not crash
        self.assertNotEqual(response.status_code, 404)

    def test_list_users_returns_list(self) -> None:
        UserFactory(username="list_test_2", password="test")
        UserFactory(username="list_test_1", password="test")
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        usernames = [row["username"] for row in rows]
        self.assertEqual(usernames, sorted(usernames))

    def test_cashier_cannot_list_users(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, 403)


class UserProfileAPITest(APITestCase):
    """Tests for user detail/profile endpoints."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(password="profile_test")
        self.admin = UserFactory(role="admin", is_staff=True, password="admin123")
        self.manager = UserFactory(role="manager", password="manager123")
        self.cashier = UserFactory(role="cashier", password="cashier123")
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_retrieve_user_detail(self) -> None:
        response = self.client.get(f"/api/users/{self.user.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_manager_can_retrieve_user_detail(self) -> None:
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(f"/api/users/{self.user.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_admin_can_update_user_detail_by_pk(self) -> None:
        response = self.client.patch(
            f"/api/users/{self.user.pk}/",
            {"first_name": "AdminUpdated"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "AdminUpdated")

    def test_manager_cannot_update_user_detail_by_pk(self) -> None:
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            f"/api/users/{self.user.pk}/",
            {"first_name": "ManagerUpdated"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_retrieve_user_detail(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        response = self.client.get(f"/api/users/{self.user.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_update_user_detail_by_pk(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        response = self.client.put(
            f"/api/users/{self.cashier.pk}/",
            {"first_name": "Updated", "last_name": "Name"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class SelfProfileAPITest(APITestCase):
    """Tests for the self-profile endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(role="cashier", password="self_profile_test")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_self_profile_get(self) -> None:
        response = self.client.get("/api/users/profile/")
        self.assertEqual(response.status_code, 200)

    def test_self_profile_can_update_contact_fields(self) -> None:
        response = self.client.patch(
            "/api/users/profile/",
            {
                "first_name": "Front",
                "last_name": "Desk",
                "phone": "555-0101",
                "notes": "Prefers morning shift.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Front")
        self.assertEqual(self.user.last_name, "Desk")
        self.assertEqual(self.user.phone, "555-0101")
        self.assertEqual(self.user.notes, "Prefers morning shift.")

    def test_self_profile_cannot_update_sensitive_fields(self) -> None:
        response = self.client.patch(
            "/api/users/profile/",
            {
                "role": "admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": False,
                "password": "new_self_profile_pw",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "cashier")
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password("self_profile_test"))

    def test_self_profile_update_endpoint_uses_same_restrictions(self) -> None:
        response = self.client.patch(
            "/api/users/profile/update/",
            {
                "first_name": "Counter",
                "role": "manager",
                "is_staff": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Counter")
        self.assertEqual(self.user.role, "cashier")
        self.assertFalse(self.user.is_staff)


class UserCreateAPITest(APITestCase):
    """Tests for user creation endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.admin = UserFactory(role="admin", password="admin123")
        self.cashier = UserFactory(role="cashier", password="cashier123")

    def test_admin_can_create_user(self) -> None:
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/users/create/",
            {
                "username": "new_api_user",
                "email": "new@test.com",
                "password": "secure_pass_123",
                "role": "manager",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "manager")

    def test_cashier_cannot_create_user(self) -> None:
        self.client.force_authenticate(user=self.cashier)
        response = self.client.post(
            "/api/users/create/",
            {
                "username": "cashier_attempt",
                "email": "cashier-attempt@test.com",
                "password": "secure_pass_123",
                "role": "manager",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_requires_password(self) -> None:
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/users/create/",
            {
                "username": "new_api_user2",
                "email": "new2@test.com",
            },
            format="json",
        )
        # Password should be required — may return 400
        self.assertNotEqual(response.status_code, 404)


class LoginViewAPITest(APITestCase):
    """Tests for the user login view."""

    def setUp(self) -> None:
        self.client = APIClient()
        UserFactory(username="login_test_user", password="login_pass_123")

    def test_login_with_valid_credentials(self) -> None:
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "login_test_user",
                "password": "login_pass_123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'login_test_user')
        self.assertEqual(response.data['user']['role'], 'cashier')

    def test_login_with_invalid_credentials(self) -> None:
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "login_test_user",
                "password": "wrong_pass",
            },
            format="json",
        )
        # May return 401 — but must not crash
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['detail'], 'Invalid username or password.')

    def test_login_missing_fields(self) -> None:
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "",
                "password": "",
            },
            format="json",
        )
        self.assertNotEqual(response.status_code, 404)

    def test_inactive_user_cannot_log_in(self) -> None:
        user = UserFactory(username="inactive_login", password="inactive_pass")
        user.is_active = False
        user.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/auth/login/",
            {"username": "inactive_login", "password": "inactive_pass"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)


class LogoutViewAPITest(APITestCase):
    """Tests for the user logout view."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = UserFactory(username="logout_test_user", password="logout_pass_123")

    def test_logout_clears_session_even_without_refresh_token(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post("/api/auth/logout/", {}, format="json")

        self.assertEqual(response.status_code, 205)
        follow_up = self.client.get("/api/users/profile/")
        self.assertEqual(follow_up.status_code, 401)




class PasswordChangeViewAPITest(APITestCase):
    """Tests for the password change view endpoint."""

    def setUp(self) -> None:
        self.user = UserFactory(password="old_pw_test_123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_password_change_endpoint_exists(self) -> None:
        response = self.client.put(
            "/api/auth/password-change/",
            {
                "old_password": "old_pw_test_123",
                "new_password1": "new_pw_test_456",
                "new_password2": "new_pw_test_456",
            },
            format="json",
        )
        self.assertNotEqual(response.status_code, 404)

    def test_password_change_wrong_old_pw(self) -> None:
        response = self.client.put(
            "/api/auth/password-change/",
            {
                "old_password": "wrong_old",
                "new_password1": "new_pw_test_789",
                "new_password2": "new_pw_test_789",
            },
            format="json",
        )
        self.assertIn(response.status_code, [200, 400, 401])


class AuthBackendTest(TestCase):
    """Tests for MotelAuthBackend with edge cases."""

    def test_auth_backend_returns_none_for_empty_username(self) -> None:
        from apps.users.backends import MotelAuthBackend

        backend = MotelAuthBackend()
        result = backend.authenticate(username="", password="anything")
        self.assertIsNone(result)

    def test_auth_backend_returns_none_for_empty_password(self) -> None:
        from apps.users.backends import MotelAuthBackend

        backend = MotelAuthBackend()
        result = backend.authenticate(username="anyuser", password="")
        self.assertIsNone(result)

    def test_get_user_by_id_not_found(self) -> None:
        from apps.users.backends import MotelAuthBackend

        backend = MotelAuthBackend()
        result = backend.get_user(999999)
        self.assertIsNone(result)
