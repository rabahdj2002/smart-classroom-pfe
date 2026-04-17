from django.shortcuts import render, redirect
from django.conf import settings
from django.db.models import Q
from django.db import IntegrityError
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import Student, Staff, Classroom, AttendanceReport, Session, SystemSettings
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode
import json

from .reporting import (
    auto_finish_active_classrooms,
    build_report_pdf_attachment,
    generate_attendance_report_for_session,
    get_system_settings,
    maybe_email_report,
)
from .mqtt_commands import publish_classroom_command


def _is_portal_admin(user):
    return user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser)


def portal_admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")

        if not _is_portal_admin(request.user):
            logout(request)
            messages.error(request, 'This account is not allowed to access the portal.')
            return redirect('login')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def login_view(request):
    if _is_portal_admin(request.user):
        return redirect('dashboard')

    if request.user.is_authenticated and request.user.is_superuser:
        logout(request)
        messages.error(request, 'This account is not allowed to access the portal.')

    error = ''
    next_url = request.GET.get('next') or '/'

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '/')

        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = '/'

        user = authenticate(request, username=username, password=password)
        if user and _is_portal_admin(user):
            login(request, user)
            return redirect(next_url)

        error = 'Invalid credentials or unauthorized account.'

    return render(request, 'dashboard/login.html', {'error': error, 'next': next_url})


@portal_admin_required
def logout_view(request):
    logout(request)
    return redirect('login')


@portal_admin_required
def personal_info(request):
    errors = []
    success_message = ''
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()

        if action == 'profile':
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()

            if not email:
                errors.append('Email is required.')

            if email:
                duplicate_email = (
                    request.user.__class__.objects.exclude(pk=request.user.pk)
                    .filter(email=email)
                    .exists()
                )
                if duplicate_email:
                    errors.append('This email is already used by another account.')

            if not errors:
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.email = email
                request.user.save()
                success_message = 'Personal information updated successfully.'

        elif action == 'password':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                success_message = 'Password changed successfully.'
            else:
                for field_errors in password_form.errors.values():
                    errors.extend(field_errors)

    context = {
        'errors': errors,
        'success_message': success_message,
        'password_form': password_form,
    }
    return render(request, 'dashboard/personal_info.html', context)


@portal_admin_required
def mqtt_docs(request):
    settings_obj = get_system_settings()
    broker_host = settings_obj.mqtt_broker_host or getattr(settings, 'DASHBOARD_MQTT_BROKER_HOST', '127.0.0.1')
    broker_port = settings_obj.mqtt_broker_port or getattr(settings, 'DASHBOARD_MQTT_BROKER_PORT', 1883)
    topic_wildcard = settings_obj.mqtt_topic_wildcard or getattr(settings, 'DASHBOARD_MQTT_TOPIC', 'smartclass/#')
    default_events_topic = 'smartclass/classrooms/<classroom_name>/events'

    context = {
        'mqtt': {
            'broker_host': broker_host,
            'broker_port': broker_port,
            'topic_wildcard': topic_wildcard,
            'default_events_topic': default_events_topic,
            'username_set': bool(getattr(settings, 'DASHBOARD_MQTT_USERNAME', '')),
            'keepalive': getattr(settings, 'DASHBOARD_MQTT_KEEPALIVE_SECONDS', 60),
            'reconnect_delay': getattr(settings, 'DASHBOARD_MQTT_RECONNECT_DELAY_SECONDS', 3),
        }
    }
    return render(request, 'dashboard/mqtt_docs.html', context)


def _parse_bool(post_data, key):
    return post_data.get(key) in ['on', 'true', '1', 'yes']
    
