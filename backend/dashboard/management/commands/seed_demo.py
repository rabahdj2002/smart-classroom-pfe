from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dashboard.models import ClassTimetableSlot, Classroom, Session, Specialization, Staff, Student, SystemSettings
from dashboard.mqtt_runtime import _is_configured_host
from dashboard.reporting import generate_attendance_report_for_session

CLASSROOMS = [
    ('A101', 'Block A', '1', 40),
    ('A102', 'Block A', '1', 40),
    ('B201', 'Block B', '2', 60),
    ('LAB-IoT', 'Block C', '0', 24),
]
TEACHERS = [
    ('Dr. Amina Bensalem', 'PROF'),
    ('Dr. Karim Haddad', 'PROF'),
    ('Dr. Leila Mansouri', 'PROF'),
    ('Yacine Ait', 'ADMIN'),
]
STUDENT_NAMES = [
    'Sara Belkacem', 'Mehdi Cherif', 'Nour Hamidi', 'Rami Ouali', 'Ines Kaci', 'Walid Saadi',
    'Lina Brahimi', 'Adam Ferhat', 'Yasmine Toumi', 'Ilyes Rahmani', 'Meriem Zerrouki', 'Anis Djellal',
]
SUBJECTS = ['Control Systems', 'Embedded Systems', 'Industrial Networks', 'Signal Processing', 'Robotics']


class Command(BaseCommand):
    help = 'Load idempotent demo data (classrooms, staff, students, timetable, sessions and reports) and a demo admin.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='demo')
        parser.add_argument('--password', default='demo12345')

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=options['username'], defaults={'is_staff': True, 'is_superuser': True})
        if created:
            user.set_password(options['password'])
            user.save()

        system_settings, _ = SystemSettings.objects.get_or_create(pk=1)
        if not _is_configured_host(system_settings.mqtt_broker_host):
            system_settings.mqtt_broker_host = settings.DASHBOARD_MQTT_BROKER_HOST
            system_settings.mqtt_broker_port = settings.DASHBOARD_MQTT_BROKER_PORT
            system_settings.save(update_fields=['mqtt_broker_host', 'mqtt_broker_port'])

        if Classroom.objects.exists():
            self.stdout.write('Demo data already present, skipping.')
            return

        spec_codes = list(Specialization.objects.filter(is_active=True).values_list('code', flat=True)) or ['AUTO']
        if not Specialization.objects.exists():
            Specialization.objects.create(code='AUTO', name='Automatic Control')

        rooms = [Classroom.objects.create(name=n, building=b, floor=f, capacity=c) for n, b, f, c in CLASSROOMS]
        staff = [
            Staff.objects.create(
                name=name, role=role, email=f'staff{i}@demo.campus', id_number=f'T-{100 + i}',
                rfid_number=f'RFID-T-{100 + i}', can_open_door=role == 'ADMIN',
            )
            for i, (name, role) in enumerate(TEACHERS)
        ]
        teachers = [s for s in staff if s.role == 'PROF']
        years = ['L3', 'M1', 'M2']
        students = [
            Student.objects.create(
                name=name, email=f'student{i}@demo.campus', specialization=spec_codes[i % len(spec_codes)],
                year=years[i % len(years)], student_card_id=f'CARD-{2000 + i}', rfid_number=f'RFID-S-{2000 + i}',
            )
            for i, name in enumerate(STUDENT_NAMES)
        ]

        for r_index, room in enumerate(rooms):
            for weekday in (5, 6, 0, 1, 2, 3):
                for slot in (0, 1, 2, 4):
                    if (weekday + slot + r_index) % 3 == 0:
                        continue
                    ClassTimetableSlot.objects.create(
                        classroom=room, weekday=weekday, slot_index=slot,
                        subject=SUBJECTS[(weekday + slot + r_index) % len(SUBJECTS)],
                        teacher=teachers[(slot + r_index) % len(teachers)],
                    )

        now = timezone.now()
        for day in range(1, 15):
            for r_index, room in enumerate(rooms[:3]):
                start = (now - timedelta(days=day)).replace(hour=8 + 2 * r_index, minute=0, second=0, microsecond=0)
                session = Session.objects.create(classroom=room, teacher=teachers[(day + r_index) % len(teachers)], start_time=start)
                session.students.set(students[(day + r_index) % 4::2])
                generate_attendance_report_for_session(session, session_end=start + timedelta(minutes=90))

        live = Session.objects.create(classroom=rooms[0], teacher=teachers[0], start_time=now - timedelta(minutes=25))
        live.students.set(students[:8])
        Classroom.objects.filter(pk=rooms[0].pk).update(occupied=True, lights_on=True, projector_on=True, session_started_at=live.start_time, last_activity_at=now)

        self.stdout.write(self.style.SUCCESS(
            f'Demo data loaded: {len(rooms)} classrooms, {len(staff)} staff, {len(students)} students. '
            f'Log in as {options["username"]} / {options["password"]}.'
        ))
