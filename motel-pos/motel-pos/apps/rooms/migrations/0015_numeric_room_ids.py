from django.core.validators import RegexValidator
from django.db import migrations, models


def numeric_room_ids(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    mappings = list(Room.objects.values_list("room_id", "room_number"))
    if any(not str(number).isdigit() for _, number in mappings):
        raise RuntimeError("Every room_number must be numeric before converting room IDs.")
    numbers = [str(number) for _, number in mappings]
    if len(numbers) != len(set(numbers)):
        raise RuntimeError("Room numbers must be unique before converting room IDs.")

    related = [
        (apps.get_model("occupancy", "SensorReading"), "room_id"),
        (apps.get_model("occupancy", "OccupancyEvent"), "room_id"),
        (apps.get_model("revenue", "OccupancySession"), "room_id"),
        (apps.get_model("rooms", "RoomAmenity"), "room_id"),
        (apps.get_model("rooms", "MaintenanceLog"), "room_id"),
        (apps.get_model("rooms", "RentalSession"), "room_id"),
    ]
    fk_related = [
        (apps.get_model("occupancy", "RoomPulseRoomState"), "room_id"),
        (apps.get_model("workorders", "WorkOrder"), "room_id"),
        (apps.get_model("maintenance", "PlannedMaintenanceOccurrence"), "room_id"),
    ]
    through_models = [
        apps.get_model("rooms", "RoomGroup").rooms.through,
        apps.get_model("maintenance", "PlannedMaintenanceTemplate").rooms.through,
    ]

    for old_id, room_number in mappings:
        new_id = str(room_number)
        if old_id == new_id:
            continue
        old = Room.objects.get(pk=old_id)
        values = {
            field.name: getattr(old, field.name)
            for field in Room._meta.concrete_fields
            if not field.primary_key
        }
        Room.objects.create(room_id=new_id, **values)
        for model, field in related:
            model.objects.filter(**{field: old_id}).update(**{field: new_id})
        for model, field in fk_related:
            model.objects.filter(**{field: old_id}).update(**{field: new_id})
        for through in through_models:
            through.objects.filter(room_id=old_id).update(room_id=new_id)
        old.delete()


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ("rooms", "0014_alter_rentalsession_options_alter_room_options"),
        ("occupancy", "0003_roompulsedelivery_alter_occupancyevent_event_type_and_more"),
        ("revenue", "0003_alter_shiftledger_options"),
        ("maintenance", "0001_initial"),
        ("workorders", "0004_workorder_assigned_to_label_workorder_attachments_and_more"),
    ]
    operations = [
        migrations.RunPython(numeric_room_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="room",
            name="room_id",
            field=models.CharField(
                max_length=50,
                primary_key=True,
                serialize=False,
                validators=[RegexValidator(r"^[0-9]+$", "Room ID must contain numbers only.")],
            ),
        ),
    ]
