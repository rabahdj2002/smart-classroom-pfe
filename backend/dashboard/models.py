from django.db import models
from django.utils import timezone
 

class Student(models.Model):
    SPECIALIZATION_CHOICES = [
        ('INFO', 'Informatique'),
        ('MATH', 'Mathématiques'),
        ('ST', 'Sciences et Techniques'),
        ('SM', 'Sciences de la Matière'),
        ('MI', 'Mathématiques et Informatique'),
    ]
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    specialization = models.CharField(max_length=20, choices=SPECIALIZATION_CHOICES)
    year = models.IntegerField()
    student_card_id = models.CharField(max_length=50, unique=True)
    rfid_number = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return f"{self.name} ({self.specialization})"


class Staff(models.Model):
    ROLE_CHOICES = [
        ('PROF', 'Teacher / Professor'),
        ('ASSISTANT', 'Assistant'),
        ('ADMIN', 'Administrator'),
        ('IT', 'IT Support'),
        ('SECURITY', 'Security'),
        ('OTHER', 'Other'),
    ]
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    id_number = models.CharField(max_length=50, unique=True)
    rfid_number = models.CharField(max_length=50, unique=True)
    can_open_door = models.BooleanField(default=False)
    can_control_lights = models.BooleanField(default=False)
    can_control_projector = models.BooleanField(default=False)
    can_manage_classrooms = models.BooleanField(default=False)
    can_manage_staff = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.role})"


class Classroom(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    occupied = models.BooleanField(default=False)
    lights_on = models.BooleanField(default=False)
    door = models.BooleanField(default=False)
    projector_on = models.BooleanField(default=False)
    smoke_detected = models.BooleanField(default=False)
    session_started_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    danger_indicator = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name


class TemperatureSettings(models.Model):
    min_temperature = models.FloatField(default=15.0)
    max_temperature = models.FloatField(default=28.0)

    def __str__(self):
        return f"Temperature Settings ({self.min_temperature}C - {self.max_temperature}C)"


class SystemSettings(models.Model):
    smoke_alert_enabled = models.BooleanField(default=True)
    auto_finish_enabled = models.BooleanField(default=True)
    cron_interval_minutes = models.PositiveIntegerField(default=5)
    last_auto_finish_run_at = models.DateTimeField(null=True, blank=True)
    auto_finish_minutes = models.PositiveIntegerField(default=90)
    email_reports_enabled = models.BooleanField(default=False)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_from_email = models.EmailField(blank=True)

    def __str__(self):
        return "System Settings"


class Session(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='sessions')
    teacher = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    students = models.ManyToManyField(Student, blank=True, related_name='sessions')
    start_time = models.DateTimeField(default=timezone.now)
    expected_report_time = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"Session {self.id} - {self.classroom.name} ({self.start_time:%Y-%m-%d %H:%M})"


class AttendanceReport(models.Model):
    session = models.OneToOneField('Session', on_delete=models.CASCADE, null=True, blank=True, related_name='report')
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='attendance_reports')
    teacher = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    session_start = models.DateTimeField()
    session_end = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=0)
    total_students = models.PositiveIntegerField(default=0)
    total_staff = models.PositiveIntegerField(default=0)
    details = models.TextField(blank=True)
    generated_at = models.DateTimeField(default=timezone.now)
    emailed = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Report {self.classroom.name} ({self.session_start:%Y-%m-%d %H:%M} - {self.session_end:%H:%M})"
    

