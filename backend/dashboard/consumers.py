import json
import threading
import paho.mqtt.client as mqtt
from channels.generic.websocket import WebsocketConsumer

class MQTTProxyConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()
        
        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_connect = self.on_mqtt_connect
        
        # Connect to local broker
        try:
            self.mqtt_client.connect("127.0.0.1", 1883, 60)
            
            # Start loop in a background thread
            self.mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever)
            self.mqtt_thread.daemon = True
            self.mqtt_thread.start()
        except Exception as e:
            self.send(text_data=json.dumps({
                'error': f'Could not connect to MQTT broker: {str(e)}'
            }))
            self.close()

    def disconnect(self, close_code):
        if hasattr(self, 'mqtt_client'):
            self.mqtt_client.disconnect()

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
            topic = data.get('topic')
            payload = data.get('payload')
            
            if topic and payload is not None:
                # Ensure payload is a string or bytes for paho-mqtt
                if not isinstance(payload, (str, bytes)):
                    payload = json.dumps(payload)
                
                self.mqtt_client.publish(topic, payload)
        except json.JSONDecodeError:
            self.send(text_data=json.dumps({'error': 'Invalid JSON'}))
        except Exception as e:
            self.send(text_data=json.dumps({'error': str(e)}))

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # Subscribe to all topics by default or a specific range
            # For a proxy, we might want to subscribe to topics the client asks for
            # For now, subscribing to smartclass/# as a default
            client.subscribe("smartclass/#")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            payload = str(msg.payload)
            
        self.send(text_data=json.dumps({
            'topic': msg.topic,
            'payload': payload
        }))
