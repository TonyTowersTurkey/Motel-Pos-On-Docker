import django.db.models.deletion
from django.db import migrations, models

DEFAULT_SHAPES = [
    "4-door car",
    "Pickup",
    "Sedan",
    "Coupe",
    "SUV",
    "Van",
    "Minivan",
    "Hatchback",
    "Wagon",
    "Convertible",
]


def seed_vehicle_shapes(apps, schema_editor):
    vehicle_shape = apps.get_model("guests", "VehicleShape")
    for sort_order, name in enumerate(DEFAULT_SHAPES, start=1):
        vehicle_shape.objects.get_or_create(
            name=name,
            defaults={"active": True, "sort_order": sort_order},
        )


class Migration(migrations.Migration):
    dependencies = [("guests", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="VehicleShape",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=50, unique=True)),
                ("active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "vehicle_shapes",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="vehicle",
            name="vehicle_shape",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vehicles",
                to="guests.vehicleshape",
            ),
        ),
        migrations.RunPython(seed_vehicle_shapes, migrations.RunPython.noop),
    ]
