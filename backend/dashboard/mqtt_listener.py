import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, time as dt_time, timedelta

import paho.mqtt.client as mqtt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AttendanceReport, ClassTimetableSlot, Classroom, ImmediateTeacherAccessGrant, Session, Staff, Student, StudentSessionAttendance
from .mqtt_commands import publish_custom_topic
from .reporting import auto_finish_active_classrooms, generate_attendance_report_for_session, get_system_settings

logger = logging.getLogger(__name__)

_mqtt_started = False
_mqtt_lock = threading.Lock()
TIMETABLE_SLOT_STARTS = [
    dt_time(8, 0),
    dt_time(9, 30),
    dt_time(11, 0),
    dt_time(12, 30),
    dt_time(14, 0),
    dt_time(15, 30),
]
TIMETABLE_SLOT_DURATION_MINUTES = 90


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


def _is_teacher_access_request(topic, data):
    if '/access/response' in topic:
        return False

    command = str(data.get('command', '')).strip().lower()
    event = str(data.get('event', '')).strip().lower()
    request = str(data.get('request', '')).strip().lower()
    message_type = str(data.get('type', '')).strip().lower()

    return (
        topic.endswith('/access/request')
        or command in {'teacher_access_check', 'teacher_authorization_check'}
        or event in {'teacher_access_request', 'teacher_authorization_request'}
        or request in {'teacher_access', 'teacher_authorization'}
        or message_type in {'teacher_access_request', 'teacher_authorization_request'}
    )


def _is_student_door_delay_request(topic, data):
    if '/door-delay/response' in topic:
        return False

    if topic.endswith('/door-delay/request'):
        return True

    command = str(data.get('command', '')).strip().lower()
    event = str(data.get('event', '')).strip().lower()
    request = str(data.get('request', '')).strip().lower()
    message_type = str(data.get('type', '')).strip().lower()

    return (
        command in {'door_delay_request', 'student_delay_request'}
        or event in {'door_delay_request', 'student_delay_request'}
        or request in {'door_delay', 'student_delay'}
        or message_type in {'door_delay_request', 'student_delay_request'}
    )


def _is_attendance_request(topic, data):
    if '/attendance/response' in topic:
        return False

    if topic.endswith('/attendance/request'):
        return True

    command = str(data.get('command', '')).strip().lower()
    event = str(data.get('event', '')).strip().lower()
    request = str(data.get('request', '')).strip().lower()
    message_type = str(data.get('type', '')).strip().lower()

    return (
        command in {'attendance_request', 'student_attendance'}
        or event in {'attendance_request', 'student_attendance'}
        or request in {'attendance', 'student_attendance'}
        or message_type in {'attendance_request', 'student_attendance'}
    )



def _resolve_response_topic(topic, payload_data, classroom):
    explicit_topic = str(payload_data.get('response_topic', '')).strip()
    if explicit_topic:
        return explicit_topic

    if topic.endswith('/door-delay/request'):
        return f"{topic[:-len('request')]}response"

    if topic.endswith('/access/request'):
        return f"{topic[:-len('request')]}response"

    if classroom:
        return f'smartclass/classrooms/{classroom.name}/access/response'

    return 'smartclass/access/response'


def _slot_bounds(reference_date, slot_index):
    slot_start_naive = datetime.combine(reference_date, TIMETABLE_SLOT_STARTS[slot_index])
    slot_start = timezone.make_aware(slot_start_naive, timezone.get_current_timezone())
    slot_end = slot_start + timedelta(minutes=TIMETABLE_SLOT_DURATION_MINUTES)
    return slot_start, slot_end


