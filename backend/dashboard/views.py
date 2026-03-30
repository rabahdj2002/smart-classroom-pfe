from django.shortcuts import render, redirect
from django.db.models import Count
from .models import Student, Staff, Classroom, Attendance
from django.utils import timezone
from datetime import timedelta
import json
    
def dash(request):
    today = timezone.now().date()
    
    context = {
        'total_students': Student.objects.count(),
        'total_staff': Staff.objects.count(),
        'total_classrooms': Classroom.objects.count(),
        'total_attendance_today': Attendance.objects.filter(timestamp__date=today).count(),
        'total_attendance_all_time': Attendance.objects.count(),
        'classrooms': Classroom.objects.all(),
    }
    
    return render(request, 'dashboard.html', context)


def classes(request):
    today = timezone.now().date()
    classrooms = Classroom.objects.all()

    classroom_list = []
    for room in classrooms:
        classroom_list.append({
            'id': room.id,
            'name': room.name,
            'capacity': room.capacity,
            'lights_on': room.lights_on,
            'projector_on': room.projector_on,
            'door': room.door,
            'occupied': room.occupied,
        })

    context = {'classrooms': classroom_list}
    return render(request, 'dashboard/classes.html', context)


def classroom_detail(request, id):
    classroom = Classroom.objects.filter(id=id).first()
    if not classroom:
        return render(request, '404.html', status=404)

    today = timezone.now().date()
    occupied_students = (
        Attendance.objects.filter(classroom=classroom, timestamp__date=today)
        .values('students')
        .distinct()
        .count()
    )
    
    # Count today's sessions/occupations (Attendance records)
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

    occupied_percentage = 0
    if classroom.capacity:
        occupied_percentage = (occupied_students / classroom.capacity) * 100

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

    context = {
        'classroom': classroom,
        'occupied_students': occupied_students,
        'today_sessions': today_sessions,
        'weekly_sessions': weekly_sessions,
        'monthly_sessions': monthly_sessions,
        'occupied_percentage': occupied_percentage,
        'usage_labels_json': json.dumps(usage_labels),
        'usage_values_json': json.dumps(usage_student_values),
        'usage_teacher_values_json': json.dumps(usage_teacher_values),
        'capacity': classroom.capacity,
        'weekly_student_sessions': weekly_student_sessions,
        'weekly_teacher_sessions': weekly_teacher_sessions,
    }
    return render(request, 'dashboard/classroom_detail.html', context)


def add_class(request):
    errors = []
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        capacity_raw = request.POST.get('capacity', '').strip()
        lights_on = bool(request.POST.get('lights_on'))
        projector_on = bool(request.POST.get('projector_on'))
        door = bool(request.POST.get('door'))
        danger_indicator = bool(request.POST.get('danger_indicator'))

        if not name:
            errors.append('Name is required.')

        try:
            capacity = int(capacity_raw)
            if capacity <= 0:
                errors.append('Capacity must be a positive integer.')
        except ValueError:
            errors.append('Capacity must be a number.')
            capacity = 0

        if not errors:
            Classroom.objects.create(
                name=name,
                capacity=capacity,
                lights_on=lights_on,
                projector_on=projector_on,
                door=door,
                danger_indicator=danger_indicator,
                occupied=False,
            )
            return redirect('classes')

        context = {
            'errors': errors,
            'form': {
                'name': name,
                'capacity': capacity_raw,
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