from django.shortcuts import render, redirect
from django.db.models import Q
from django.db import IntegrityError
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .models import Student, Staff, Classroom, Attendance, TemperatureSettings
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import timedelta, datetime
from functools import wraps
import json


def _is_portal_admin(user):
    return user.is_authenticated and user.is_active and user.is_staff and not user.is_superuser


def portal_admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?next={request.path}")

        if not _is_portal_admin(request.user):
            logout(request)
            messages.error(request, 'Only admin portal accounts can access this website.')
            return redirect('login')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def login_view(request):
    if _is_portal_admin(request.user):
        return redirect('dashboard')

    if request.user.is_authenticated and request.user.is_superuser:
        logout(request)
        messages.error(request, 'Superadmin accounts are not allowed in this portal.')

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

        if user and user.is_superuser:
            error = 'Superadmin accounts are not allowed in this portal.'
        else:
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


def get_temperature_settings():
    settings_obj, _ = TemperatureSettings.objects.get_or_create(
        pk=1,
        defaults={'min_temperature': 15.0, 'max_temperature': 28.0},
    )
    return settings_obj
    
@portal_admin_required
def dash(request):
    today = timezone.now().date()
    now = timezone.now()
    temperature_settings = get_temperature_settings()
    
    # Basic counts
    total_students = Student.objects.count()
    total_staff = Staff.objects.count()
    total_classrooms = Classroom.objects.count()
    total_attendance_today = Attendance.objects.filter(timestamp__date=today).count()
    
    # Classroom status and warnings
    all_classrooms = Classroom.objects.all()
    danger_classrooms = list(all_classrooms.filter(danger_indicator=True))
    warning_classrooms = list(
        all_classrooms.filter(temperature__isnull=False).filter(
            Q(temperature__gt=temperature_settings.max_temperature)
            | Q(temperature__lt=temperature_settings.min_temperature)
        )
    )
    
    # Remove duplicates if temperature-based warnings overlap with danger
    warning_classrooms = [c for c in warning_classrooms if c not in danger_classrooms]
    
    # Current usage
    classroom_status = []
    for classroom in all_classrooms:
        today_sessions = Attendance.objects.filter(
            classroom=classroom, 
            timestamp__date=today
        ).count()

        used_today = classroom.occupied
        
        status = "danger" if classroom in danger_classrooms else ("warning" if classroom in warning_classrooms else "normal")
        
        classroom_status.append({
            'id': classroom.id,
            'name': classroom.name,
            'today_sessions': today_sessions,
            'used_today': used_today,
            'occupied': classroom.occupied,
            'lights_on': classroom.lights_on,
            'projector_on': classroom.projector_on,
            'door': classroom.door,
            'temperature': classroom.temperature,
            'status': status,
        })
    
    # Today's hourly activity
    hourly_attendance = [0] * 24
    hourly_labels = []
    for hour in range(24):
        hour_start = datetime.combine(today, datetime.min.time()).replace(hour=hour)
        hour_end = hour_start.replace(hour=(hour + 1) % 24)
        
        if hour == 23:
            hour_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        
        hour_attendance = Attendance.objects.filter(
            timestamp__gte=hour_start,
            timestamp__lt=hour_end
        ).count()
        
        hourly_attendance[hour] = hour_attendance
        hourly_labels.append(f"{hour:02d}:00")
    
    # Weekly trends (last 7 days)
    weekly_labels = []
    weekly_attendance = []
    weekly_classrooms_used = []
    
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_attendance = Attendance.objects.filter(timestamp__date=day).count()
        day_classrooms = Attendance.objects.filter(timestamp__date=day).values('classroom').distinct().count()
        
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
        'warning_classrooms': warning_classrooms,
        'has_warnings': len(danger_classrooms) > 0 or len(warning_classrooms) > 0,
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
        'temperature_min': temperature_settings.min_temperature,
        'temperature_max': temperature_settings.max_temperature,
        'today': today.strftime('%A, %B %d, %Y'),
    }
    
    return render(request, 'dashboard.html', context)