@portal_admin_required
def dash(request):
    today = timezone.now().date()
    system_settings = get_system_settings()

    # Auto-finish expired classroom sessions before loading dashboard stats.
    auto_finish_active_classrooms()
    
    # Basic counts
    total_students = Student.objects.count()
    total_staff = Staff.objects.count()
    total_classrooms = Classroom.objects.count()
    total_attendance_today = Session.objects.filter(start_time__date=today).count()
    
    # Classroom status and warnings
    all_classrooms = Classroom.objects.all()
    danger_classrooms = list(all_classrooms.filter(danger_indicator=True))
    smoke_alert_classrooms = list(all_classrooms.filter(smoke_detected=True)) if system_settings.smoke_alert_enabled else []

    smoke_alert_classrooms = [c for c in smoke_alert_classrooms if c not in danger_classrooms]
    
    # Current usage
    classroom_status = []
    for classroom in all_classrooms:
        today_sessions = Session.objects.filter(
            classroom=classroom, 
            start_time__date=today
        ).count()

        used_today = classroom.occupied
        
        status = "danger" if classroom in danger_classrooms else ("smoke" if classroom in smoke_alert_classrooms else "normal")
        
        classroom_status.append({
            'id': classroom.id,
            'name': classroom.name,
            'today_sessions': today_sessions,
            'used_today': used_today,
            'occupied': classroom.occupied,
            'lights_on': classroom.lights_on,
            'projector_on': classroom.projector_on,
            'door': classroom.door,
            'smoke_detected': classroom.smoke_detected,
            'status': status,
        })
    
    # Today's hourly activity
    hourly_attendance = [0] * 24
    hourly_labels = []
    for hour in range(24):
        hour_attendance = Session.objects.filter(
            start_time__date=today,
            start_time__hour=hour,
        ).count()
        
        hourly_attendance[hour] = hour_attendance
        hourly_labels.append(f"{hour:02d}:00")
    
    # Weekly trends (last 7 days)
    weekly_labels = []
    weekly_attendance = []
    weekly_classrooms_used = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_attendance = Session.objects.filter(start_time__date=day).count()
        day_classrooms = Session.objects.filter(start_time__date=day).values('classroom').distinct().count()
        
        weekly_labels.append(day.strftime('%a'))
        weekly_attendance.append(day_attendance)
        weekly_classrooms_used.append(day_classrooms)
    
    # Peak hours analysis
    peak_hour = hourly_attendance.index(max(hourly_attendance)) if hourly_attendance else 0
    peak_hour_label = f"{peak_hour:02d}:00 - {(peak_hour + 1) % 24:02d}:00"
    peak_hour_sessions = hourly_attendance[peak_hour]
    
    # Off-peak hours analysis
    min_hour = hourly_attendance.index(min(hourly_attendance)) if hourly_attendance else 0
    
    # Overall statistics
    used_classrooms = sum(1 for c in classroom_status if c['used_today'])
    unused_classrooms = total_classrooms - used_classrooms
    avg_occupancy = (used_classrooms / total_classrooms) * 100 if total_classrooms else 0
    
    context = {
        'total_students': total_students,
        'total_staff': total_staff,
        'total_classrooms': total_classrooms,
        'total_attendance_today': total_attendance_today,
        'classrooms': all_classrooms,
        'classroom_status': classroom_status,
        'danger_classrooms': danger_classrooms,
        'smoke_alert_classrooms': smoke_alert_classrooms,
        'has_warnings': len(danger_classrooms) > 0 or len(smoke_alert_classrooms) > 0,
        'used_classrooms': used_classrooms,
        'unused_classrooms': unused_classrooms,
        'avg_occupancy': round(avg_occupancy, 1),
        'peak_hour_label': peak_hour_label,
        'peak_hour_sessions': peak_hour_sessions,
        'hourly_labels_json': json.dumps(hourly_labels),
        'hourly_attendance_json': json.dumps(hourly_attendance),
        'weekly_labels_json': json.dumps(weekly_labels),
        'weekly_attendance_json': json.dumps(weekly_attendance),
        'weekly_classrooms_json': json.dumps(weekly_classrooms_used),
        'smoke_alert_enabled': system_settings.smoke_alert_enabled,
        'today': today.strftime('%A, %B %d, %Y'),
    }
    
    return render(request, 'dashboard.html', context)


@portal_admin_required
def classes(request):
    settings_obj = get_system_settings()
    query = request.GET.get('q', '').strip()
    usage = request.GET.get('usage', '').strip()
    lights = request.GET.get('lights', '').strip()
    projector = request.GET.get('projector', '').strip()
    door = request.GET.get('door', '').strip()
    page_number = request.GET.get('page', '1').strip()

    classrooms = Classroom.objects.all()
    if query:
        classrooms = classrooms.filter(name__icontains=query)
    if usage == 'used':
        classrooms = classrooms.filter(occupied=True)
    elif usage == 'unused':
        classrooms = classrooms.filter(occupied=False)

    if lights == 'on':
        classrooms = classrooms.filter(lights_on=True)
    elif lights == 'off':
        classrooms = classrooms.filter(lights_on=False)

    if projector == 'on':
        classrooms = classrooms.filter(projector_on=True)
    elif projector == 'off':
        classrooms = classrooms.filter(projector_on=False)

    if door == 'open':
        classrooms = classrooms.filter(door=True)
    elif door == 'closed':
        classrooms = classrooms.filter(door=False)

    classrooms = classrooms.order_by('name')

    paginator = Paginator(classrooms, settings_obj.default_list_page_size)
    page_obj = paginator.get_page(page_number)

    classroom_list = []
    for room in page_obj.object_list:
        today_sessions = Session.objects.filter(
            classroom=room,
            start_time__date=timezone.now().date(),
        ).count()
        classroom_list.append({
            'id': room.id,
            'name': room.name,
            'lights_on': room.lights_on,
            'projector_on': room.projector_on,
            'door': room.door,
            'today_sessions': today_sessions,
            'used_today': room.occupied,
            'occupied': room.occupied,
        })

    filters = {
        'q': query,
        'usage': usage,
        'lights': lights,
        'projector': projector,
        'door': door,
    }
    pagination_query = urlencode({key: value for key, value in filters.items() if value})

    context = {
        'classrooms': classroom_list,
        'settings_obj': settings_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'filters': filters,
    }
    return render(request, 'dashboard/classes.html', context)


@portal_admin_required
def bulk_delete_classes(request):
    if request.method != 'POST':
        return redirect('classes')

    settings_obj = get_system_settings()
    if not settings_obj.allow_bulk_actions:
        messages.error(request, 'Bulk actions are disabled by system settings.')
        return redirect('classes')

    raw_ids = request.POST.getlist('class_ids')
    class_ids = []
    for raw_id in raw_ids:
        try:
            class_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not class_ids:
        messages.warning(request, 'Select at least one classroom to delete.')
        return redirect('classes')

    classes_to_delete = Classroom.objects.filter(id__in=class_ids)
    deleted_count = classes_to_delete.count()
    if deleted_count == 0:
        messages.warning(request, 'No matching classrooms were found for deletion.')
        return redirect('classes')

    classes_to_delete.delete()
    messages.success(request, f'{deleted_count} classroom(s) deleted successfully.')
    return redirect('classes')


