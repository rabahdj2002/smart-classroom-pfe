from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0016_delete_attendance'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='allow_bulk_actions',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='default_list_page_size',
            field=models.PositiveIntegerField(default=50),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='default_sessions_order',
            field=models.CharField(default='id_desc', max_length=8),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='show_kpi_badges',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='ui_compact_mode',
            field=models.BooleanField(default=False),
        ),
    ]