@portal_admin_required
def classes(request):
    classrooms = Classroom.objects.all()

    classroom_list = []
    for room in classrooms:
        today_sessions = Attendance.objects.filter(
            classroom=room,
            timestamp__date=timezone.now().date(),
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

    context = {'classrooms': classroom_list}
    return render(request, 'dashboard/classes.html', context)


@portal_admin_required
def classroom_detail(request, id):
    classroom = Classroom.objects.filter(id=id).first()
    if not classroom:
        return render(request, '404.html', status=404)
    temperature_settings = get_temperature_settings()

    today = timezone.now().date()
    today_sessions = Attendance.objects.filter(classroom=classroom, timestamp__date=today).count()

    start_date = today - timedelta(days=29)
    usage_labels = []
    usage_student_values = []
    usage_teacher_values = []

    for n in range(30):
        day = start_date + timedelta(days=n)

        student_count = (
            Attendance.objects.filter(classroom=classroom, timestamp__date=day)
            .values('students')
            .distinct()
            .count()
        )

        teacher_count = (
            Attendance.objects.filter(classroom=classroom, timestamp__date=day)
            .exclude(staff=None)
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
    
    weekly_sessions = Attendance.objects.filter(
        classroom=classroom, 
        timestamp__date__gte=start_date_7,
        timestamp__date__lte=today
    ).count()
    
    monthly_sessions = Attendance.objects.filter(
        classroom=classroom, 
        timestamp__date__gte=start_date_30,
        timestamp__date__lte=today
    ).count()

    has_temp_warning = False
    temp_warning_type = None
    if classroom.temperature is not None:
        if classroom.temperature > temperature_settings.max_temperature:
            has_temp_warning = True
            temp_warning_type = 'high'
        elif classroom.temperature < temperature_settings.min_temperature:
            has_temp_warning = True
            temp_warning_type = 'low'

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
        'temperature_min': temperature_settings.min_temperature,
        'temperature_max': temperature_settings.max_temperature,
        'has_temp_warning': has_temp_warning,
        'temp_warning_type': temp_warning_type,
    }
    return render(request, 'dashboard/classroom_detail.html', context)


@portal_admin_required
def temperature_settings(request):
    settings_obj = get_temperature_settings()
    errors = []
    success_message = ''

    if request.method == 'POST':
        min_temperature_raw = request.POST.get('min_temperature', '').strip()
        max_temperature_raw = request.POST.get('max_temperature', '').strip()

        try:
            min_temperature = float(min_temperature_raw)
            max_temperature = float(max_temperature_raw)
            if min_temperature >= max_temperature:
                errors.append('Minimum temperature must be lower than maximum temperature.')
        except ValueError:
            errors.append('Temperature values must be valid numbers.')
            min_temperature = settings_obj.min_temperature
            max_temperature = settings_obj.max_temperature

        if not errors:
            settings_obj.min_temperature = min_temperature
            settings_obj.max_temperature = max_temperature
            settings_obj.save()
            success_message = 'Temperature warning settings updated successfully.'

    context = {
        'settings_obj': settings_obj,
        'errors': errors,
        'success_message': success_message,
        'classrooms': Classroom.objects.order_by('name'),
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
        count = Attendance.objects.filter(students=student, timestamp__date=day).count()
        attendance_labels.append(day.strftime('%b %d'))
        attendance_values.append(count)

    weekly_student_sessions = sum(attendance_values[-7:])
    recent_attendance = Attendance.objects.filter(students=student).order_by('-timestamp')[:7]

    context = {
        'student': student,
        'attendance_labels_json': json.dumps(attendance_labels),
        'attendance_values_json': json.dumps(attendance_values),
        'weekly_student_sessions': weekly_student_sessions,
        'recent_attendance': recent_attendance,
    }
    return render(request, 'dashboard/student_detail.html', context)


@portal_admin_required
def students(request):
    student_list = Student.objects.all()
    context = {
        'students': student_list,
    }
    return render(request, 'dashboard/students.html', context)


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
    query = request.GET.get('q', '').strip()
    role = request.GET.get('role', '').strip()
    privilege = request.GET.get('privilege', '').strip()

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

    context = {
        'staff_members': staff_members,
        'role_choices': Staff.ROLE_CHOICES,
        'filters': {
            'q': query,
            'role': role,
            'privilege': privilege,
        },
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