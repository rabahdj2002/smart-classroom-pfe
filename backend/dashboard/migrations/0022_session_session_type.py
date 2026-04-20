# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0021_systemsettings_student_door_close_delay_minutes'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='session_type',
            field=models.CharField(
                choices=[
                    ('regular', 'Regular RFID Event'),
                    ('timetable_access', 'Timetable Access'),
                    ('out_of_schedule_access', 'Out-of-Schedule Access'),
                    ('inspection', 'Admin Inspection'),
                ],
                default='regular',
                max_length=25,
            ),
        ),
    ]
