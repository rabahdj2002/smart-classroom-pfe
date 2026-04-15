from .models import Student, Staff, Classroom


def dashboard_counts(request):
    return {
        'dashboard_counts': {
            'students': Student.objects.count(),
            'staff': Staff.objects.count(),
            'classrooms': Classroom.objects.count(),
        }
    }
