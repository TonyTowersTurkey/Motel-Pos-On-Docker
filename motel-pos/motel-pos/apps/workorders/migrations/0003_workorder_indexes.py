from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("workorders", "0002_add_planned_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(fields=["status", "priority"], name="workorders__status_a1b0ea_idx"),
        ),
        migrations.AddIndex(
            model_name="workorder",
            index=models.Index(fields=["room", "due_date"], name="workorders__room_id_dd6070_idx"),
        ),
    ]
