from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0019_classtimetableslot_systemsettings_teacher_access_window_minutes'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImmediateTeacherAccessGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('granted_by_username', models.CharField(blank=True, max_length=150)),
                ('granted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('classroom', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='immediate_access_grants', to='dashboard.classroom')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='immediate_access_grants', to='dashboard.staff')),
            ],
            options={
                'ordering': ['-granted_at'],
            },
        ),
    ]
