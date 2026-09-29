from django.core.validators import FileExtensionValidator
from django.db import migrations, models

import apps.guests.models

VEHICLE_SHAPES = [
    "Micro",
    "Sedan",
    "Hatchback",
    "Coupe",
    "Station Wagon",
    "Roadster",
    "Cabriolet",
    "Muscle Car",
    "Sport Car",
    "Super Car",
    "Limousine",
    "CUV",
    "Pickup",
    "SUV",
    "Minivan",
    "Van",
    "Campervan",
    "Bus",
    "Monster Truck",
    "Mini Truck",
    "Truck",
    "Big Truck",
]


def replace_vehicle_shapes(apps, schema_editor):
    del schema_editor
    vehicle = apps.get_model("guests", "Vehicle")
    vehicle_shape = apps.get_model("guests", "VehicleShape")
    vehicle.objects.update(vehicle_shape=None)
    vehicle_shape.objects.all().delete()
    vehicle_shape.objects.bulk_create(
        [
            vehicle_shape(name=name, active=True, sort_order=index)
            for index, name in enumerate(VEHICLE_SHAPES, start=1)
        ]
    )


class Migration(migrations.Migration):
    dependencies = [("guests", "0002_vehicleshape_vehicle_vehicle_shape")]

    operations = [
        migrations.AddField(
            model_name="vehicleshape",
            name="icon",
            field=models.ImageField(
                blank=True,
                help_text=(
                    "Upload a simple PNG, JPEG, or WebP silhouette (maximum 2 MB)."
                ),
                upload_to="vehicle-shapes/",
                validators=[
                    FileExtensionValidator(["png", "jpg", "jpeg", "webp"]),
                    apps.guests.models.validate_vehicle_shape_icon_size,
                ],
            ),
        ),
        migrations.RunPython(replace_vehicle_shapes, migrations.RunPython.noop),
    ]
