# Generated migration for session types and student attendance tracking

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0022_session_session_type'),
    ]

    operations = [
        # Update Session model
        migrations.RemoveField(
            model_name='session',
            name='session_type',
        ),
        migrations.AddField(
            model_name='session',
            name='session_type',
            field=models.CharField(
                choices=[
                    ('class', 'Class Session'),
                    ('inspection', 'Admin Inspection'),
                ],
                default='class',
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name='session',
            name='access_type',
            field=models.CharField(
                choices=[
                    ('timetable', 'Scheduled Timetable'),
                    ('out_of_schedule', 'Out-of-Schedule Override'),
                    ('none', 'N/A (Inspection)'),
                ],
                default='none',
                max_length=20,
            ),
        ),
        # Create StudentSessionAttendance model
        migrations.CreateModel(
            name='StudentSessionAttendance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('arrival_time', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_attendances', to='dashboard.session')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_attendances', to='dashboard.student')),
            ],
            options={
                'verbose_name_plural': 'Student Session Attendances',
                'ordering': ['arrival_time'],
            },
        ),
        migrations.AddConstraint(
            model_name='studentsessionattendance',
            constraint=models.UniqueConstraint(fields=['session', 'student'], name='unique_session_student_attendance'),
        ),
    ]
