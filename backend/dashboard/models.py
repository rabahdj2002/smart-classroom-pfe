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
    temperature = models.FloatField(null=True, blank=True)
    danger_indicator = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name


class TemperatureSettings(models.Model):
    min_temperature = models.FloatField(default=15.0)
    max_temperature = models.FloatField(default=28.0)

    def __str__(self):
        return f"Temperature Settings ({self.min_temperature}C - {self.max_temperature}C)"


class Attendance(models.Model):
    id = models.AutoField(primary_key=True)
    students = models.ManyToManyField(Student, blank=True) # make sure it's a list of students
    #student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, null=True, blank=True)
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        if self.staff:
            attendee = self.staff.name
        elif self.students.exists():
            attendee = f"{self.students.count()} students"
        else:
            attendee = "Unknown"   
        return f"Attendance: {attendee} in {self.classroom} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    

