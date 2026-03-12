from django.shortcuts import render
from .models import Student, Staff, Classroom, Attendance
from django.utils import timezone
    
def dash(request):
    today = timezone.now().date()
    
    context = {
        'total_students': Student.objects.count(),
        'total_staff': Staff.objects.count(),
        'total_classrooms': Classroom.objects.count(),
        'total_attendance_today': Attendance.objects.filter(timestamp__date=today).count(),
        'total_attendance_all_time': Attendance.objects.count(),
    }
    
    return render(request, 'dashboard.html', context) 