def _evaluate_teacher_access(classroom, teacher_rfid, event_time, request_id=None):
    checked_at = timezone.localtime(event_time)
    payload = {
        'event': 'teacher_access_response',
        'request_id': request_id,
        'approved': False,
        'classroom_id': classroom.id,
        'classroom_name': classroom.name,
        'checked_at': checked_at.isoformat(),
    }

    if not teacher_rfid:
        payload['reason'] = 'missing_teacher_rfid'
        return payload

    teacher = Staff.objects.filter(rfid_number=str(teacher_rfid).strip(), role='PROF').first()
    if not teacher:
        admin_teacher = Staff.objects.filter(rfid_number=str(teacher_rfid).strip(), role='ADMIN').first()
        if admin_teacher:
            payload.update(
                {
                    'approved': True,
                    'reason': 'authorized_admin_override',
                    'teacher_id': admin_teacher.id,
                    'teacher_name': admin_teacher.name,
                    'teacher_rfid': admin_teacher.rfid_number,
                    'access_window_minutes': 0,
                }
            )
            return payload

    if not teacher:
        payload['reason'] = 'teacher_not_found'
        payload['teacher_rfid'] = str(teacher_rfid).strip()
        return payload

    settings_obj = get_system_settings()
    window_minutes = settings_obj.teacher_access_window_minutes or 10
    payload['teacher_id'] = teacher.id
    payload['teacher_name'] = teacher.name
    payload['teacher_rfid'] = teacher.rfid_number
    payload['access_window_minutes'] = window_minutes

    immediate_access_grant = ImmediateTeacherAccessGrant.objects.filter(
        teacher=teacher,
        is_active=True,
        expires_at__gte=event_time,
    ).filter(
        classroom__isnull=True,
    ).order_by('-granted_at').first()

    if not immediate_access_grant:
        immediate_access_grant = ImmediateTeacherAccessGrant.objects.filter(
            teacher=teacher,
            classroom=classroom,
            is_active=True,
            expires_at__gte=event_time,
        ).order_by('-granted_at').first()

    if immediate_access_grant:
        payload.update(
            {
                'approved': True,
                'reason': 'authorized_immediate_override',
                'override_expires_at': timezone.localtime(immediate_access_grant.expires_at).isoformat(),
                'override_scope': immediate_access_grant.classroom.name if immediate_access_grant.classroom_id else 'all_classrooms',
            }
        )
        return payload

    weekday = checked_at.weekday()
    teacher_slots = list(
        ClassTimetableSlot.objects.filter(
            classroom=classroom,
            weekday=weekday,
            teacher=teacher,
        ).order_by('slot_index')
    )

    if not teacher_slots:
        payload['reason'] = 'no_timetable_slot_for_teacher'
        payload['weekday'] = weekday
        return payload

    closest_slot = None
    closest_delta_minutes = None

    for slot in teacher_slots:
        slot_start, slot_end = _slot_bounds(checked_at.date(), slot.slot_index)
        delta_minutes = abs((event_time - slot_start).total_seconds()) / 60.0
        if closest_delta_minutes is None or delta_minutes < closest_delta_minutes:
            closest_delta_minutes = delta_minutes
            closest_slot = (slot, slot_start, slot_end)

        if delta_minutes <= window_minutes:
            payload.update(
                {
                    'approved': True,
                    'reason': 'authorized_in_time_window',
                    'weekday': weekday,
                    'slot_index': slot.slot_index,
                    'slot_label': slot.get_slot_index_display(),
                    'slot_start': slot_start.isoformat(),
                    'slot_end': slot_end.isoformat(),
                    'subject': slot.subject,
                }
            )
            return payload

    if closest_slot:
        slot, slot_start, slot_end = closest_slot
        payload.update(
            {
                'reason': 'outside_allowed_time_window',
                'weekday': weekday,
                'closest_slot_index': slot.slot_index,
                'closest_slot_label': slot.get_slot_index_display(),
                'closest_slot_start': slot_start.isoformat(),
                'closest_slot_end': slot_end.isoformat(),
                'minutes_from_start': round(closest_delta_minutes, 2),
            }
        )

    return payload


def _create_session_from_teacher_access(classroom, response_payload, event_time):
    """
    Create a session when teacher access is approved.
    Session type and access type determined by the reason for approval:
    - inspection session for admin_override (no time restrictions)
    - class session with out_of_schedule access for immediate_override
    - class session with timetable access for in_time_window
    """
    reason = response_payload.get('reason', '')
    teacher_id = response_payload.get('teacher_id')
    
    if not teacher_id:
        return
    
    teacher = Staff.objects.filter(id=teacher_id).first()
    if not teacher:
        return
    
    # Determine session type and access type based on reason
    if reason == 'authorized_admin_override':
        session_type = 'inspection'
        access_type = 'none'
    elif reason == 'authorized_immediate_override':
        session_type = 'class'
        access_type = 'out_of_schedule'
    elif reason == 'authorized_in_time_window':
        session_type = 'class'
        access_type = 'timetable'
    else:
        session_type = 'class'
        access_type = 'none'
    
    # Close any existing open sessions to start fresh
    _close_open_sessions_for_classroom(classroom, event_time)
    
    settings_obj = get_system_settings()
    expected_time = event_time + timedelta(minutes=settings_obj.auto_finish_minutes)
    
    session_kwargs = {
        'classroom': classroom,
        'teacher': teacher if teacher.role in {'PROF', 'ADMIN'} else None,
        'start_time': event_time,
        'session_type': session_type,
        'access_type': access_type,
    }

    if session_type == 'inspection':
        session_kwargs.update(
            {
                'expected_report_time': None,
                'ended_at': event_time,
                'is_closed': True,
            }
        )
    else:
        session_kwargs['expected_report_time'] = expected_time

    Session.objects.create(**session_kwargs)


