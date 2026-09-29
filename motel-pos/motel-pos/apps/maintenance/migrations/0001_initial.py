from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('rooms', '0012_roomgroup'),
        ('workorders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlannedMaintenanceTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('category', models.CharField(max_length=100)),
                ('default_priority', models.CharField(choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')], default='normal', max_length=20)),
                ('frequency_value', models.PositiveIntegerField(default=6)),
                ('frequency_unit', models.CharField(choices=[('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years')], default='months', max_length=10)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('auto_create_work_orders', models.BooleanField(default=True)),
                ('create_days_before_due', models.PositiveIntegerField(default=7)),
                ('estimated_minutes_per_room', models.PositiveIntegerField(default=20)),
                ('all_rooms', models.BooleanField(default=False)),
                ('target_building', models.CharField(blank=True, max_length=100)),
                ('target_floor', models.CharField(blank=True, max_length=50)),
                ('target_room_type', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('room_groups', models.ManyToManyField(blank=True, related_name='maintenance_templates', to='rooms.roomgroup')),
                ('rooms', models.ManyToManyField(blank=True, related_name='maintenance_templates', to='rooms.room')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='PlannedMaintenanceOccurrence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('due_date', models.DateField()),
                ('is_skipped', models.BooleanField(default=False)),
                ('skipped_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='maintenance_occurrences', to='rooms.room')),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='occurrences', to='maintenance.plannedmaintenancetemplate')),
                ('work_order', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='planned_occurrence_record', to='workorders.workorder')),
            ],
            options={
                'ordering': ['due_date', 'room__room_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='plannedmaintenanceoccurrence',
            constraint=models.UniqueConstraint(fields=('template', 'room', 'due_date'), name='unique_template_room_due_date'),
        ),
    ]