@portal_admin_required
def classroom_detail(request, id):
    classroom = Classroom.objects.filter(id=id).first()
    if not classroom:
        return render(request, '404.html', status=404)
    system_settings = get_system_settings()

    today = timezone.now().date()
    today_sessions = Session.objects.filter(classroom=classroom, start_time__date=today).count()

    start_date = today - timedelta(days=29)
    usage_labels = []
    usage_student_values = []
    usage_teacher_values = []

    for n in range(30):
        day = start_date + timedelta(days=n)

        student_count = (
            Session.objects.filter(classroom=classroom, start_time__date=day)
            .values('students')
            .distinct()
            .count()
        )

        teacher_count = (
            Session.objects.filter(classroom=classroom, start_time__date=day)
            .exclude(teacher=None)
            .values('teacher')
            .distinct()
            .count()
        )

        usage_labels.append(day.strftime('%a'))
        usage_student_values.append(student_count)
        usage_teacher_values.append(teacher_count)

    weekly_student_sessions = sum(usage_student_values[-7:])
    weekly_teacher_sessions = sum(usage_teacher_values[-7:])

    # Calculate session counts for different periods
    start_date_7 = today - timedelta(days=6)  # Last 7 days including today
    start_date_30 = today - timedelta(days=29)  # Last 30 days including today
    
    weekly_sessions = Session.objects.filter(
        classroom=classroom, 
        start_time__date__gte=start_date_7,
        start_time__date__lte=today
    ).count()
    
    monthly_sessions = Session.objects.filter(
        classroom=classroom, 
        start_time__date__gte=start_date_30,
        start_time__date__lte=today
    ).count()

    has_smoke_alert = system_settings.smoke_alert_enabled and classroom.smoke_detected

    context = {
        'classroom': classroom,
        'today_sessions': today_sessions,
        'weekly_sessions': weekly_sessions,
        'monthly_sessions': monthly_sessions,
        'usage_labels_json': json.dumps(usage_labels),
        'usage_values_json': json.dumps(usage_student_values),
        'usage_teacher_values_json': json.dumps(usage_teacher_values),
        'weekly_student_sessions': weekly_student_sessions,
        'weekly_teacher_sessions': weekly_teacher_sessions,
        'has_smoke_alert': has_smoke_alert,
    }
    return render(request, 'dashboard/classroom_detail.html', context)


@portal_admin_required
def classroom_command(request, id):
    if request.method != 'POST':
        return redirect('classroom_detail', id=id)

    classroom = Classroom.objects.filter(id=id).first()
    if not classroom:
        return render(request, '404.html', status=404)

    action = request.POST.get('action', '').strip()

    command_map = {
        'lights_on': ('lights', True),
        'lights_off': ('lights', False),
        'projector_on': ('projector', True),
        'projector_off': ('projector', False),
        'clear_smoke': ('smoke_reset', True),
    }

    if action not in command_map:
        messages.error(request, 'Unknown classroom command.')
        return redirect('classroom_detail', id=id)

    command, value = command_map[action]

    try:
        publish_classroom_command(classroom, command, value)

        if action in {'lights_on', 'lights_off'}:
            classroom.lights_on = bool(value)
            classroom.save(update_fields=['lights_on'])
        elif action in {'projector_on', 'projector_off'}:
            classroom.projector_on = bool(value)
            classroom.save(update_fields=['projector_on'])
        elif action == 'clear_smoke':
            classroom.smoke_detected = False
            classroom.danger_indicator = False
            classroom.save(update_fields=['smoke_detected', 'danger_indicator'])

        messages.success(request, f'Command sent successfully: {action.replace("_", " ")}')
    except Exception as exc:
        messages.error(request, f'Failed to send command: {exc}')

    return redirect('classroom_detail', id=id)


