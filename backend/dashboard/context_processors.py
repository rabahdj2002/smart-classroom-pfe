from .models import Student, Staff, Classroom, Session


def dashboard_counts(request):
    return {
        'dashboard_counts': {
            'students': Student.objects.count(),
            'staff': Staff.objects.count(),
            'classrooms': Classroom.objects.count(),
            'sessions': Session.objects.count(),
        }
    }
