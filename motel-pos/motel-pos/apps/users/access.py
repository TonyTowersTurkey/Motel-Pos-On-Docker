"""Django group and permission policy for motel application access."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.db import transaction

from apps.users.models import User

CASHIER_GROUP = "Cashier"
MANAGER_GROUP = "Manager"
ADMIN_GROUP = "Motel Admin"

ROLE_GROUPS = {
    User.Role.CASHIER: CASHIER_GROUP,
    User.Role.MANAGER: MANAGER_GROUP,
    User.Role.ADMIN: ADMIN_GROUP,
}

CASHIER_PERMISSIONS = {
    "rooms.view_room",
    "rooms.operate_room",
    "rooms.view_rentalsession",
    "rooms.add_rentalsession",
    "rooms.extend_rentalsession",
    "guests.view_vehicle",
    "guests.add_vehicle",
    "guests.view_vehicleshape",
    "occupancy.view_occupancyevent",
    "revenue.view_shift_reports",
    "revenue.generate_shift",
}

MANAGER_PERMISSIONS = CASHIER_PERMISSIONS | {
    "users.view_user",
    "rooms.add_room",
    "rooms.change_room",
    "rooms.delete_room",
    "rooms.view_roomgroup",
    "rooms.add_roomgroup",
    "rooms.change_roomgroup",
    "rooms.delete_roomgroup",
    "rooms.view_pricingtier",
    "rooms.add_pricingtier",
    "rooms.change_pricingtier",
    "rooms.delete_pricingtier",
    "rooms.view_amenity",
    "rooms.add_amenity",
    "rooms.change_amenity",
    "rooms.delete_amenity",
    "rooms.view_roomamenity",
    "rooms.add_roomamenity",
    "rooms.change_roomamenity",
    "rooms.delete_roomamenity",
    "rooms.view_maintenancelog",
    "rooms.add_maintenancelog",
    "rooms.change_maintenancelog",
    "rooms.delete_maintenancelog",
    "rooms.change_rentalsession",
    "rooms.delete_rentalsession",
    "rooms.view_dynamicpricingrule",
    "rooms.add_dynamicpricingrule",
    "rooms.change_dynamicpricingrule",
    "rooms.delete_dynamicpricingrule",
    "guests.change_vehicle",
    "guests.delete_vehicle",
    "guests.add_vehicleshape",
    "guests.change_vehicleshape",
    "guests.delete_vehicleshape",
    "occupancy.add_occupancyevent",
    "occupancy.change_occupancyevent",
    "occupancy.delete_occupancyevent",
    "occupancy.view_auditlog",
    "revenue.view_occupancysession",
    "revenue.add_occupancysession",
    "revenue.change_occupancysession",
    "revenue.delete_occupancysession",
    "revenue.view_shiftledger",
    "revenue.add_shiftledger",
    "revenue.change_shiftledger",
    "revenue.delete_shiftledger",
    "revenue.generate_management_reports",
    "maintenance.view_plannedmaintenancetemplate",
    "maintenance.add_plannedmaintenancetemplate",
    "maintenance.change_plannedmaintenancetemplate",
    "maintenance.delete_plannedmaintenancetemplate",
    "maintenance.view_plannedmaintenanceoccurrence",
    "maintenance.add_plannedmaintenanceoccurrence",
    "maintenance.change_plannedmaintenanceoccurrence",
    "maintenance.delete_plannedmaintenanceoccurrence",
    "workorders.view_workorder",
    "workorders.add_workorder",
    "workorders.change_workorder",
    "workorders.delete_workorder",
}

ADMIN_PERMISSIONS = MANAGER_PERMISSIONS | {
    "core.view_motelsettings",
    "core.change_motelsettings",
    "users.view_user",
    "users.add_user",
    "users.change_user",
    "users.delete_user",
}

GROUP_PERMISSIONS = {
    CASHIER_GROUP: CASHIER_PERMISSIONS,
    MANAGER_GROUP: MANAGER_PERMISSIONS,
    ADMIN_GROUP: ADMIN_PERMISSIONS,
}

PERMISSION_CACHE_KEYS = (
    "_perm_cache",
    "_user_perm_cache",
    "_group_perm_cache",
)


def _permissions_for(
    labels: tuple[str, ...] | list[str] | set[str], using: str
) -> list[Permission]:
    """Resolve ``app_label.codename`` labels that exist in the database."""
    labels = set(labels)
    codenames = {label.partition(".")[2] for label in labels}
    permissions = Permission.objects.using(using).filter(
        codename__in=codenames,
        content_type__app_label__in={label.partition(".")[0] for label in labels},
    )
    return [
        permission
        for permission in permissions
        if f"{permission.content_type.app_label}.{permission.codename}" in labels
    ]


@transaction.atomic
def provision_role_groups(
    *, using: str = "default", migrate_users: bool = True
) -> None:
    """Create managed groups, set their permissions, and migrate role users."""
    managed_groups: dict[str, Group] = {}
    for group_name, permission_labels in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.using(using).get_or_create(name=group_name)
        group.permissions.set(_permissions_for(permission_labels, using))
        managed_groups[group_name] = group

    if not migrate_users:
        return

    managed_names = set(GROUP_PERMISSIONS)
    for role, group_name in ROLE_GROUPS.items():
        for user in User.objects.using(using).filter(role=role).iterator():
            user.groups.remove(*user.groups.filter(name__in=managed_names))
            user.groups.add(managed_groups[group_name])


def assign_role_group(user: User) -> None:
    """Assign the managed group matching ``user.role`` while preserving others."""
    group_name = ROLE_GROUPS.get(user.role)
    if group_name is None or not user.pk:
        return
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.remove(*user.groups.filter(name__in=GROUP_PERMISSIONS))
    user.groups.add(group)
    for cache_key in PERMISSION_CACHE_KEYS:
        user.__dict__.pop(cache_key, None)