@portal_admin_required
def temperature_settings(request):
    settings_obj = get_system_settings()
    errors = []
    success_message = ''
    mqtt_default_host = getattr(settings, 'DASHBOARD_MQTT_BROKER_HOST', '127.0.0.1')
    mqtt_default_port = getattr(settings, 'DASHBOARD_MQTT_BROKER_PORT', 1883)
    mqtt_default_topic = getattr(settings, 'DASHBOARD_MQTT_TOPIC', 'smartclass/#')

    if request.method == 'POST':
        auto_finish_enabled = _parse_bool(request.POST, 'auto_finish_enabled')
        allow_bulk_actions = _parse_bool(request.POST, 'allow_bulk_actions')
        show_kpi_badges = _parse_bool(request.POST, 'show_kpi_badges')
        ui_compact_mode = _parse_bool(request.POST, 'ui_compact_mode')
        email_reports_enabled = _parse_bool(request.POST, 'email_reports_enabled')
        smtp_use_tls = _parse_bool(request.POST, 'smtp_use_tls')
        mqtt_production_mode = _parse_bool(request.POST, 'mqtt_production_mode')

        cron_interval_minutes_raw = request.POST.get('cron_interval_minutes', '').strip()
        auto_finish_minutes_raw = request.POST.get('auto_finish_minutes', '').strip()
        default_list_page_size_raw = request.POST.get('default_list_page_size', '').strip()
        default_sessions_order = request.POST.get('default_sessions_order', '').strip()
        mqtt_broker_host = request.POST.get('mqtt_broker_host', '').strip()
        mqtt_broker_port_raw = request.POST.get('mqtt_broker_port', '').strip()
        mqtt_topic_wildcard = request.POST.get('mqtt_topic_wildcard', '').strip()
        smtp_host = request.POST.get('smtp_host', '').strip()
        smtp_port_raw = request.POST.get('smtp_port', '').strip()
        smtp_username = request.POST.get('smtp_username', '').strip()
        smtp_password = request.POST.get('smtp_password', '').strip()
        smtp_from_email = request.POST.get('smtp_from_email', '').strip()

        try:
            cron_interval_minutes = int(cron_interval_minutes_raw)
            if cron_interval_minutes <= 0:
                errors.append('Cron interval must be greater than 0 minutes.')
        except ValueError:
            errors.append('Cron interval must be a valid integer.')
            cron_interval_minutes = settings_obj.cron_interval_minutes

        try:
            auto_finish_minutes = int(auto_finish_minutes_raw)
            if auto_finish_minutes <= 0:
                errors.append('Auto-finish duration must be greater than 0 minutes.')
        except ValueError:
            errors.append('Auto-finish duration must be a valid integer.')
            auto_finish_minutes = settings_obj.auto_finish_minutes

        try:
            default_list_page_size = int(default_list_page_size_raw)
            if default_list_page_size < 10 or default_list_page_size > 200:
                errors.append('Default list page size must be between 10 and 200.')
        except ValueError:
            errors.append('Default list page size must be a valid integer.')
            default_list_page_size = settings_obj.default_list_page_size

        if default_sessions_order not in {'id_asc', 'id_desc'}:
            errors.append('Default sessions order is invalid.')
            default_sessions_order = settings_obj.default_sessions_order

        try:
            smtp_port = int(smtp_port_raw)
            if smtp_port <= 0:
                errors.append('SMTP port must be a positive number.')
        except ValueError:
            errors.append('SMTP port must be a valid integer.')
            smtp_port = settings_obj.smtp_port

        try:
            mqtt_broker_port = int(mqtt_broker_port_raw)
            if mqtt_broker_port <= 0:
                errors.append('MQTT broker port must be a positive number.')
        except ValueError:
            errors.append('MQTT broker port must be a valid integer.')
            mqtt_broker_port = settings_obj.mqtt_broker_port

        if not mqtt_broker_host:
            errors.append('MQTT broker address is required.')

        if not mqtt_topic_wildcard:
            errors.append('MQTT topic wildcard is required.')

        if mqtt_topic_wildcard and '#' in mqtt_topic_wildcard and not mqtt_topic_wildcard.endswith('/#') and mqtt_topic_wildcard != '#':
            errors.append('MQTT topic wildcard using # must end with /# (example: smartclass/#).')

        if mqtt_production_mode:
            mqtt_mode = 'production'
        else:
            mqtt_mode = 'test'

        if email_reports_enabled and not smtp_from_email:
            errors.append('From email is required when automatic report emails are enabled.')

        if not errors:
            settings_obj.auto_finish_enabled = auto_finish_enabled
            settings_obj.cron_interval_minutes = cron_interval_minutes
            settings_obj.auto_finish_minutes = auto_finish_minutes
            settings_obj.default_list_page_size = default_list_page_size
            settings_obj.default_sessions_order = default_sessions_order
            settings_obj.allow_bulk_actions = allow_bulk_actions
            settings_obj.show_kpi_badges = show_kpi_badges
            settings_obj.ui_compact_mode = ui_compact_mode
            settings_obj.mqtt_mode = mqtt_mode
            settings_obj.mqtt_broker_host = mqtt_broker_host
            settings_obj.mqtt_broker_port = mqtt_broker_port
            settings_obj.mqtt_topic_wildcard = mqtt_topic_wildcard
            settings_obj.email_reports_enabled = email_reports_enabled
            settings_obj.smtp_host = smtp_host
            settings_obj.smtp_port = smtp_port
            settings_obj.smtp_username = smtp_username
            if smtp_password:
                settings_obj.smtp_password = smtp_password
            settings_obj.smtp_use_tls = smtp_use_tls
            settings_obj.smtp_from_email = smtp_from_email
            settings_obj.save()

            # Apply new timing immediately (e.g., change from 90 to 10 minutes).
            auto_finish_active_classrooms()
            success_message = 'System settings updated successfully.'

    context = {
        'settings_obj': settings_obj,
        'errors': errors,
        'success_message': success_message,
        'mqtt_default_host': mqtt_default_host,
        'mqtt_default_port': mqtt_default_port,
        'mqtt_default_topic': mqtt_default_topic,
    }
    return render(request, 'dashboard/settings.html', context)


@portal_admin_required
def add_class(request):
    errors = []
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        occupied = bool(request.POST.get('occupied'))
        lights_on = bool(request.POST.get('lights_on'))
        projector_on = bool(request.POST.get('projector_on'))
        door = bool(request.POST.get('door'))
        smoke_detected = bool(request.POST.get('smoke_detected'))
        danger_indicator = bool(request.POST.get('danger_indicator'))

        if not name:
            errors.append('Name is required.')

        if not errors:
            Classroom.objects.create(
                name=name,
                occupied=occupied,
                lights_on=lights_on,
                projector_on=projector_on,
                door=door,
                smoke_detected=smoke_detected,
                danger_indicator=danger_indicator,
            )
            return redirect('classes')

        context = {
            'errors': errors,
            'form': {
                'name': name,
                'occupied': occupied,
                'lights_on': lights_on,
                'projector_on': projector_on,
                'door': door,
                'smoke_detected': smoke_detected,
                'danger_indicator': danger_indicator,
            },
        }

        return render(request, 'dashboard/classroom_add.html', context)

    context = {
        'errors': [],
        'form': {},
    }
    return render(request, 'dashboard/classroom_add.html', context)


