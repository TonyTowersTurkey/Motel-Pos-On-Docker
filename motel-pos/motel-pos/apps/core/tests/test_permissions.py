"""Tests for DRF-to-Django permission adapters."""

from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from apps.core.permissions import DjangoActionPermissions, DjangoPermissionRequired
from apps.users.tests.factories import UserFactory


class PermissionAdaptersTest(TestCase):
    def test_action_permission_uses_declared_django_permission(self) -> None:
        user = UserFactory(role="cashier")
        request = SimpleNamespace(user=user)
        view = SimpleNamespace(
            action="override",
            permission_map={"override": "rooms.operate_room"},
        )

        self.assertTrue(DjangoActionPermissions().has_permission(request, view))
        view.permission_map["override"] = "rooms.change_room"
        self.assertFalse(DjangoActionPermissions().has_permission(request, view))

    def test_action_permission_fails_closed_without_mapping(self) -> None:
        user = UserFactory(role="admin")
        request = SimpleNamespace(user=user)
        view = SimpleNamespace(action="unmapped", permission_map={})

        self.assertFalse(DjangoActionPermissions().has_permission(request, view))

    def test_required_permission_supports_direct_user_permission(self) -> None:
        user = UserFactory(role="cashier")
        permission = Permission.objects.get(
            content_type__app_label="users", codename="view_user"
        )
        user.user_permissions.add(permission)
        user = type(user).objects.get(pk=user.pk)
        request = SimpleNamespace(user=user)
        view = SimpleNamespace(permission_required="users.view_user")

        self.assertTrue(DjangoPermissionRequired().has_permission(request, view))

    def test_manager_page_uses_permission_instead_of_legacy_role(self) -> None:
        user = UserFactory(role="cashier")
        permission = Permission.objects.get(
            content_type__app_label="rooms", codename="change_room"
        )
        user.user_permissions.add(permission)
        client = Client()
        client.force_login(user)

        response = client.get("/manager/")

        self.assertEqual(response.status_code, 200)

    def test_legacy_manager_role_without_group_is_not_authoritative(self) -> None:
        user = UserFactory.build(role="manager")
        user.email = "ungrouped-manager@test.example"
        user.set_password("test-password")
        user.save()
        client = Client()
        client.force_login(user)

        response = client.get("/manager/")

        self.assertEqual(response.status_code, 403)