def _handle_teacher_access_request(topic, data, event_time):
    classroom = _resolve_classroom(data, topic)
    response_topic = _resolve_response_topic(topic, data, classroom)

    if not classroom:
        response_payload = {
            'event': 'teacher_access_response',
            'request_id': data.get('request_id'),
            'approved': False,
            'reason': 'classroom_not_found',
            'checked_at': timezone.localtime(event_time).isoformat(),
        }
    else:
        teacher_rfid = data.get('teacher_rfid') or data.get('staff_rfid') or data.get('rfid_number')
        response_payload = _evaluate_teacher_access(
            classroom=classroom,
            teacher_rfid=teacher_rfid,
            event_time=event_time,
            request_id=data.get('request_id'),
        )

        if response_payload.get('approved'):
            _create_session_from_teacher_access(
                classroom=classroom,
                response_payload=response_payload,
                event_time=event_time,
            )

    try:
        publish_custom_topic(response_topic, response_payload)
    except Exception:
        logger.exception('Failed to publish teacher access response. topic=%s payload=%s', response_topic, response_payload)


def _handle_student_door_delay_request(topic, data, event_time):
    classroom = _resolve_classroom(data, topic)
    response_topic = _resolve_response_topic(topic, data, classroom)

    if not classroom:
        response_payload = 0
    else:
        settings_obj = get_system_settings()
        response_payload = int(settings_obj.student_door_close_delay_minutes)

    try:
        publish_custom_topic(response_topic, response_payload)
    except Exception:
        logger.exception('Failed to publish student door delay response. topic=%s payload=%s', response_topic, response_payload)


def _handle_attendance_request(topic, data, event_time):
    """
    Handle student attendance request from the device.
    Records when each student arrives at the session.
    """
    classroom = _resolve_classroom(data, topic)

    if not classroom:
        logger.warning('Attendance request received but classroom could not be resolved. topic=%s', topic)
        return

    session = _get_open_session_for_classroom(classroom)
    if not session:
        logger.warning('Attendance request received but no open session found for classroom %s. topic=%s', classroom.name, topic)
        return

    student_rfids = _normalize_student_rfids(data)
    if student_rfids:
        students = list(Student.objects.filter(rfid_number__in=student_rfids))
        if students:
            attendance_records = []
            for student in students:
                # Create or get attendance record with arrival time
                attendance, created = StudentSessionAttendance.objects.get_or_create(
                    session=session,
                    student=student,
                    defaults={'arrival_time': event_time}
                )
                attendance_records.append(attendance)
                
                # Also ensure student is in the session's M2M relationship
                session.students.add(student)
            
            logger.info('Recorded attendance for %d students in session %d', len(attendance_records), session.id)
            for attendance in attendance_records:
                logger.info('Student %s arrived at %s', attendance.student.name, attendance.arrival_time)

            missing = sorted(set(student_rfids) - {s.rfid_number for s in students})
            if missing:
                logger.warning('Unknown student RFIDs in attendance request: %s', ', '.join(missing))
        else:
            logger.warning('No students found for provided RFIDs in attendance request. topic=%s', topic)
    else:
        logger.warning('Attendance request received but no student RFIDs provided. topic=%s', topic)



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

    event_time = timezone.now()

    if _is_teacher_access_request(topic, data):
        _handle_teacher_access_request(topic, data, event_time)
        return

    if _is_student_door_delay_request(topic, data):
        _handle_student_door_delay_request(topic, data, event_time)
        return

    if _is_attendance_request(topic, data):
        _handle_attendance_request(topic, data, event_time)
        return

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
    username = getattr(settings, 'DASHBOARD_MQTT_USERNAME', '')
    password = getattr(settings, 'DASHBOARD_MQTT_PASSWORD', '')
    reconnect_delay = int(getattr(settings, 'DASHBOARD_MQTT_RECONNECT_DELAY_SECONDS', 3))

    def on_message(_client, _userdata, msg):
        process_mqtt_payload(msg.topic, msg.payload)

    while True:
        try:
            settings_obj = get_system_settings()
            broker_host = settings_obj.mqtt_broker_host or getattr(settings, 'DASHBOARD_MQTT_BROKER_HOST', '127.0.0.1')
            broker_port = int(settings_obj.mqtt_broker_port or getattr(settings, 'DASHBOARD_MQTT_BROKER_PORT', 1883))
            keepalive = int(getattr(settings, 'DASHBOARD_MQTT_KEEPALIVE_SECONDS', 60))
            topic = settings_obj.mqtt_topic_wildcard or getattr(settings, 'DASHBOARD_MQTT_TOPIC', 'smartclass/#')

            def on_connect(client, _userdata, _flags, rc):
                if rc == 0:
                    client.subscribe(topic)
                    logger.info('MQTT connected. host=%s port=%s topic=%s', broker_host, broker_port, topic)
                else:
                    logger.warning('MQTT connection failed with rc=%s', rc)

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
