# Generated for manager room editing fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0007_expand_room_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="price",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="room",
            name="ac",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="room",
            name="tv",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="room",
            name="edificio",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="room",
            name="cuenta_luma",
            field=models.IntegerField(default=0),
        ),
    ]
