from django.shortcuts import render, redirect
from django.db.models import Q
from .models import Student, Staff, Classroom, Attendance, TemperatureSettings
from django.utils import timezone
from datetime import timedelta, datetime
import json


def get_temperature_settings():
    settings_obj, _ = TemperatureSettings.objects.get_or_create(
        pk=1,
        defaults={'min_temperature': 15.0, 'max_temperature': 28.0},
    )
    return settings_obj
    
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


def students(request):
    student_list = Student.objects.all()
    context = {
        'students': student_list,
    }
    return render(request, 'dashboard/students.html', context)