@portal_admin_required
def add_student(request):
    errors = []
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        specialization = request.POST.get('specialization', '').strip()
        year_raw = request.POST.get('year', '').strip()
        student_card_id = request.POST.get('student_card_id', '').strip()
        rfid_number = request.POST.get('rfid_number', '').strip()

        if not name:
            errors.append('Name is required.')
        if not email:
            errors.append('Email is required.')
        if not specialization:
            errors.append('Specialization is required.')

        try:
            year = int(year_raw)
            if year <= 0:
                errors.append('Year must be a positive number.')
        except ValueError:
            errors.append('Year must be a number.')
            year = None

        if not student_card_id:
            errors.append('Student card ID is required.')
        if not rfid_number:
            errors.append('RFID number is required.')

        if not errors:
            Student.objects.create(
                name=name,
                email=email,
                specialization=specialization,
                year=year,
                student_card_id=student_card_id,
                rfid_number=rfid_number,
            )
            return redirect('students')

        context = {
            'errors': errors,
            'form': {
                'name': name,
                'email': email,
                'specialization': specialization,
                'year': year_raw,
                'student_card_id': student_card_id,
                'rfid_number': rfid_number,
            },
        }
        return render(request, 'dashboard/student_add.html', context)

    context = {
        'errors': [],
        'form': {},
    }
    return render(request, 'dashboard/student_add.html', context)


@portal_admin_required
def student_detail(request, id):
    student = Student.objects.filter(id=id).first()
    if not student:
        return render(request, '404.html', status=404)

    today = timezone.now().date()
    start_date = today - timedelta(days=29)

    attendance_labels = []
    attendance_values = []

    for n in range(30):
        day = start_date + timedelta(days=n)
        count = Session.objects.filter(students=student, start_time__date=day).count()
        attendance_labels.append(day.strftime('%b %d'))
        attendance_values.append(count)

    weekly_student_sessions = sum(attendance_values[-7:])
    recent_sessions = Session.objects.filter(students=student).select_related('classroom').order_by('-start_time')[:7]

    context = {
        'student': student,
        'attendance_labels_json': json.dumps(attendance_labels),
        'attendance_values_json': json.dumps(attendance_values),
        'weekly_student_sessions': weekly_student_sessions,
        'recent_sessions': recent_sessions,
    }
    return render(request, 'dashboard/student_detail.html', context)


@portal_admin_required
def students(request):
    settings_obj = get_system_settings()
    query = request.GET.get('q', '').strip()
    specialization = request.GET.get('specialization', '').strip()
    year = request.GET.get('year', '').strip()
    page_number = request.GET.get('page', '1').strip()

    student_list = Student.objects.all()
    if query:
        student_list = student_list.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(rfid_number__icontains=query)
            | Q(student_card_id__icontains=query)
        )
    if specialization:
        student_list = student_list.filter(specialization=specialization)
    if year:
        student_list = student_list.filter(year=year)

    student_list = student_list.order_by('name')
    paginator = Paginator(student_list, settings_obj.default_list_page_size)
    page_obj = paginator.get_page(page_number)

    filters = {
        'q': query,
        'specialization': specialization,
        'year': year,
    }
    pagination_query = urlencode({key: value for key, value in filters.items() if value})

    context = {
        'students': page_obj.object_list,
        'settings_obj': settings_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'filters': filters,
    }
    return render(request, 'dashboard/students.html', context)


@portal_admin_required
def bulk_delete_students(request):
    if request.method != 'POST':
        return redirect('students')

    settings_obj = get_system_settings()
    if not settings_obj.allow_bulk_actions:
        messages.error(request, 'Bulk actions are disabled by system settings.')
        return redirect('students')

    raw_ids = request.POST.getlist('student_ids')
    student_ids = []
    for raw_id in raw_ids:
        try:
            student_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not student_ids:
        messages.warning(request, 'Select at least one student to delete.')
        return redirect('students')

    students_to_delete = Student.objects.filter(id__in=student_ids)
    deleted_count = students_to_delete.count()
    if deleted_count == 0:
        messages.warning(request, 'No matching students were found for deletion.')
        return redirect('students')

    students_to_delete.delete()
    messages.success(request, f'{deleted_count} student(s) deleted successfully.')
    return redirect('students')


@portal_admin_required
def download_report_pdf(request, id):
    report = AttendanceReport.objects.select_related('classroom').filter(id=id).first()
    if not report:
        return render(request, '404.html', status=404)

    pdf_content = build_report_pdf_attachment(report)
    classroom_slug = slugify(report.classroom.name) or 'classroom'
    filename = f"attendance_report_{report.id}_{classroom_slug}.pdf"

    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@portal_admin_required
def email_report(request, id):
    if request.method != 'POST':
        return redirect('sessions')

    report = AttendanceReport.objects.select_related('session', 'classroom', 'teacher').filter(id=id).first()
    if not report:
        return render(request, '404.html', status=404)

    if not report.teacher or not report.teacher.email:
        messages.error(request, 'This report has no teacher email address to send to.')
        return redirect('session_detail', id=report.session_id)

    settings_obj = get_system_settings()
    if not settings_obj.smtp_host or not settings_obj.smtp_from_email:
        messages.error(request, 'SMTP host and From Email must be configured before sending reports.')
        return redirect('session_detail', id=report.session_id)

    maybe_email_report(report, settings_obj=settings_obj, force=True)

    if report.email_error:
        messages.error(request, f'Failed to send report: {report.email_error}')
    else:
        messages.success(request, 'Report emailed successfully.')

    return redirect('session_detail', id=report.session_id)


