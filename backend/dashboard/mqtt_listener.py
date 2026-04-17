import json
import logging
import os
import sys
import threading
import time
from datetime import timedelta

import paho.mqtt.client as mqtt
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AttendanceReport, Classroom, Session, Staff, Student
from .reporting import auto_finish_active_classrooms, generate_attendance_report_for_session, get_system_settings

logger = logging.getLogger(__name__)

_mqtt_started = False
_mqtt_lock = threading.Lock()


def _bool_or_none(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'1', 'true', 'on', 'yes'}:
            return True
        if normalized in {'0', 'false', 'off', 'no'}:
            return False
    return None


def _resolve_timestamp(data):
    raw = data.get('timestamp')
    if not raw:
        return timezone.now()

    parsed = parse_datetime(str(raw))
    if not parsed:
        return timezone.now()

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _resolve_classroom(data, topic):
    classroom_id = data.get('classroom_id')
    classroom_name = data.get('classroom_name') or data.get('classroom')

    if classroom_id:
        classroom = Classroom.objects.filter(id=classroom_id).first()
        if classroom:
            return classroom

    if classroom_name:
        classroom = Classroom.objects.filter(name__iexact=str(classroom_name).strip()).first()
        if classroom:
            return classroom
        return Classroom.objects.create(name=str(classroom_name).strip())

    # Topic fallback: smartclass/classrooms/<name>/...
    parts = topic.split('/')
    if len(parts) >= 3 and parts[0] == 'smartclass' and parts[1] == 'classrooms':
        guessed_name = parts[2].strip()
        if guessed_name:
            classroom = Classroom.objects.filter(name__iexact=guessed_name).first()
            if classroom:
                return classroom
            return Classroom.objects.create(name=guessed_name)

    return None


def _normalize_student_rfids(data):
    # Accept student_rfid, student_rfids, or students as a list/string.
    if data.get('student_rfid'):
        return [str(data.get('student_rfid')).strip()]

    candidates = data.get('student_rfids')
    if candidates is None:
        candidates = data.get('students')

    if candidates is None:
        return []

    if isinstance(candidates, str):
        # Support CSV or single value.
        if ',' in candidates:
            return [part.strip() for part in candidates.split(',') if part.strip()]
        return [candidates.strip()] if candidates.strip() else []

    if isinstance(candidates, list):
        return [str(item).strip() for item in candidates if str(item).strip()]

    return []


def _is_new_session_request(data):
    return any(
        _bool_or_none(data.get(key)) is True
        for key in ('new_session', 'session_start', 'start_new_session', 'force_new_session')
    )


def _close_open_sessions_for_classroom(classroom, event_time):
    settings_obj = get_system_settings()
    closed_reports = []

    open_sessions = Session.objects.select_related('classroom', 'teacher').prefetch_related('students').filter(
        classroom=classroom,
        is_closed=False,
    ).order_by('start_time')

    for session in open_sessions:
        existing_report = AttendanceReport.objects.filter(session=session).first()
        if existing_report:
            session.is_closed = True
            session.ended_at = existing_report.session_end
            session.save(update_fields=['is_closed', 'ended_at'])
            closed_reports.append(existing_report)
            continue

        report = generate_attendance_report_for_session(session, session_end=event_time, settings_obj=settings_obj)
        closed_reports.append(report)

    return closed_reports


def _get_open_session_for_classroom(classroom):
    return Session.objects.filter(classroom=classroom, is_closed=False).order_by('-start_time').first()


def _update_classroom_status(classroom, data, event_time):
    updated_fields = []

    field_map = {
        'occupied': 'occupied',
        'lights_on': 'lights_on',
        'door': 'door',
        'projector_on': 'projector_on',
        'smoke_detected': 'smoke_detected',
        'danger_indicator': 'danger_indicator',
    }

    for payload_key, model_field in field_map.items():
        parsed = _bool_or_none(data.get(payload_key))
        if parsed is not None and getattr(classroom, model_field) != parsed:
            setattr(classroom, model_field, parsed)
            updated_fields.append(model_field)

    if updated_fields:
        classroom.last_activity_at = event_time
        updated_fields.append('last_activity_at')

        if classroom.occupied and not classroom.session_started_at:
            classroom.session_started_at = event_time
            updated_fields.append('session_started_at')

        classroom.save(update_fields=updated_fields)


def _get_or_create_open_session(classroom, event_time, teacher=None, force_new=False):
    if force_new:
        _close_open_sessions_for_classroom(classroom, event_time)

    session = _get_open_session_for_classroom(classroom)
    if session:
        if teacher and teacher.role == 'PROF' and not session.teacher:
            session.teacher = teacher
            session.save(update_fields=['teacher'])
        return session

    settings_obj = get_system_settings()
    expected_time = event_time + timedelta(minutes=settings_obj.auto_finish_minutes)
    return Session.objects.create(
        classroom=classroom,
        teacher=teacher if teacher and teacher.role == 'PROF' else None,
        start_time=event_time,
        expected_report_time=expected_time,
    )


