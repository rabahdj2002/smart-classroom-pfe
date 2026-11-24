from unittest.mock import MagicMock, patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import TestCase, override_settings

from .consumers import MQTTProxyConsumer
from .models import AttendanceReport, Classroom, Session, Staff, Student, SystemSettings
from .mqtt_listener import process_mqtt_payload
from .mqtt_runtime import get_mqtt_runtime_config

RUNTIME = {'broker_host': 'localhost', 'broker_port': 1883, 'keepalive': 60, 'tls_enabled': False, 'username': '', 'password': ''}


class WebSocketBridgeTests(TestCase):
    def _connect(self, user):
        async def run():
            communicator = WebsocketCommunicator(MQTTProxyConsumer.as_asgi(), '/mqtt/')
            communicator.scope['user'] = user
            connected, code = await communicator.connect()
            if connected:
                await communicator.send_json_to({'topic': 'other/topic', 'payload': 'x'})
                reply = await communicator.receive_json_from()
                await communicator.send_json_to({'topic': 'smartclass/classrooms/A1/commands', 'payload': {'command': 'lights'}})
                await communicator.receive_nothing()
                await communicator.disconnect()
                return connected, reply
            return connected, code
        return async_to_sync(run)()

    def test_anonymous_websocket_is_rejected(self):
        connected, code = self._connect(AnonymousUser())
        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    @patch('dashboard.consumers.get_mqtt_runtime_config', return_value=RUNTIME)
    @patch('dashboard.consumers.mqtt.Client')
    def test_admin_can_only_publish_smartclass_topics(self, client_cls, _config):
        client = MagicMock()
        client_cls.return_value = client
        admin = get_user_model().objects.create_user('ws-admin', password='x', is_staff=True)
        connected, reply = self._connect(admin)
        self.assertTrue(connected)
        self.assertIn('error', reply)
        client.publish.assert_called_once_with('smartclass/classrooms/A1/commands', '{"command": "lights"}')


class MqttRuntimeConfigTests(TestCase):
    @override_settings(DASHBOARD_MQTT_BROKER_HOST='mqtt', DASHBOARD_MQTT_BROKER_PORT=1883)
    def test_placeholder_broker_falls_back_to_environment(self):
        SystemSettings.objects.get_or_create(pk=1)
        config = get_mqtt_runtime_config()
        self.assertEqual((config['broker_host'], config['broker_port'], config['tls_enabled']), ('mqtt', 1883, False))

    def test_configured_broker_in_database_wins(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'mqtt_broker_host': 'broker.example.com', 'mqtt_broker_port': 8883})
        config = get_mqtt_runtime_config()
        self.assertEqual((config['broker_host'], config['broker_port'], config['tls_enabled']), ('broker.example.com', 8883, True))


class MqttPayloadRobustnessTests(TestCase):
    def test_malformed_and_unknown_payloads_do_not_raise(self):
        Classroom.objects.create(name='R1')
        for topic, payload in [
            ('smartclass/classrooms/R1/events', b'not-json'),
            ('smartclass/classrooms/R1/events', b'[1, 2, 3]'),
            ('smartclass/classrooms/NOPE/events', b'{"occupied": true}'),
            ('smartclass/classrooms/R1/access/request', b'{}'),
            ('random/topic', b'{"x": 1}'),
            ('smartclass/classrooms/R1/events', b'\xff\xfe'),
        ]:
            with self.subTest(topic=topic, payload=payload), patch('dashboard.mqtt_listener.publish_custom_topic'):
                process_mqtt_payload(topic, payload)


class SeedDemoCommandTests(TestCase):
    def test_seed_demo_is_idempotent_and_pages_render(self):
        call_command('seed_demo', stdout=MagicMock())
        call_command('seed_demo', stdout=MagicMock())
        self.assertEqual(Classroom.objects.count(), 4)
        self.assertEqual(Staff.objects.count(), 4)
        self.assertEqual(Student.objects.count(), 12)
        self.assertGreater(AttendanceReport.objects.count(), 0)
        self.assertTrue(Session.objects.filter(is_closed=False).exists())
        self.assertTrue(self.client.login(username='demo', password='demo12345'))
        for url in ['/', '/classes/', '/sessions/', '/students/', '/staff/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_seed_demo_skips_when_real_data_exists_and_keeps_custom_broker(self):
        Staff.objects.create(name='Existing', email='staff0@demo.campus', role='PROF', id_number='T-100', rfid_number='RFID-T-100')
        SystemSettings.objects.update_or_create(pk=1, defaults={'mqtt_broker_host': 'broker.example.com', 'mqtt_broker_port': 8883})
        call_command('seed_demo', stdout=MagicMock())
        self.assertFalse(Classroom.objects.exists())
        self.assertEqual(SystemSettings.objects.get(pk=1).mqtt_broker_host, 'broker.example.com')