@portal_admin_required
def sessions(request):
    settings_obj = get_system_settings()
    classroom_id = request.GET.get('classroom', '').strip()
    teacher_query = request.GET.get('teacher', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    order = request.GET.get('order', settings_obj.default_sessions_order).strip()
    page_number = request.GET.get('page', '1').strip()

    if order not in {'id_asc', 'id_desc'}:
        order = settings_obj.default_sessions_order

    session_list = Session.objects.select_related('classroom', 'teacher').prefetch_related('report', 'students').all()

    if classroom_id:
        session_list = session_list.filter(classroom_id=classroom_id)
    if teacher_query:
        session_list = session_list.filter(
            Q(teacher__name__icontains=teacher_query)
            | Q(teacher__email__icontains=teacher_query)
        )
    if start_date:
        session_list = session_list.filter(start_time__date__gte=start_date)
    if end_date:
        session_list = session_list.filter(start_time__date__lte=end_date)

    if order == 'id_desc':
        session_list = session_list.order_by('-id')
    else:
        session_list = session_list.order_by('id')

    paginator = Paginator(session_list, settings_obj.default_list_page_size)
    page_obj = paginator.get_page(page_number)

    sessions_materialized = list(page_obj.object_list)
    for session in sessions_materialized:
        session.student_names = list(session.students.values_list('name', flat=True))

    filters = {
        'classroom': classroom_id,
        'teacher': teacher_query,
        'start_date': start_date,
        'end_date': end_date,
        'order': order,
    }
    pagination_query = urlencode({key: value for key, value in filters.items() if value})

    context = {
        'sessions': sessions_materialized,
        'settings_obj': settings_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'classrooms': Classroom.objects.order_by('name'),
        'filters': filters,
    }
    return render(request, 'dashboard/sessions.html', context)


def _sync_classroom_state(classroom):
    has_open = Session.objects.filter(classroom=classroom, is_closed=False).exists()
    if not has_open:
        classroom.occupied = False
        classroom.session_started_at = None
        classroom.last_activity_at = None
        classroom.save(update_fields=['occupied', 'session_started_at', 'last_activity_at'])


@portal_admin_required
def add_session(request):
    errors = []
    form = {'student_ids': []}

    if request.method == 'POST':
        classroom_id = request.POST.get('classroom_id', '').strip()
        teacher_id = request.POST.get('teacher_id', '').strip()
        start_time_raw = request.POST.get('start_time', '').strip()
        student_ids = request.POST.getlist('student_ids')

        form = {
            'classroom_id': classroom_id,
            'teacher_id': teacher_id,
            'start_time': start_time_raw,
            'student_ids': student_ids,
        }

        classroom = Classroom.objects.filter(id=classroom_id).first() if classroom_id else None
        teacher = Staff.objects.filter(id=teacher_id, role='PROF').first() if teacher_id else None
        selected_students = Student.objects.filter(id__in=student_ids).distinct() if student_ids else Student.objects.none()

        if not classroom:
            errors.append('A valid classroom is required.')

        start_time = parse_datetime(start_time_raw) if start_time_raw else None
        if not start_time:
            errors.append('A valid start time is required.')
        elif timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time, timezone.get_current_timezone())

        if classroom and Session.objects.filter(classroom=classroom, is_closed=False).exists():
            errors.append('This classroom already has an active session.')

        if not errors:
            settings_obj = get_system_settings()
            expected_report_time = start_time + timedelta(minutes=settings_obj.auto_finish_minutes)

            session = Session.objects.create(
                classroom=classroom,
                teacher=teacher,
                start_time=start_time,
                expected_report_time=expected_report_time,
                is_closed=False,
            )
            if selected_students.exists():
                session.students.add(*selected_students)

            classroom.occupied = True
            classroom.session_started_at = start_time
            classroom.last_activity_at = timezone.now()
            classroom.save(update_fields=['occupied', 'session_started_at', 'last_activity_at'])

            # If session is already overdue under current settings, generate report immediately.
            auto_finish_active_classrooms()
            return redirect('sessions')

    context = {
        'errors': errors,
        'form': form,
        'classrooms': Classroom.objects.order_by('name'),
        'teachers': Staff.objects.filter(role='PROF').order_by('name'),
        'students': Student.objects.order_by('name'),
        'back_url': '/sessions/',
    }
    return render(request, 'dashboard/session_add.html', context)


@portal_admin_required
def edit_session(request, id):
    session = Session.objects.select_related('classroom', 'teacher').prefetch_related('students').filter(id=id).first()
    if not session:
        return render(request, '404.html', status=404)

    if session.is_closed:
        messages.error(request, 'Closed sessions cannot be modified.')
        return redirect('session_detail', id=session.id)

    errors = []
    form = {
        'classroom_id': str(session.classroom_id),
        'teacher_id': str(session.teacher_id) if session.teacher_id else '',
        'start_time': timezone.localtime(session.start_time).strftime('%Y-%m-%dT%H:%M'),
        'student_ids': [str(student_id) for student_id in session.students.values_list('id', flat=True)],
    }

    if request.method == 'POST':
        classroom_id = request.POST.get('classroom_id', '').strip()
        teacher_id = request.POST.get('teacher_id', '').strip()
        start_time_raw = request.POST.get('start_time', '').strip()
        student_ids = request.POST.getlist('student_ids')

        form = {
            'classroom_id': classroom_id,
            'teacher_id': teacher_id,
            'start_time': start_time_raw,
            'student_ids': student_ids,
        }

        classroom = Classroom.objects.filter(id=classroom_id).first() if classroom_id else None
        teacher = Staff.objects.filter(id=teacher_id, role='PROF').first() if teacher_id else None
        selected_students = Student.objects.filter(id__in=student_ids).distinct() if student_ids else Student.objects.none()

        if not classroom:
            errors.append('A valid classroom is required.')

        start_time = parse_datetime(start_time_raw) if start_time_raw else None
        if not start_time:
            errors.append('A valid start time is required.')
        elif timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time, timezone.get_current_timezone())

        if classroom and Session.objects.filter(classroom=classroom, is_closed=False).exclude(id=session.id).exists():
            errors.append('This classroom already has another active session.')

        if not errors:
            settings_obj = get_system_settings()
            expected_report_time = start_time + timedelta(minutes=settings_obj.auto_finish_minutes)

            previous_classroom = session.classroom
            session.classroom = classroom
            session.teacher = teacher
            session.start_time = start_time
            session.expected_report_time = expected_report_time
            session.save(update_fields=['classroom', 'teacher', 'start_time', 'expected_report_time'])
            session.students.set(selected_students)

            classroom.occupied = True
            classroom.session_started_at = start_time
            classroom.last_activity_at = timezone.now()
            classroom.save(update_fields=['occupied', 'session_started_at', 'last_activity_at'])

            if previous_classroom.id != classroom.id:
                _sync_classroom_state(previous_classroom)

            auto_finish_active_classrooms()
            messages.success(request, 'Session updated successfully.')
            return redirect('session_detail', id=session.id)

    context = {
        'errors': errors,
        'form': form,
        'classrooms': Classroom.objects.order_by('name'),
        'teachers': Staff.objects.filter(role='PROF').order_by('name'),
        'students': Student.objects.order_by('name'),
        'page_title': f'Edit Session #{session.id}',
        'submit_label': 'Save Changes',
        'is_edit': True,
        'back_url': f'/sessions/{session.id}/',
    }
    return render(request, 'dashboard/session_add.html', context)


