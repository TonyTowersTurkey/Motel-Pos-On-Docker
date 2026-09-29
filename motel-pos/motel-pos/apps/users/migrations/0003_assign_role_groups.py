from __future__ import annotations

from django.db import migrations

ROLE_GROUPS = {
    "cashier": "Cashier",
    "manager": "Manager",
    "admin": "Motel Admin",
}


def assign_role_groups(apps, schema_editor):
    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")
    using = schema_editor.connection.alias

    groups = {
        role: Group.objects.using(using).get_or_create(name=group_name)[0]
        for role, group_name in ROLE_GROUPS.items()
    }
    for role, group in groups.items():
        for user in User.objects.using(using).filter(role=role).iterator():
            user.groups.add(group)


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("users", "0002_user_unique_email"),
    ]

    operations = [  # noqa: RUF012
        migrations.RunPython(assign_role_groups, migrations.RunPython.noop),
    ]
