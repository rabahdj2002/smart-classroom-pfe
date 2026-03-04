import os
import sys
import django

# FIX: Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# Setup Django (CORRECT settings path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclass.settings')
django.setup()

import json
from dashboard.models import Sensor, SensorReading
from django.utils import timezone
import paho.mqtt.client as mqtt

BROKER = "192.168.70.25"
PORT = 1883
TOPIC = "smartclass/#"

def on_connect(client, userdata, flags, rc):
    print(f"✅ MQTT Connected! Listening: {TOPIC}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    try:
        print(f"📨 {msg.topic}: {msg.payload}")
        sensor, created = Sensor.objects.get_or_create(
            topic=msg.topic,
            defaults={'name': msg.topic.split('/')[-1].title()}
        )
        
        data = json.loads(msg.payload.decode())
        SensorReading.objects.create(
            sensor=sensor,
            timestamp=timezone.now(),
            **{k: float(v) if isinstance(v, (int, float)) else v 
               for k, v in data.items() 
               if k in ['temperature', 'humidity', 'pressure', 'light', 'motion']}
        )
        print(f"💾 Saved: {sensor.name}")
    except Exception as e:
        print(f"❌ Error: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()
