from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rooms", "0012_roomgroup")]

    operations = [
        migrations.AlterField(
            model_name="room",
            name="sensor_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Legacy external device identifier; not used for "
                    "room-status ingestion."
                ),
                max_length=100,
            ),
        ),
    ]
