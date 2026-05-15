from django.contrib import admin
from .models import AttendanceReport, ClassTimetableSlot, Classroom, ImmediateTeacherAccessGrant, Session, Staff, Student, StudentSessionAttendance, SystemSettings, TemperatureSettings

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
    list_display = ('id', 'classroom', 'teacher', 'session_type', 'access_type', 'start_time', 'is_closed')
    list_filter = ('classroom', 'session_type', 'access_type', 'is_closed', 'start_time')
    search_fields = ('classroom__name', 'teacher__name', 'teacher__email')


@admin.register(StudentSessionAttendance)
class StudentSessionAttendanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'student', 'arrival_time')
    list_filter = ('session__classroom', 'arrival_time')
    search_fields = ('student__name', 'student__email', 'session__classroom__name')
    readonly_fields = ('created_at',)



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
        'teacher_access_window_minutes',
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


@admin.register(ClassTimetableSlot)
class ClassTimetableSlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'classroom', 'weekday', 'slot_index', 'teacher', 'subject')
    list_filter = ('classroom', 'weekday', 'slot_index')
    search_fields = ('classroom__name', 'teacher__name', 'subject')


@admin.register(ImmediateTeacherAccessGrant)
class ImmediateTeacherAccessGrantAdmin(admin.ModelAdmin):
    list_display = ('id', 'teacher', 'classroom', 'granted_by_username', 'granted_at', 'expires_at', 'is_active')
    list_filter = ('is_active', 'classroom', 'granted_at')
    search_fields = ('teacher__name', 'teacher__id_number', 'teacher__rfid_number', 'granted_by_username')
    
