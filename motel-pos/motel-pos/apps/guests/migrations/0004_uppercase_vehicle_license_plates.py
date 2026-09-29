from django.db import migrations
from django.db.models.functions import Upper


def uppercase_vehicle_license_plates(apps, schema_editor):
    del schema_editor
    vehicle = apps.get_model("guests", "Vehicle")
    vehicle.objects.exclude(license_plate="").update(
        license_plate=Upper("license_plate")
    )


class Migration(migrations.Migration):
    dependencies = [("guests", "0003_replace_vehicle_shapes_and_add_icons")]

    operations = [
        migrations.RunPython(
            uppercase_vehicle_license_plates,
            migrations.RunPython.noop,
        ),
    ]
