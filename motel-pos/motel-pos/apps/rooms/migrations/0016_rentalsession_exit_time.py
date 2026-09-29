from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rooms", "0015_numeric_room_ids")]

    operations = [
        migrations.AddField(
            model_name="rentalsession",
            name="exit_time",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Actual room exit time; end time remains the billed stay boundary."
                ),
                null=True,
            ),
        ),
    ]
