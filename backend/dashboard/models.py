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
    default_list_page_size = models.PositiveIntegerField(default=50)
    default_sessions_order = models.CharField(max_length=8, default='id_desc')
    allow_bulk_actions = models.BooleanField(default=True)
    show_kpi_badges = models.BooleanField(default=True)
    ui_compact_mode = models.BooleanField(default=False)
    email_reports_enabled = models.BooleanField(default=False)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=255, blank=True)
    smtp_password = models.CharField(max_length=255, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_from_email = models.EmailField(blank=True)
    mqtt_mode = models.CharField(max_length=16, default='production')
    mqtt_broker_host = models.CharField(max_length=255, blank=True)
    mqtt_broker_port = models.PositiveIntegerField(default=1883)
    mqtt_topic_wildcard = models.CharField(max_length=255, default='smartclass/#')
    teacher_access_window_minutes = models.PositiveIntegerField(default=10)
    student_door_close_delay_minutes = models.PositiveIntegerField(default=10)

    def __str__(self):
        return "System Settings"


class Session(models.Model):
    SESSION_TYPE_CHOICES = [
        ('class', 'Class Session'),
        ('inspection', 'Admin Inspection'),
    ]
    
    ACCESS_TYPE_CHOICES = [
        ('timetable', 'Scheduled Timetable'),
        ('out_of_schedule', 'Out-of-Schedule Override'),
        ('none', 'N/A (Inspection)'),
    ]
    
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='sessions')
    teacher = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    students = models.ManyToManyField(Student, blank=True, related_name='sessions')
    start_time = models.DateTimeField(default=timezone.now)
    expected_report_time = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)
    session_type = models.CharField(max_length=15, choices=SESSION_TYPE_CHOICES, default='class')
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPE_CHOICES, default='none')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"Session {self.id} - {self.classroom.name} ({self.start_time:%Y-%m-%d %H:%M})"


class StudentSessionAttendance(models.Model):
    """Track when each student arrived during a session."""
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='student_attendances')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='session_attendances')
    arrival_time = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['arrival_time']
        unique_together = ('session', 'student')
        verbose_name_plural = 'Student Session Attendances'

    def __str__(self):
        return f"{self.student.name} - {self.session} ({self.arrival_time:%H:%M:%S})"


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


class ImmediateTeacherAccessGrant(models.Model):
    teacher = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='immediate_access_grants')
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='immediate_access_grants',
        null=True,
        blank=True,
    )
    granted_by_username = models.CharField(max_length=150, blank=True)
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-granted_at']

    def __str__(self):
        scope = self.classroom.name if self.classroom_id else 'Any classroom'
        return f"Immediate access for {self.teacher.name} ({scope}) until {self.expires_at:%Y-%m-%d %H:%M}"


class ClassTimetableSlot(models.Model):
    WEEKDAY_CHOICES = [
        (5, 'Saturday'),
        (6, 'Sunday'),
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
    ]

    SLOT_CHOICES = [
        (0, '08:00 - 09:30'),
        (1, '09:30 - 11:00'),
        (2, '11:00 - 12:30'),
        (3, '12:30 - 14:00'),
        (4, '14:00 - 15:30'),
        (5, '15:30 - 17:00'),
    ]

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='timetable_slots')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    slot_index = models.PositiveSmallIntegerField(choices=SLOT_CHOICES)
    subject = models.CharField(max_length=120, blank=True)
    teacher = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timetable_slots',
        limit_choices_to={'role': 'PROF'},
    )

    class Meta:
        ordering = ['weekday', 'slot_index']
        constraints = [
            models.UniqueConstraint(
                fields=['classroom', 'weekday', 'slot_index'],
                name='unique_timetable_slot_per_classroom',
            )
        ]

    def __str__(self):
        return f"{self.classroom.name} | {self.get_weekday_display()} | {self.get_slot_index_display()}"


