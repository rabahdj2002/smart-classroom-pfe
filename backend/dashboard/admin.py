from django.contrib import admin
from .models import Student, Staff, Classroom, Attendance

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialization', 'year', 'student_card_id', 'rfid_number')
    search_fields = ('name', 'email', 'student_card_id', 'rfid_number')
    list_filter = ('specialization', 'year')

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'id_number', 'rfid_number')
    search_fields = ('name', 'email', 'id_number', 'rfid_number')
    list_filter = ('role',)

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'capacity', 'occupied', 'lights_on', 'projector_on', 'temperature', 'danger_indicator')
    list_filter = ('occupied', 'danger_indicator')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'staff', 'timestamp')
    list_filter = ('classroom', 'timestamp')
    date_hierarchy = 'timestamp'
    
