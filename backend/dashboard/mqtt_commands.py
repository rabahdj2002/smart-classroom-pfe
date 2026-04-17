import json
import logging

import paho.mqtt.client as mqtt
from django.conf import settings

from .models import SystemSettings

logger = logging.getLogger(__name__)


def _get_system_settings():
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return settings_obj


def _build_command_topic(classroom_name):
    return f"smartclass/classrooms/{classroom_name}/commands"


def _publish_payload(topic, payload):
    settings_obj = _get_system_settings()
    broker_host = settings_obj.mqtt_broker_host or getattr(settings, 'DASHBOARD_MQTT_BROKER_HOST', '127.0.0.1')
    broker_port = int(settings_obj.mqtt_broker_port or getattr(settings, 'DASHBOARD_MQTT_BROKER_PORT', 1883))
    username = getattr(settings, 'DASHBOARD_MQTT_USERNAME', '')
    password = getattr(settings, 'DASHBOARD_MQTT_PASSWORD', '')
    keepalive = int(getattr(settings, 'DASHBOARD_MQTT_KEEPALIVE_SECONDS', 60))

    client = mqtt.Client()
    if username:
        client.username_pw_set(username=username, password=password or None)

    client.connect(broker_host, broker_port, keepalive)
    client.loop_start()
    try:
        result = client.publish(topic, json.dumps(payload), qos=1, retain=False)
        result.wait_for_publish()
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f'Failed to publish MQTT command, rc={result.rc}')
    finally:
        client.loop_stop()
        client.disconnect()


def publish_classroom_command(classroom, command, value=None):
    payload = {
        'command': command,
        'classroom_id': classroom.id,
        'classroom_name': classroom.name,
        'value': value,
    }
    topic = _build_command_topic(classroom.name)
    _publish_payload(topic, payload)
    logger.info('Published MQTT command to %s: %s', topic, payload)
    return topic, payload
