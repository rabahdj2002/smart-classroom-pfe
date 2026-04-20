from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0020_immediateteacheraccessgrant'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='student_door_close_delay_minutes',
            field=models.PositiveIntegerField(default=10),
        ),
    ]
