from django.db import migrations, models


FORWARD_MODES = {
    "manual_confirm_dirty": "pos_hands_on_mode",
    "automatic_release_vacant": "audit_mode",
}
REVERSE_MODES = {value: key for key, value in FORWARD_MODES.items()}


def rename_mode_values(apps, schema_editor):
    del schema_editor
    motel_settings = apps.get_model("core", "MotelSettings")
    for old_value, new_value in FORWARD_MODES.items():
        motel_settings.objects.filter(operating_mode=old_value).update(
            operating_mode=new_value
        )


def restore_mode_values(apps, schema_editor):
    del schema_editor
    motel_settings = apps.get_model("core", "MotelSettings")
    for new_value, old_value in REVERSE_MODES.items():
        motel_settings.objects.filter(operating_mode=new_value).update(
            operating_mode=old_value
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0001_motel_settings")]

    operations = [
        migrations.RenameField(
            model_name="motelsettings",
            old_name="vehicle_departure_mode",
            new_name="operating_mode",
        ),
        migrations.RunPython(rename_mode_values, restore_mode_values),
        migrations.AlterField(
            model_name="motelsettings",
            name="operating_mode",
            field=models.CharField(
                choices=[
                    (
                        "audit_mode",
                        "Audit Mode — hands-off, no cashier interaction",
                    ),
                    (
                        "pos_hands_on_mode",
                        "POS Hands On Mode — wait for cashier, then mark room dirty",
                    ),
                ],
                default="pos_hands_on_mode",
                help_text=(
                    "Controls the motel's overall operating workflow. Audit Mode "
                    "is hands-off; POS Hands On Mode waits for cashier interaction."
                ),
                max_length=40,
            ),
        ),
    ]
