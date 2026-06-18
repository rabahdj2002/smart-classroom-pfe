import json
import threading
import paho.mqtt.client as mqtt
from channels.generic.websocket import WebsocketConsumer

from .mqtt_runtime import configure_mqtt_client, get_mqtt_runtime_config

class MQTTProxyConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

        runtime_config = get_mqtt_runtime_config()

        self.mqtt_client = mqtt.Client(transport="tcp")
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_connect = self.on_mqtt_connect

        configure_mqtt_client(self.mqtt_client, runtime_config)
        
        try:
            self.mqtt_client.connect(
                runtime_config['broker_host'],
                runtime_config['broker_port'],
                runtime_config['keepalive'],
            )
            
            # Lightweight background thread for the MQTT loop
            self.mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever)
            self.mqtt_thread.daemon = True
            self.mqtt_thread.start()
        except Exception as e:
            self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Failed to bridge to MQTT: {str(e)}'
            }))
            self.close()

    def disconnect(self, close_code):
        if hasattr(self, 'mqtt_client'):
            self.mqtt_client.disconnect()

    def receive(self, text_data):
        """Handle commands from Frontend -> WebSocket -> Local MQTT"""
        try:
            data = json.loads(text_data)
            topic = data.get('topic')
            payload = data.get('payload')
            
            if topic and payload is not None:
                # Ensure payload is a string or bytes for paho-mqtt
                if not isinstance(payload, (str, bytes)):
                    payload = json.dumps(payload)
                
                self.mqtt_client.publish(topic, payload)
        except Exception as e:
            self.send(text_data=json.dumps({'error': str(e)}))

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # Listen to all smartclass events to proxy back to UI
            client.subscribe("smartclass/#")

    def on_mqtt_message(self, client, userdata, msg):
        """Handle events from Local MQTT -> WebSocket -> Frontend"""
        try:
            payload = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            payload = str(msg.payload)
            
        self.send(text_data=json.dumps({
            'topic': msg.topic,
            'payload': payload
        }))
