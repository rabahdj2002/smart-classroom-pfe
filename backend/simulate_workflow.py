#!/usr/bin/env python
"""
Simulate a complete classroom workflow:
1. Admin inspection
2. Teacher session
3. 5 students attending
"""

import os
import django
import json
from datetime import datetime, time as dt_time, timedelta
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartclass.settings')
django.setup()

from django.utils import timezone
from dashboard.models import Staff, Student, Classroom, Session, ClassTimetableSlot, SystemSettings, StudentSessionAttendance
from dashboard.mqtt_listener import process_mqtt_payload


def day_name(weekday):
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return days[weekday]


print("=" * 80)
print("SMART CLASSROOM MQTT WORKFLOW SIMULATION")
print("=" * 80)

# Setup test data
print("\n1. Setting up test data...")

# Create classroom
classroom, _ = Classroom.objects.get_or_create(
    name='d3',
    defaults={'occupied': False}
)
print(f"   ✓ Classroom: {classroom.name}")

# Create admin
admin, _ = Staff.objects.get_or_create(
    rfid_number='ADMIN-INSPECTION-001',
    defaults={
        'name': 'Admin Inspector',
        'email': 'admin@school.edu',
        'role': 'ADMIN',
        'id_number': 'A-001',
    }
)
print(f"   ✓ Admin: {admin.name} (RFID: {admin.rfid_number})")

# Create teacher
teacher, _ = Staff.objects.get_or_create(
    rfid_number='TEACHER-SESSION-001',
    defaults={
        'name': 'Prof. Ahmed',
        'email': 'ahmed@school.edu',
        'role': 'PROF',
        'id_number': 'T-001',
    }
)
print(f"   ✓ Teacher: {teacher.name} (RFID: {teacher.rfid_number})")

# Create timetable slot for today
today = timezone.now().date()
weekday = today.weekday()
slot, _ = ClassTimetableSlot.objects.get_or_create(
    classroom=classroom,
    weekday=weekday,
    slot_index=0,
    defaults={
        'teacher': teacher,
        'subject': 'Physics',
    }
)
print(f"   ✓ Timetable: {slot.get_slot_index_display()} on {day_name(weekday)}")

# Create 5 students
students = []
for i in range(1, 6):
    student, _ = Student.objects.get_or_create(
        rfid_number=f'STUDENT-{i:03d}',
        defaults={
            'name': f'Student {i}',
            'email': f'student{i}@school.edu',
            'specialization': 'INFO',
            'year': 2,
            'student_card_id': f'CARD-{i:03d}',
        }
    )
    students.append(student)
    print(f"   ✓ Student {i}: {student.name} (RFID: {student.rfid_number})")

print("\n" + "=" * 80)
print("2. SIMULATING INSPECTION (Admin Access)")
print("=" * 80)

# Mock current time to be 08:05 (within timetable window)
mock_time = timezone.make_aware(
    datetime.combine(today, dt_time(8, 5, 0))
)

with patch('dashboard.mqtt_listener.timezone.now', return_value=mock_time):
    with patch('dashboard.mqtt_listener.publish_custom_topic') as mock_publish:
        print(f"\nSending admin inspection request to classroom '{classroom.name}'...")
        
        payload = json.dumps({
            'teacher_rfid': admin.rfid_number,
            'request_id': 'inspection-001'
        })
        
        process_mqtt_payload(
            f'smartclass/classrooms/{classroom.name}/access/request',
            payload.encode()
        )
        
        # Check response
        if mock_publish.called:
            response = mock_publish.call_args[0][1]
            print(f"   ✓ Response: {response.get('reason')}")
            print(f"   ✓ Session Type: Inspection")
        
        # Verify session was created
        inspection_session = Session.objects.filter(
            classroom=classroom,
            session_type='inspection'
        ).first()
        
        if inspection_session:
            print(f"   ✓ Inspection session created: ID {inspection_session.id}")
            print(f"   ✓ Logged in: {inspection_session.teacher.name}")
        
        # Close inspection after 5 minutes
        print("\nClosing inspection session (simulating 5 min duration)...")

print("\n" + "=" * 80)
print("3. SIMULATING TEACHER SESSION")
print("=" * 80)

# Close inspection
if inspection_session:
    inspection_session.is_closed = True
    inspection_session.ended_at = mock_time
    inspection_session.save()
    print(f"   ✓ Inspection session closed")

