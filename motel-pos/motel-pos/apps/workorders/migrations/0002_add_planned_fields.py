from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('maintenance', '0001_initial'),
        ('workorders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='workorder',
            name='planned_template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='work_orders', to='maintenance.plannedmaintenancetemplate'),
        ),
        migrations.AddField(
            model_name='workorder',
            name='planned_occurrence',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='work_order_link', to='maintenance.plannedmaintenanceoccurrence'),
        ),
    ]
