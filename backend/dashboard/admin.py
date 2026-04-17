from django.contrib import admin
from .models import Student, Staff, Classroom, Session, TemperatureSettings, SystemSettings, AttendanceReport

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'specialization', 'year', 'student_card_id', 'rfid_number')
    search_fields = ('name', 'email', 'student_card_id', 'rfid_number')
    list_filter = ('specialization', 'year')

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'role', 'id_number', 'rfid_number')
    search_fields = ('name', 'email', 'id_number', 'rfid_number')
    list_filter = ('role',)

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'occupied', 'door', 'lights_on', 'projector_on', 'smoke_detected', 'danger_indicator')
    list_filter = ('occupied', 'smoke_detected', 'danger_indicator')


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'classroom', 'teacher', 'start_time', 'expected_report_time', 'is_closed')
    list_filter = ('classroom', 'is_closed', 'start_time')
    search_fields = ('classroom__name', 'teacher__name', 'teacher__email')


@admin.register(TemperatureSettings)
class TemperatureSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'min_temperature', 'max_temperature')


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'smoke_alert_enabled',
        'auto_finish_enabled',
        'auto_finish_minutes',
        'email_reports_enabled',
        'smtp_host',
        'smtp_port',
    )


@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'classroom',
        'teacher',
        'session_start',
        'session_end',
        'duration_minutes',
        'total_students',
        'total_staff',
        'emailed',
    )
    list_filter = ('classroom', 'emailed', 'generated_at')
    search_fields = ('classroom__name', 'teacher__name', 'teacher__email')
    
