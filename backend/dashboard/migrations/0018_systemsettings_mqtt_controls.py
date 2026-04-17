from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0017_systemsettings_ui_controls'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='mqtt_broker_host',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='mqtt_broker_port',
            field=models.PositiveIntegerField(default=1883),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='mqtt_mode',
            field=models.CharField(default='production', max_length=16),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='mqtt_topic_wildcard',
            field=models.CharField(default='smartclass/#', max_length=255),
        ),
    ]