# Teacher starts session
with patch('dashboard.mqtt_listener.timezone.now', return_value=mock_time):
    with patch('dashboard.mqtt_listener.publish_custom_topic') as mock_publish:
        print(f"\nSending teacher access request to classroom '{classroom.name}'...")
        
        payload = json.dumps({
            'teacher_rfid': teacher.rfid_number,
            'request_id': 'session-001'
        })
        
        process_mqtt_payload(
            f'smartclass/classrooms/{classroom.name}/access/request',
            payload.encode()
        )
        
        # Check response
        if mock_publish.called:
            response = mock_publish.call_args[0][1]
            print(f"   ✓ Response: {response.get('reason')}")
            print(f"   ✓ Access Window: {response.get('access_window_minutes')} minutes")
        
        # Verify session was created
        teacher_session = Session.objects.filter(
            classroom=classroom,
            teacher=teacher,
            session_type='class',
            access_type='timetable'
        ).order_by('-id').first()
        
        if teacher_session:
            print(f"   ✓ Teacher session created: ID {teacher_session.id}")
            print(f"   ✓ Logged in: {teacher_session.teacher.name}")

print("\n" + "=" * 80)
print("4. SIMULATING STUDENT ATTENDANCE")
print("=" * 80)

if teacher_session:
    # Send attendance in batches
    batch1_students = students[:3]
    batch2_students = students[3:]
    
    print(f"\nBatch 1: {len(batch1_students)} students entering...")
    with patch('dashboard.mqtt_listener.publish_custom_topic'):
        # Batch 1: Students arrive 2 minutes after session starts
        batch1_time = mock_time + timedelta(minutes=2)
        print(f"   Students arriving at {batch1_time.strftime('%H:%M:%S')}...")
        with patch('dashboard.mqtt_listener.timezone.now', return_value=batch1_time):
            payload = json.dumps({
                'student_rfids': [s.rfid_number for s in batch1_students],
                'event': 'attendance_request'
            })
            
            process_mqtt_payload(
                f'smartclass/classrooms/{classroom.name}/attendance/request',
                payload.encode()
            )
            
            teacher_session.refresh_from_db()
            print(f"   ✓ Session now has {teacher_session.students.count()} students")
            for student in batch1_students:
                print(f"     - {student.name}")
    
    print(f"\nBatch 2: {len(batch2_students)} more students entering...")
    with patch('dashboard.mqtt_listener.publish_custom_topic'):
        # Batch 2: Students arrive 5 minutes after session starts
        batch2_time = mock_time + timedelta(minutes=5)
        print(f"   Students arriving at {batch2_time.strftime('%H:%M:%S')}...")
        with patch('dashboard.mqtt_listener.timezone.now', return_value=batch2_time):
            payload = json.dumps({
                'student_rfids': [s.rfid_number for s in batch2_students],
                'event': 'attendance_request'
            })
            
            process_mqtt_payload(
                f'smartclass/classrooms/{classroom.name}/attendance/request',
                payload.encode()
            )
            
            teacher_session.refresh_from_db()
            print(f"   ✓ Session now has {teacher_session.students.count()} students")
            for student in batch2_students:
                print(f"     - {student.name}")

print("\n" + "=" * 80)
print("5. FINAL SESSION STATE")
print("=" * 80)

if teacher_session:
    teacher_session.refresh_from_db()
    
    print(f"\nSession: {teacher_session}")
    print(f"  Type: {teacher_session.get_session_type_display()}")
    print(f"  Access Type: {teacher_session.get_access_type_display()}")
    print(f"  Teacher: {teacher_session.teacher.name}")
    print(f"  Started: {teacher_session.start_time}")
    print(f"  Students Registered: {teacher_session.students.count()}/5")
    
    # Display attendance with arrival times
    print(f"\n  Attendance Records with Arrival Times:")
    attendance_records = StudentSessionAttendance.objects.filter(session=teacher_session).order_by('arrival_time')
    for i, attendance in enumerate(attendance_records, 1):
        arrival_delta = (attendance.arrival_time - teacher_session.start_time).total_seconds() / 60
        print(f"    {i}. {attendance.student.name} - Arrived at {attendance.arrival_time.strftime('%H:%M:%S')} ({arrival_delta:.0f} min after session start)")

print("\n" + "=" * 80)
print("SIMULATION COMPLETE")
print("=" * 80)
