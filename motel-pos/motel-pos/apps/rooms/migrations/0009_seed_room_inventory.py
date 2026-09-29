from django.db import migrations


ROOM_INVENTORY = [
    (1, 60, "E1"),
    (2, 40, "E1"),
    (3, 40, "E1"),
    (4, 40, "E1"),
    (5, 40, "E1"),
    (6, 40, "E1"),
    (7, 40, "E1"),
    (8, 40, "E1"),
    (9, 40, "E1"),
    (10, 40, "E1"),
    (11, 40, "E1"),
    (12, 40, "E1"),
    (13, 40, "E1"),
    (14, 40, "E1"),
    (15, 40, "E1"),
    (16, 40, "E1"),
    (17, 40, "E1"),
    (18, 40, "E1"),
    (19, 40, "E1"),
    (20, 40, "E1"),
    (21, 40, "E1"),
    (22, 45, "E1"),
    (23, 45, "E1"),
    (24, 45, "E1"),
    (25, 45, "E1"),
    (26, 45, "E1"),
    (27, 45, "E1"),
    (28, 45, "E1"),
    (29, 45, "E1"),
    (30, 45, "E1"),
    (31, 100, "E1"),
    (32, 45, "E1"),
    (33, 45, "E2"),
    (34, 45, "E2"),
    (35, 45, "E2"),
    (36, 45, "E2"),
    (37, 45, "E2"),
    (38, 45, "E2"),
    (39, 45, "E2"),
    (40, 45, "E2"),
    (41, 45, "E2"),
    (42, 45, "E2"),
    (43, 45, "E2"),
    (44, 70, "E2"),
    (45, 70, "E2"),
    (46, 70, "E2"),
    (47, 45, "E2"),
    (48, 45, "E2"),
    (49, 45, "E2"),
    (50, 45, "E2"),
    (51, 45, "E3"),
    (52, 70, "E3"),
    (53, 50, "E3"),
    (54, 50, "E3"),
    (55, 50, "E3"),
    (56, 50, "E3"),
    (57, 50, "E3"),
    (58, 50, "E3"),
    (59, 50, "E3"),
    (60, 50, "E3"),
    (61, 50, "E3"),
    (62, 50, "E3"),
    (63, 50, "E3"),
    (64, 50, "E3"),
    (65, 50, "E3"),
    (66, 50, "E3"),
    (67, 50, "E3"),
    (68, 50, "E3"),
    (69, 50, "E3"),
    (70, 50, "E3"),
    (71, 50, "E3"),
    (72, 50, "E3"),
    (73, 50, "E3"),
    (74, 50, "E3"),
    (75, 100, "E4"),
    (76, 100, "E4"),
    (77, 50, "E4"),
    (78, 50, "E4"),
    (79, 50, "E4"),
    (80, 50, "E4"),
    (81, 50, "E4"),
    (82, 50, "E4"),
    (83, 50, "E4"),
    (84, 50, "E4"),
    (85, 50, "E4"),
    (86, 100, "E4"),
    (87, 100, "E4"),
]


def seed_room_inventory(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    for room_number, price, edificio in ROOM_INVENTORY:
        room_id = f"room_{room_number}"
        Room.objects.update_or_create(
            room_id=room_id,
            defaults={
                "room_number": str(room_number),
                "sensor_id": f"sensor_{room_id}",
                "active": True,
                "price": price,
                "edificio": edificio,
            },
        )


def reverse_seed_room_inventory(apps, schema_editor):
    Room = apps.get_model("rooms", "Room")
    room_ids = [f"room_{room_number}" for room_number, _, _ in ROOM_INVENTORY]
    Room.objects.filter(room_id__in=room_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0008_room_manager_fields"),
    ]

    operations = [
        migrations.RunPython(seed_room_inventory, reverse_seed_room_inventory),
    ]
