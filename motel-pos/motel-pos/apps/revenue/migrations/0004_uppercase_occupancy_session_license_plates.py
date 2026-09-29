from django.db import migrations
from django.db.models.functions import Upper


def uppercase_occupancy_session_license_plates(apps, schema_editor):
    del schema_editor
    occupancy_session = apps.get_model("revenue", "OccupancySession")
    occupancy_session.objects.exclude(license_plate="").update(
        license_plate=Upper("license_plate")
    )


class Migration(migrations.Migration):
    dependencies = [("revenue", "0003_alter_shiftledger_options")]

    operations = [
        migrations.RunPython(
            uppercase_occupancy_session_license_plates,
            migrations.RunPython.noop,
        ),
    ]
