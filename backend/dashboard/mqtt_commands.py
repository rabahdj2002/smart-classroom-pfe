import json
import logging

import paho.mqtt.client as mqtt

from .mqtt_runtime import configure_mqtt_client, get_mqtt_runtime_config

logger = logging.getLogger(__name__)

def _build_command_topic(classroom_name):
    return f"smartclass/classrooms/{classroom_name}/commands"


def _publish_payload(topic, payload):
    runtime_config = get_mqtt_runtime_config()

    client = mqtt.Client(transport="tcp")
    configure_mqtt_client(client, runtime_config)

    client.connect(
        runtime_config['broker_host'],
        runtime_config['broker_port'],
        runtime_config['keepalive'],
    )
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
