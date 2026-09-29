"""Tests for the transitional Django group permission policy."""

from django.contrib.auth.models import Group
from django.test import TestCase

from apps.users.access import (
    ADMIN_GROUP,
    CASHIER_GROUP,
    MANAGER_GROUP,
    assign_role_group,
    provision_role_groups,
)
from apps.users.models import User


class RoleGroupPolicyTest(TestCase):
    def test_managed_groups_have_expected_permissions(self) -> None:
        provision_role_groups()

        cashier = Group.objects.get(name=CASHIER_GROUP)
        manager = Group.objects.get(name=MANAGER_GROUP)
        admin = Group.objects.get(name=ADMIN_GROUP)

        self.assertTrue(cashier.permissions.filter(codename="operate_room").exists())
        self.assertTrue(manager.permissions.filter(codename="change_room").exists())
        self.assertTrue(admin.permissions.filter(codename="change_user").exists())
        self.assertFalse(cashier.permissions.filter(codename="change_room").exists())

    def test_existing_roles_are_migrated_to_managed_groups(self) -> None:
        cashier = User.objects.create_user(
            username="group_cashier", email="cashier@group.test", role="cashier"
        )
        manager = User.objects.create_user(
            username="group_manager", email="manager@group.test", role="manager"
        )
        admin = User.objects.create_user(
            username="group_admin", email="admin@group.test", role="admin"
        )

        provision_role_groups()

        self.assertTrue(cashier.groups.filter(name=CASHIER_GROUP).exists())
        self.assertTrue(manager.groups.filter(name=MANAGER_GROUP).exists())
        self.assertTrue(admin.groups.filter(name=ADMIN_GROUP).exists())

    def test_role_group_assignment_preserves_unmanaged_groups(self) -> None:
        user = User.objects.create_user(username="group_update", role="cashier")
        unrelated = Group.objects.create(name="Night Shift")
        user.groups.add(unrelated)

        assign_role_group(user)
        user.role = User.Role.MANAGER
        user.save(update_fields=["role"])
        assign_role_group(user)

        self.assertTrue(user.groups.filter(name=MANAGER_GROUP).exists())
        self.assertFalse(user.groups.filter(name=CASHIER_GROUP).exists())
        self.assertTrue(user.groups.filter(name="Night Shift").exists())
