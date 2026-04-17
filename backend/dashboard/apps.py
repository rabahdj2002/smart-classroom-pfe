from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        from . import signals  # noqa: F401
        from .mqtt_listener import start_mqtt_listener
        from .scheduler import start_internal_scheduler

        start_internal_scheduler()
        start_mqtt_listener()
