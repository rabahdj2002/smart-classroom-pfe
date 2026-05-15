from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0018_systemsettings_mqtt_controls'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='teacher_access_window_minutes',
            field=models.PositiveIntegerField(default=10),
        ),
        migrations.CreateModel(
            name='ClassTimetableSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField(choices=[(5, 'Saturday'), (6, 'Sunday'), (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday')])),
                ('slot_index', models.PositiveSmallIntegerField(choices=[(0, '08:00 - 09:30'), (1, '09:30 - 11:00'), (2, '11:00 - 12:30'), (3, '12:30 - 14:00'), (4, '14:00 - 15:30'), (5, '15:30 - 17:00')])),
                ('subject', models.CharField(blank=True, max_length=120)),
                ('classroom', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_slots', to='dashboard.classroom')),
                ('teacher', models.ForeignKey(blank=True, limit_choices_to={'role': 'PROF'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='timetable_slots', to='dashboard.staff')),
            ],
            options={
                'ordering': ['weekday', 'slot_index'],
                'constraints': [models.UniqueConstraint(fields=('classroom', 'weekday', 'slot_index'), name='unique_timetable_slot_per_classroom')],
            },
        ),
    ]