@portal_admin_required
def end_session(request, id):
    if request.method != 'POST':
        return redirect('sessions')

    session = Session.objects.select_related('classroom').filter(id=id).first()
    if not session:
        return render(request, '404.html', status=404)

    if session.is_closed:
        messages.info(request, 'Session is already closed.')
        return redirect('session_detail', id=session.id)

    now = timezone.now()
    generate_attendance_report_for_session(session, session_end=now)
    _sync_classroom_state(session.classroom)
    messages.success(request, 'Session ended and report generated.')
    return redirect('session_detail', id=session.id)


@portal_admin_required
def delete_session(request, id):
    if request.method != 'POST':
        return redirect('sessions')

    session = Session.objects.select_related('classroom').filter(id=id).first()
    if not session:
        return render(request, '404.html', status=404)

    classroom = session.classroom
    session.delete()
    _sync_classroom_state(classroom)
    messages.success(request, 'Session deleted successfully.')
    return redirect('sessions')


@portal_admin_required
def bulk_delete_sessions(request):
    if request.method != 'POST':
        return redirect('sessions')

    settings_obj = get_system_settings()
    if not settings_obj.allow_bulk_actions:
        messages.error(request, 'Bulk actions are disabled by system settings.')
        return redirect('sessions')

    raw_ids = request.POST.getlist('session_ids')
    session_ids = []
    for raw_id in raw_ids:
        try:
            session_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not session_ids:
        messages.warning(request, 'Select at least one session to delete.')
        return redirect('sessions')

    sessions_to_delete = list(
        Session.objects.select_related('classroom').filter(id__in=session_ids)
    )
    if not sessions_to_delete:
        messages.warning(request, 'No matching sessions were found for deletion.')
        return redirect('sessions')

    affected_classrooms = {session.classroom for session in sessions_to_delete}
    deleted_count = len(sessions_to_delete)

    Session.objects.filter(id__in=[session.id for session in sessions_to_delete]).delete()

    for classroom in affected_classrooms:
        _sync_classroom_state(classroom)

    messages.success(request, f'{deleted_count} session(s) deleted successfully.')
    return redirect('sessions')


@portal_admin_required
def session_detail(request, id):
    session = Session.objects.select_related('classroom', 'teacher').prefetch_related('report', 'students').filter(id=id).first()
    if not session:
        return render(request, '404.html', status=404)

    report = AttendanceReport.objects.filter(session=session).first()

    if report:
        total_students = report.total_students
        total_staff = report.total_staff
    else:
        total_students = session.students.count()
        total_staff = 1 if session.teacher else 0

    student_names = list(session.students.values_list('name', flat=True))

    context = {
        'session': session,
        'report': report,
        'total_students': total_students,
        'total_staff': total_staff,
        'student_names': student_names,
    }
    return render(request, 'dashboard/session_detail.html', context)


def _validate_staff_payload(payload, existing_staff=None):
    errors = []
    name = payload.get('name', '').strip()
    email = payload.get('email', '').strip()
    role = payload.get('role', '').strip()
    id_number = payload.get('id_number', '').strip()
    rfid_number = payload.get('rfid_number', '').strip()

    can_open_door = bool(payload.get('can_open_door'))
    can_control_lights = bool(payload.get('can_control_lights'))
    can_control_projector = bool(payload.get('can_control_projector'))
    can_manage_classrooms = bool(payload.get('can_manage_classrooms'))
    can_manage_staff = bool(payload.get('can_manage_staff'))

    if not name:
        errors.append('Name is required.')
    if not email:
        errors.append('Email is required.')
    if not role:
        errors.append('Role is required.')
    if not id_number:
        errors.append('ID number is required.')
    if not rfid_number:
        errors.append('RFID card serial code is required.')

    base_queryset = Staff.objects.all()
    if existing_staff:
        base_queryset = base_queryset.exclude(id=existing_staff.id)

    if email and base_queryset.filter(email=email).exists():
        errors.append('Email is already used by another staff member.')
    if id_number and base_queryset.filter(id_number=id_number).exists():
        errors.append('ID number is already used by another staff member.')
    if rfid_number and base_queryset.filter(rfid_number=rfid_number).exists():
        errors.append('RFID card serial code is already used by another staff member.')

    return {
        'errors': errors,
        'clean_data': {
            'name': name,
            'email': email,
            'role': role,
            'id_number': id_number,
            'rfid_number': rfid_number,
            'can_open_door': can_open_door,
            'can_control_lights': can_control_lights,
            'can_control_projector': can_control_projector,
            'can_manage_classrooms': can_manage_classrooms,
            'can_manage_staff': can_manage_staff,
        },
    }


