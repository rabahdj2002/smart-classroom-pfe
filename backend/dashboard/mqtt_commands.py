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
    
    # Simple HiveMQ Cloud publication
    broker_host = settings_obj.mqtt_broker_host
    broker_port = int(settings_obj.mqtt_broker_port)
    username = settings_obj.mqtt_username
    password = settings_obj.mqtt_password
    keepalive = 60

    client = mqtt.Client(transport="tcp")
    client.tls_set() # Always required for HiveMQ Cloud

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


def publish_custom_topic(topic, payload):
    _publish_payload(topic, payload)
    logger.info('Published MQTT payload to %s: %s', topic, payload)
    return topic, payload
