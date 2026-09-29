import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_default_motel_settings(apps, schema_editor):
    del schema_editor
    motel_settings = apps.get_model("core", "MotelSettings")
    motel_settings.objects.get_or_create(
        singleton_id=1,
        defaults={"vehicle_departure_mode": "manual_confirm_dirty"},
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="MotelSettings",
            fields=[
                (
                    "singleton_id",
                    models.PositiveSmallIntegerField(
                        default=1,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "vehicle_departure_mode",
                    models.CharField(
                        choices=[
                            (
                                "manual_confirm_dirty",
                                "Manual confirmation, then mark room dirty",
                            ),
                            (
                                "automatic_release_vacant",
                                "Automatically release vehicle and keep room vacant",
                            ),
                        ],
                        default="manual_confirm_dirty",
                        help_text=(
                            "Controls what happens when Room Pulse reports a vacant "
                            "room that still has an attached vehicle."
                        ),
                        max_length=40,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        editable=False,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_motel_settings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "motel operational settings",
                "verbose_name_plural": "motel operational settings",
            },
        ),
        migrations.RunPython(
            create_default_motel_settings,
            migrations.RunPython.noop,
        ),
    ]
