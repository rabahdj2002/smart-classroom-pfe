import json
from datetime import datetime, timedelta, time as dt_time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils import timezone

from .models import AttendanceReport, ClassTimetableSlot, Classroom, ImmediateTeacherAccessGrant, Session, Staff, Student, SystemSettings
from .mqtt_listener import _evaluate_teacher_access, process_mqtt_payload
from .views import add_session


class BackupRestoreTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='admin',
			email='admin@example.com',
			password='password123',
			is_staff=True,
		)
		self.client.login(username='admin', password='password123')

		self.staff = Staff.objects.create(
			name='Teacher One',
			email='teacher@example.com',
			role='PROF',
			id_number='T-001',
			rfid_number='RFID-TEACHER-1',
		)
		self.student = Student.objects.create(
			name='Student One',
			email='student@example.com',
			specialization='INFO',
			year=2,
			student_card_id='CARD-001',
			rfid_number='RFID-STUDENT-1',
		)
		self.classroom = Classroom.objects.create(name='Room A', occupied=True, lights_on=True)
		self.session = Session.objects.create(
			classroom=self.classroom,
			teacher=self.staff,
			start_time=timezone.now(),
			is_closed=True,
		)
		self.session.students.add(self.student)
		AttendanceReport.objects.create(
			session=self.session,
			classroom=self.classroom,
			teacher=self.staff,
			session_start=self.session.start_time,
			session_end=self.session.start_time + timedelta(minutes=90),
			duration_minutes=90,
			total_students=1,
			total_staff=1,
			details='Sample backup report',
		)

	def test_students_json_export_returns_full_backup(self):
		response = self.client.get(reverse('export_students', args=['json']))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'application/json')

		payload = json.loads(response.content.decode('utf-8'))
		self.assertEqual(payload['version'], 1)
		self.assertEqual(len(payload['students']), 1)
		self.assertEqual(len(payload['classrooms']), 1)
		self.assertEqual(len(payload['sessions']), 1)
		self.assertEqual(len(payload['attendance_reports']), 1)
		self.assertEqual(len(payload['staff']), 1)

	def test_restore_students_round_trip_recreates_data(self):
		response = self.client.get(reverse('export_students', args=['json']))
		backup_file = SimpleUploadedFile('backup.json', response.content, content_type='application/json')

		AttendanceReport.objects.all().delete()
		Session.objects.all().delete()
		Student.objects.all().delete()
		Classroom.objects.all().delete()
		Staff.objects.all().delete()

		restore_response = self.client.post(reverse('restore_students'), {'backup_file': backup_file})

		self.assertEqual(restore_response.status_code, 302)
		self.assertEqual(Staff.objects.count(), 1)
		self.assertEqual(Student.objects.count(), 1)
		self.assertEqual(Classroom.objects.count(), 1)
		self.assertEqual(Session.objects.count(), 1)
		self.assertEqual(AttendanceReport.objects.count(), 1)
		restored_session = Session.objects.first()
		self.assertEqual(restored_session.students.count(), 1)

	def test_staff_csv_export_includes_privilege_columns(self):
		response = self.client.get(reverse('export_staff', args=['csv']))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
		self.assertIn('Can Open Door', response.content.decode('utf-8'))
		self.assertIn('Teacher One', response.content.decode('utf-8'))

	def test_restore_staff_round_trip_recreates_data(self):
		response = self.client.get(reverse('export_staff', args=['json']))
		backup_file = SimpleUploadedFile('backup.json', response.content, content_type='application/json')

		AttendanceReport.objects.all().delete()
		Session.objects.all().delete()
		Student.objects.all().delete()
		Classroom.objects.all().delete()
		Staff.objects.all().delete()

		restore_response = self.client.post(reverse('restore_staff'), {'backup_file': backup_file})

		self.assertEqual(restore_response.status_code, 302)
		self.assertEqual(Staff.objects.count(), 1)
		self.assertEqual(Student.objects.count(), 1)
		self.assertEqual(Classroom.objects.count(), 1)
		self.assertEqual(Session.objects.count(), 1)
		self.assertEqual(AttendanceReport.objects.count(), 1)


class TimetableAndAuthorizationTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.user = get_user_model().objects.create_user(
			username='admin2',
			email='admin2@example.com',
			password='password123',
			is_staff=True,
		)
		self.client.login(username='admin2', password='password123')

		self.teacher = Staff.objects.create(
			name='Prof Timetable',
			email='proftt@example.com',
			role='PROF',
			id_number='TT-001',
			rfid_number='RFID-PROF-TT',
		)
		self.classroom = Classroom.objects.create(name='Room Time')

		settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
		settings_obj.teacher_access_window_minutes = 10
		settings_obj.student_door_close_delay_minutes = 10
		settings_obj.save(update_fields=['teacher_access_window_minutes', 'student_door_close_delay_minutes'])

	def test_classroom_timetable_page_can_be_saved(self):
		response = self.client.post(
			reverse('classroom_timetable', args=[self.classroom.id]),
			{
				'teacher_5_0': str(self.teacher.id),
				'subject_5_0': 'Networks',
			},
		)

		self.assertEqual(response.status_code, 302)
		slot = ClassTimetableSlot.objects.get(classroom=self.classroom, weekday=5, slot_index=0)
		self.assertEqual(slot.teacher_id, self.teacher.id)
		self.assertEqual(slot.subject, 'Networks')

	def test_teacher_access_is_approved_within_window(self):
		ClassTimetableSlot.objects.create(
			classroom=self.classroom,
			weekday=5,
			slot_index=0,
			teacher=self.teacher,
			subject='Math',
		)
		event_time = timezone.make_aware(datetime(2026, 4, 18, 8, 7, 0), timezone.get_current_timezone())
		payload = _evaluate_teacher_access(
			classroom=self.classroom,
			teacher_rfid=self.teacher.rfid_number,
			event_time=event_time,
			request_id='req-1',
		)

		self.assertTrue(payload['approved'])
		self.assertEqual(payload['reason'], 'authorized_in_time_window')

	def test_teacher_access_is_denied_outside_window(self):
		settings_obj = SystemSettings.objects.get(pk=1)
		settings_obj.teacher_access_window_minutes = 5
		settings_obj.save(update_fields=['teacher_access_window_minutes'])

		ClassTimetableSlot.objects.create(
			classroom=self.classroom,
			weekday=5,
			slot_index=0,
			teacher=self.teacher,
			subject='Physics',
		)
		event_time = timezone.make_aware(datetime(2026, 4, 18, 8, 9, 0), timezone.get_current_timezone())
		payload = _evaluate_teacher_access(
			classroom=self.classroom,
			teacher_rfid=self.teacher.rfid_number,
			event_time=event_time,
			request_id='req-2',
		)

		self.assertFalse(payload['approved'])
		self.assertEqual(payload['reason'], 'outside_allowed_time_window')

	def test_teacher_access_is_approved_for_admin_without_timetable(self):
		admin = Staff.objects.create(
			name='Admin User',
			email='admin-user@example.com',
			role='ADMIN',
			id_number='ADMIN-001',
			rfid_number='RFID-ADMIN-001',
		)
		payload = _evaluate_teacher_access(
			classroom=self.classroom,
			teacher_rfid=admin.rfid_number,
			event_time=timezone.now(),
			request_id='req-admin',
		)

		self.assertTrue(payload['approved'])
		self.assertEqual(payload['reason'], 'authorized_admin_override')
		self.assertEqual(payload['teacher_name'], admin.name)

	def test_session_page_can_create_inspection_with_staff(self):
		inspection_staff = Staff.objects.create(
			name='Inspector Staff',
			email='inspector@example.com',
			role='ADMIN',
			id_number='INS-001',
			rfid_number='RFID-INS-001',
		)

		response = self.client.post(
			reverse('add_session'),
			{
				'classroom_id': str(self.classroom.id),
				'staff_id': str(inspection_staff.id),
				'session_type': 'inspection',
				'start_time': '2026-04-20T08:15',
			},
		)

		self.assertEqual(response.status_code, 302)
		session = Session.objects.latest('id')
		self.assertEqual(session.session_type, 'inspection')
		self.assertEqual(session.teacher, inspection_staff)
		self.assertTrue(session.is_closed)
		self.assertEqual(session.access_type, 'none')
		self.assertIsNone(session.expected_report_time)
		self.assertEqual(session.students.count(), 0)

	def test_session_page_rejects_non_admin_inspection_staff(self):
		non_admin_staff = Staff.objects.create(
			name='Teacher User',
			email='teacher-user@example.com',
			role='PROF',
			id_number='PROF-999',
			rfid_number='RFID-PROF-999',
		)

		request = self.factory.post(
			reverse('add_session'),
			{
				'classroom_id': str(self.classroom.id),
				'staff_id': str(non_admin_staff.id),
				'session_type': 'inspection',
				'start_time': '2026-04-20T08:20',
			},
		)
		request.user = self.user
		request.session = self.client.session
		request._messages = FallbackStorage(request)
		response = add_session(request)

		self.assertEqual(response.status_code, 200)
		self.assertIn('Inspection sessions can only be assigned to administrators.', response.content.decode())
		self.assertEqual(Session.objects.filter(session_type='inspection').count(), 0)

	def test_teacher_access_is_approved_by_immediate_override(self):
		ClassTimetableSlot.objects.create(
			classroom=self.classroom,
			weekday=5,
			slot_index=0,
			teacher=self.teacher,
			subject='Physics',
		)

		# Create a valid immediate override even though access is outside the timetable window.
		ImmediateTeacherAccessGrant.objects.create(
			teacher=self.teacher,
			classroom=self.classroom,
			expires_at=timezone.now() + timedelta(minutes=30),
			is_active=True,
		)

		event_time = timezone.make_aware(datetime(2026, 4, 18, 8, 20, 0), timezone.get_current_timezone())
		payload = _evaluate_teacher_access(
			classroom=self.classroom,
			teacher_rfid=self.teacher.rfid_number,
			event_time=event_time,
			request_id='req-override',
		)

		self.assertTrue(payload['approved'])
		self.assertEqual(payload['reason'], 'authorized_immediate_override')

	def test_settings_can_grant_immediate_override_by_teacher_id_number(self):
		response = self.client.post(
			reverse('temperature_settings'),
			{
				'settings_action': 'grant_teacher_access',
				'teacher_identifier': self.teacher.id_number,
				'override_duration_minutes': '45',
			},
		)

		self.assertEqual(response.status_code, 302)
		grant = ImmediateTeacherAccessGrant.objects.filter(teacher=self.teacher, is_active=True).first()
		self.assertIsNotNone(grant)

	def test_settings_can_save_student_door_close_delay(self):
		settings_obj = SystemSettings.objects.get(pk=1)
		settings_obj.student_door_close_delay_minutes = 15
		settings_obj.save(update_fields=['student_door_close_delay_minutes'])

		self.assertEqual(SystemSettings.objects.get(pk=1).student_door_close_delay_minutes, 15)

	def test_process_mqtt_payload_ignores_incoming_timestamp(self):
		fixed_now = timezone.make_aware(datetime(2026, 4, 20, 9, 15, 0), timezone.get_current_timezone())
		classroom = self.classroom
		teacher = self.teacher

		with patch('dashboard.mqtt_listener.timezone.now', return_value=fixed_now):
			process_mqtt_payload(
				f'smartclass/classrooms/{classroom.name}/events',
				json.dumps({
					'classroom_name': classroom.name,
					'teacher_rfid': teacher.rfid_number,
					'occupied': True,
					'timestamp': '2000-01-01T00:00:00+00:00',
				}).encode('utf-8'),
			)

		session = Session.objects.first()
		self.assertIsNotNone(session)
		self.assertEqual(timezone.localtime(session.start_time), timezone.localtime(fixed_now))

	@patch('dashboard.mqtt_listener.publish_custom_topic')
	def test_student_door_delay_request_publishes_response(self, publish_mock):
		process_mqtt_payload(
			f'smartclass/classrooms/{self.classroom.name}/door-delay/request',
			b'{}',
		)

		self.assertTrue(publish_mock.called)
		published_topic, published_payload = publish_mock.call_args.args
		self.assertEqual(published_topic, f'smartclass/classrooms/{self.classroom.name}/door-delay/response')
		self.assertEqual(published_payload, 10)

	def test_teacher_access_creates_timetable_session(self):
		"""Teacher access approved within timetable window creates a session."""
		today = timezone.now().date()
		weekday = today.weekday()
		
		ClassTimetableSlot.objects.create(
			classroom=self.classroom,
			weekday=weekday,
			slot_index=0,
			teacher=self.teacher,
			subject='Physics',
		)

		# Mock time to be 08:05 (within the 08:00-09:30 slot with 10 min window)
		mock_time = timezone.make_aware(datetime.combine(today, dt_time(8, 5, 0)))
		
		with patch('dashboard.mqtt_listener.timezone.now', return_value=mock_time):
			# Check if teacher access is approved first
			payload = _evaluate_teacher_access(
				classroom=self.classroom,
				teacher_rfid=self.teacher.rfid_number,
				event_time=mock_time,
			)
			self.assertTrue(payload['approved'], f"Teacher access not approved: {payload}")

			with patch('dashboard.mqtt_listener.publish_custom_topic') as mock_publish:
				process_mqtt_payload(
					f'smartclass/classrooms/{self.classroom.name}/access/request',
					json.dumps({'teacher_rfid': self.teacher.rfid_number}).encode(),
				)

		session = Session.objects.filter(classroom=self.classroom).first()
		self.assertIsNotNone(session)
		self.assertEqual(session.session_type, 'class')
		self.assertEqual(session.access_type, 'timetable')
		self.assertEqual(session.teacher, self.teacher)
		self.assertTrue(session.start_time)

	def test_teacher_access_creates_out_of_schedule_session(self):
		"""Out-of-schedule access creates session with correct type."""
		ImmediateTeacherAccessGrant.objects.create(
			teacher=self.teacher,
			is_active=True,
			expires_at=timezone.now() + timedelta(hours=1),
		)

		with patch('dashboard.mqtt_listener.publish_custom_topic'):
			process_mqtt_payload(
				f'smartclass/classrooms/{self.classroom.name}/access/request',
				json.dumps({'teacher_rfid': self.teacher.rfid_number}).encode(),
			)

		session = Session.objects.filter(classroom=self.classroom).first()
		self.assertIsNotNone(session)
		self.assertEqual(session.session_type, 'class')
		self.assertEqual(session.access_type, 'out_of_schedule')
		self.assertEqual(session.teacher, self.teacher)

	def test_admin_access_creates_inspection_session(self):
		"""Admin access creates inspection session without time restrictions."""
		admin = Staff.objects.create(
			name='Admin User',
			email='admin@example.com',
			role='ADMIN',
			id_number='A-001',
			rfid_number='RFID-ADMIN-1',
		)

		with patch('dashboard.mqtt_listener.publish_custom_topic'):
			process_mqtt_payload(
				f'smartclass/classrooms/{self.classroom.name}/access/request',
				json.dumps({'teacher_rfid': admin.rfid_number}).encode(),
			)

		session = Session.objects.filter(classroom=self.classroom).first()
		self.assertIsNotNone(session)
		self.assertEqual(session.session_type, 'inspection')
		self.assertEqual(session.access_type, 'none')
		self.assertEqual(session.teacher, admin)
		self.assertTrue(session.is_closed)
		self.assertIsNone(session.expected_report_time)
		self.assertIsNotNone(session.ended_at)
		self.assertFalse(AttendanceReport.objects.filter(session=session).exists())

	def test_attendance_request_adds_students_to_open_session(self):
		"""Attendance request adds students to the open session."""
		student1 = Student.objects.create(
			name='Student A',
			email='stua@example.com',
			specialization='INFO',
			year=2,
			student_card_id='CARD-A',
			rfid_number='RFID-STUD-A',
		)
		student2 = Student.objects.create(
			name='Student B',
			email='stub@example.com',
			specialization='INFO',
			year=2,
			student_card_id='CARD-B',
			rfid_number='RFID-STUD-B',
		)

		session = Session.objects.create(
			classroom=self.classroom,
			teacher=self.teacher,
			start_time=timezone.now(),
			session_type='class',
			access_type='timetable',
		)

		with patch('dashboard.mqtt_listener.publish_custom_topic'):
			process_mqtt_payload(
				f'smartclass/classrooms/{self.classroom.name}/attendance/request',
				json.dumps({
					'student_rfids': [student1.rfid_number, student2.rfid_number],
					'event': 'attendance_request'
				}).encode(),
			)

		session.refresh_from_db()
		self.assertEqual(session.students.count(), 2)
		self.assertIn(student1, session.students.all())
		self.assertIn(student2, session.students.all())

	def test_attendance_request_with_no_open_session_logs_warning(self):
		"""Attendance request with no open session logs a warning."""
		student = Student.objects.create(
			name='Student',
			email='stu@example.com',
			specialization='INFO',
			year=2,
			student_card_id='CARD-S',
			rfid_number='RFID-STUD-S',
		)

		with patch('dashboard.mqtt_listener.logger') as mock_logger:
			with patch('dashboard.mqtt_listener.publish_custom_topic'):
				process_mqtt_payload(
					f'smartclass/classrooms/{self.classroom.name}/attendance/request',
					json.dumps({'student_rfids': [student.rfid_number]}).encode(),
				)
			mock_logger.warning.assert_called()

	def test_attendance_request_logs_arrival_times(self):
		"""Attendance request creates StudentSessionAttendance records with arrival times."""
		from dashboard.models import StudentSessionAttendance
		
		student1 = Student.objects.create(
			name='Student A',
			email='stua@example.com',
			specialization='INFO',
			year=2,
			student_card_id='CARD-A',
			rfid_number='RFID-STUD-A',
		)
		student2 = Student.objects.create(
			name='Student B',
			email='stub@example.com',
			specialization='INFO',
			year=2,
			student_card_id='CARD-B',
			rfid_number='RFID-STUD-B',
		)

		session = Session.objects.create(
			classroom=self.classroom,
			teacher=self.teacher,
			start_time=timezone.now(),
			session_type='class',
			access_type='timetable',
		)

		now = timezone.now()
		with patch('dashboard.mqtt_listener.timezone.now', return_value=now):
			with patch('dashboard.mqtt_listener.publish_custom_topic'):
				process_mqtt_payload(
					f'smartclass/classrooms/{self.classroom.name}/attendance/request',
					json.dumps({
						'student_rfids': [student1.rfid_number, student2.rfid_number],
						'event': 'attendance_request'
					}).encode(),
				)

		# Verify StudentSessionAttendance records were created
		attendance_records = StudentSessionAttendance.objects.filter(session=session).order_by('arrival_time')
		self.assertEqual(attendance_records.count(), 2)
		
		# Check first student
		att1 = attendance_records[0]
		self.assertEqual(att1.student, student1)
		self.assertEqual(att1.arrival_time, now)
		
		# Check second student
		att2 = attendance_records[1]
		self.assertEqual(att2.student, student2)
		self.assertEqual(att2.arrival_time, now)

