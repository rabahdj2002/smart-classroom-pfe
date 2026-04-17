from .models import Student, Staff, Classroom, Session, SystemSettings


def dashboard_counts(request):
    app_settings, _ = SystemSettings.objects.get_or_create(pk=1)
    return {
        'dashboard_counts': {
            'students': Student.objects.count(),
            'staff': Staff.objects.count(),
            'classrooms': Classroom.objects.count(),
            'sessions': Session.objects.count(),
        },
        'app_settings': app_settings,
    }