@portal_admin_required
def staff(request):
    settings_obj = get_system_settings()
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    privilege = request.GET.get('privilege', '').strip()
    page_number = request.GET.get('page', '1').strip()

    staff_members = Staff.objects.all().order_by('name')

    if query:
        staff_members = staff_members.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(id_number__icontains=query)
            | Q(rfid_number__icontains=query)
        )

    if role:
        staff_members = staff_members.filter(role=role)

    privilege_map = {
        'door': 'can_open_door',
        'lights': 'can_control_lights',
        'projector': 'can_control_projector',
        'classrooms': 'can_manage_classrooms',
        'staff': 'can_manage_staff',
    }

    privilege_field = privilege_map.get(privilege)
    if privilege_field:
        staff_members = staff_members.filter(**{privilege_field: True})

    paginator = Paginator(staff_members, settings_obj.default_list_page_size)
    page_obj = paginator.get_page(page_number)

    filters = {
        'q': query,
        'role': role,
        'privilege': privilege,
    }
    pagination_query = urlencode({key: value for key, value in filters.items() if value})

    context = {
        'staff_members': page_obj.object_list,
        'settings_obj': settings_obj,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'role_choices': Staff.ROLE_CHOICES,
        'filters': filters,
    }
    return render(request, 'dashboard/staff.html', context)


@portal_admin_required
def add_staff(request):
    if request.method == 'POST':
        validation = _validate_staff_payload(request.POST)
        errors = validation['errors']
        clean_data = validation['clean_data']

        if not errors:
            try:
                Staff.objects.create(**clean_data)
                return redirect('staff')
            except IntegrityError:
                errors.append('Could not create staff member because one of the unique fields already exists.')

        context = {
            'errors': errors,
            'form': clean_data,
            'role_choices': Staff.ROLE_CHOICES,
            'page_title': 'Add Staff Member',
            'submit_label': 'Create Staff Member',
            'is_edit': False,
        }
        return render(request, 'dashboard/staff_form.html', context)

    context = {
        'errors': [],
        'form': {},
        'role_choices': Staff.ROLE_CHOICES,
        'page_title': 'Add Staff Member',
        'submit_label': 'Create Staff Member',
        'is_edit': False,
    }
    return render(request, 'dashboard/staff_form.html', context)


@portal_admin_required
def edit_staff(request, id):
    staff_member = Staff.objects.filter(id=id).first()
    if not staff_member:
        return render(request, '404.html', status=404)

    if request.method == 'POST':
        validation = _validate_staff_payload(request.POST, existing_staff=staff_member)
        errors = validation['errors']
        clean_data = validation['clean_data']

        if not errors:
            try:
                for key, value in clean_data.items():
                    setattr(staff_member, key, value)
                staff_member.save()
                return redirect('staff')
            except IntegrityError:
                errors.append('Could not update staff member because one of the unique fields already exists.')

        context = {
            'errors': errors,
            'form': clean_data,
            'role_choices': Staff.ROLE_CHOICES,
            'page_title': f'Edit Staff Member - {staff_member.name}',
            'submit_label': 'Save Changes',
            'is_edit': True,
            'staff_member': staff_member,
        }
        return render(request, 'dashboard/staff_form.html', context)

    context = {
        'errors': [],
        'form': {
            'name': staff_member.name,
            'email': staff_member.email,
            'role': staff_member.role,
            'id_number': staff_member.id_number,
            'rfid_number': staff_member.rfid_number,
            'can_open_door': staff_member.can_open_door,
            'can_control_lights': staff_member.can_control_lights,
            'can_control_projector': staff_member.can_control_projector,
            'can_manage_classrooms': staff_member.can_manage_classrooms,
            'can_manage_staff': staff_member.can_manage_staff,
        },
        'role_choices': Staff.ROLE_CHOICES,
        'page_title': f'Edit Staff Member - {staff_member.name}',
        'submit_label': 'Save Changes',
        'is_edit': True,
        'staff_member': staff_member,
    }
    return render(request, 'dashboard/staff_form.html', context)


@portal_admin_required
def delete_staff(request, id):
    if request.method != 'POST':
        return redirect('staff')

    staff_member = Staff.objects.filter(id=id).first()
    if staff_member:
        staff_member.delete()

    return redirect('staff')


@portal_admin_required
def bulk_delete_staff(request):
    if request.method != 'POST':
        return redirect('staff')

    settings_obj = get_system_settings()
    if not settings_obj.allow_bulk_actions:
        messages.error(request, 'Bulk actions are disabled by system settings.')
        return redirect('staff')

    raw_ids = request.POST.getlist('staff_ids')
    staff_ids = []
    for raw_id in raw_ids:
        try:
            staff_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not staff_ids:
        messages.warning(request, 'Select at least one staff member to delete.')
        return redirect('staff')

    staff_to_delete = Staff.objects.filter(id__in=staff_ids)
    deleted_count = staff_to_delete.count()
    if deleted_count == 0:
        messages.warning(request, 'No matching staff members were found for deletion.')
        return redirect('staff')

    staff_to_delete.delete()
    messages.success(request, f'{deleted_count} staff member(s) deleted successfully.')
    return redirect('staff')