def _sync_session_from_rfids(classroom, data, event_time):
    teacher_rfid = data.get('teacher_rfid') or data.get('staff_rfid')
    student_rfids = _normalize_student_rfids(data)
    force_new_session = _is_new_session_request(data)
    activity_detected = False
    staff_member = None
    open_session = _get_open_session_for_classroom(classroom)

    if teacher_rfid:
        staff_member = Staff.objects.filter(rfid_number=str(teacher_rfid).strip()).first()
        if staff_member:
            activity_detected = True
        else:
            logger.warning('Unknown staff RFID received: %s', teacher_rfid)

        if open_session and open_session.teacher_id and staff_member and open_session.teacher_id != staff_member.id:
            _close_open_sessions_for_classroom(classroom, event_time)
            open_session = None

    session = None
    if staff_member or student_rfids or force_new_session:
        session = _get_or_create_open_session(
            classroom,
            event_time,
            teacher=staff_member,
            force_new=force_new_session,
        )

    if staff_member and session and session.teacher_id != staff_member.id:
        session.teacher = staff_member
        session.save(update_fields=['teacher'])

    if student_rfids:
        students = list(Student.objects.filter(rfid_number__in=student_rfids))
        if students:
            session.students.add(*students)
            activity_detected = True
        missing = sorted(set(student_rfids) - {s.rfid_number for s in students})
        if missing:
            logger.warning('Unknown student RFIDs received: %s', ', '.join(missing))

    if activity_detected:
        update_fields = ['last_activity_at']
        classroom.last_activity_at = event_time
        if not classroom.session_started_at:
            classroom.session_started_at = event_time
            update_fields.append('session_started_at')
        if not classroom.occupied:
            classroom.occupied = True
            update_fields.append('occupied')
        classroom.save(update_fields=update_fields)

    if force_new_session and not activity_detected:
        update_fields = ['last_activity_at', 'occupied', 'session_started_at']
        classroom.last_activity_at = event_time
        classroom.occupied = True
        classroom.session_started_at = event_time
        classroom.save(update_fields=update_fields)

    return activity_detected


def process_mqtt_payload(topic, payload):
    try:
        decoded = payload.decode('utf-8') if isinstance(payload, (bytes, bytearray)) else str(payload)
        data = json.loads(decoded) if decoded else {}
        if not isinstance(data, dict):
            logger.warning('Ignoring MQTT payload that is not a JSON object. topic=%s', topic)
            return
    except Exception:
        logger.exception('Failed to parse MQTT payload. topic=%s', topic)
        return

    event_time = _resolve_timestamp(data)

    with transaction.atomic():
        classroom = _resolve_classroom(data, topic)
        if not classroom:
            logger.warning('MQTT message ignored because classroom could not be resolved. topic=%s', topic)
            return

        _update_classroom_status(classroom, data, event_time)
        had_activity = _sync_session_from_rfids(classroom, data, event_time)

    if had_activity:
        auto_finish_active_classrooms()


def _should_start_mqtt_listener():
    if not getattr(settings, 'DASHBOARD_MQTT_ENABLED', False):
        return False

    if len(sys.argv) > 1 and sys.argv[1] == 'runserver' and os.environ.get('RUN_MAIN') != 'true':
        return False

    management_commands_without_listener = {
        'makemigrations',
        'migrate',
        'collectstatic',
        'shell',
        'dbshell',
        'createsuperuser',
        'check',
        'test',
        'loaddata',
        'dumpdata',
    }
    if len(sys.argv) > 1 and sys.argv[1] in management_commands_without_listener:
        return False

    return True


def _mqtt_loop():
    broker_host = getattr(settings, 'DASHBOARD_MQTT_BROKER_HOST', '127.0.0.1')
    broker_port = int(getattr(settings, 'DASHBOARD_MQTT_BROKER_PORT', 1883))
    keepalive = int(getattr(settings, 'DASHBOARD_MQTT_KEEPALIVE_SECONDS', 60))
    topic = getattr(settings, 'DASHBOARD_MQTT_TOPIC', 'smartclass/#')
    username = getattr(settings, 'DASHBOARD_MQTT_USERNAME', '')
    password = getattr(settings, 'DASHBOARD_MQTT_PASSWORD', '')
    reconnect_delay = int(getattr(settings, 'DASHBOARD_MQTT_RECONNECT_DELAY_SECONDS', 3))

    def on_connect(client, _userdata, _flags, rc):
        if rc == 0:
            client.subscribe(topic)
            logger.info('MQTT connected. host=%s port=%s topic=%s', broker_host, broker_port, topic)
        else:
            logger.warning('MQTT connection failed with rc=%s', rc)

    def on_message(_client, _userdata, msg):
        process_mqtt_payload(msg.topic, msg.payload)

    while True:
        try:
            client = mqtt.Client()
            if username:
                client.username_pw_set(username=username, password=password or None)
            client.on_connect = on_connect
            client.on_message = on_message
            client.connect(broker_host, broker_port, keepalive)
            client.loop_forever(retry_first_connection=True)
        except Exception:
            logger.exception('MQTT listener crashed; reconnecting in %ss.', reconnect_delay)
            time.sleep(reconnect_delay)


def start_mqtt_listener():
    global _mqtt_started

    if not _should_start_mqtt_listener():
        return

    with _mqtt_lock:
        if _mqtt_started:
            return

        thread = threading.Thread(target=_mqtt_loop, name='dashboard-mqtt-listener', daemon=True)
        thread.start()
        _mqtt_started = True
