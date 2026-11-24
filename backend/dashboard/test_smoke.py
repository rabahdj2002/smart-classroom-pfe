from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AttendanceReport, Classroom, Session, Specialization, Staff, Student


class PageSmokeTests(TestCase):
    """Every page renders for a portal admin and is protected from everyone else."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user('admin', 'admin@example.com', 'pass12345', is_staff=True)
        cls.plain = User.objects.create_user('plain', 'plain@example.com', 'pass12345')
        cls.spec, _ = Specialization.objects.get_or_create(code='INFO', defaults={'name': 'Computer Science'})
        cls.teacher = Staff.objects.create(name='Prof One', email='prof@example.com', role='PROF', id_number='T-1', rfid_number='RF-T-1')
        cls.student = Student.objects.create(name='Stu One', email='stu@example.com', specialization='INFO', year='L2', student_card_id='C-1', rfid_number='RF-S-1')
        cls.room = Classroom.objects.create(name='D3', building='B', floor='1', capacity=40)
        cls.session = Session.objects.create(classroom=cls.room, teacher=cls.teacher, start_time=timezone.now() - timedelta(minutes=30))
        cls.session.students.add(cls.student)
        cls.closed = Session.objects.create(classroom=cls.room, teacher=cls.teacher, start_time=timezone.now() - timedelta(hours=3), is_closed=True, ended_at=timezone.now() - timedelta(hours=1))
        cls.report = AttendanceReport.objects.create(session=cls.closed, classroom=cls.room, teacher=cls.teacher, session_start=cls.closed.start_time, session_end=cls.closed.ended_at, duration_minutes=120, total_students=1, total_staff=1)

    def admin_pages(self):
        return [
            reverse('dashboard'), reverse('personal_info'), reverse('mqtt_docs'), reverse('temperature_settings'),
            reverse('classes'), reverse('add_class'), reverse('edit_class', args=[self.room.id]),
            reverse('classroom_detail', args=[self.room.id]), reverse('classroom_timetable', args=[self.room.id]),
            reverse('sessions'), reverse('add_session'), reverse('edit_session', args=[self.session.id]),
            reverse('session_detail', args=[self.session.id]), reverse('session_detail', args=[self.closed.id]),
            reverse('students'), reverse('add_student'), reverse('edit_student', args=[self.student.id]),
            reverse('student_detail', args=[self.student.id]), reverse('specializations'), reverse('add_specialization'),
            reverse('edit_specialization', args=[self.spec.id]),
            reverse('staff'), reverse('add_staff'), reverse('edit_staff', args=[self.teacher.id]),
        ]

    def test_all_pages_render_for_admin(self):
        self.client.force_login(self.admin)
        for url in self.admin_pages():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonymous_users_are_redirected_to_login(self):
        for url in self.admin_pages():
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 302)
                self.assertTrue(resp['Location'].startswith('/login/'))

    def test_non_staff_users_are_rejected(self):
        self.client.force_login(self.plain)
        resp = self.client.get(reverse('dashboard'))
        self.assertRedirects(resp, reverse('login'), fetch_redirect_response=False)

    def test_list_filters_and_search_do_not_crash(self):
        self.client.force_login(self.admin)
        for url, params in [
            ('classes', {'q': 'D3', 'usage': 'unused', 'door': 'closed', 'min_capacity': 'abc', 'max_capacity': '-1'}),
            ('sessions', {'classroom': 'x', 'start_date': 'not-a-date', 'end_date': '2026-13-45', 'order': 'weird', 'page': '999'}),
            ('students', {'q': 'Stu', 'year': 'ZZ', 'page': 'abc'}),
            ('staff', {'q': 'Prof', 'role': 'NOPE', 'page': '-3'}),
        ]:
            with self.subTest(url=url, params=params):
                self.assertEqual(self.client.get(reverse(url), params).status_code, 200)

    def test_missing_objects_return_404(self):
        self.client.force_login(self.admin)
        for name in ['classroom_detail', 'edit_class', 'session_detail', 'edit_session', 'student_detail', 'edit_student', 'edit_staff', 'classroom_timetable']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[99999])).status_code, 404)

    def test_exports_in_every_format(self):
        self.client.force_login(self.admin)
        for name in ['export_classes', 'export_sessions', 'export_students', 'export_staff']:
            for fmt in ['json', 'csv', 'xlsx', 'pdf']:
                with self.subTest(name=name, fmt=fmt):
                    resp = self.client.get(reverse(name, args=[fmt]))
                    self.assertEqual(resp.status_code, 200)
                    self.assertGreater(len(resp.content), 0)

    def test_unknown_export_format_is_handled(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('export_students', args=['exe']))
        self.assertIn(resp.status_code, (302, 400))

    def test_report_pdf_download(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('download_report_pdf', args=[self.report.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_destructive_endpoints_ignore_get(self):
        self.client.force_login(self.admin)
        self.client.get(reverse('delete_session', args=[self.session.id]))
        self.client.get(reverse('delete_staff', args=[self.teacher.id]))
        self.client.get(reverse('end_session', args=[self.session.id]))
        self.assertTrue(Session.objects.filter(id=self.session.id, is_closed=False).exists())
        self.assertTrue(Staff.objects.filter(id=self.teacher.id).exists())

    def test_end_session_generates_report_and_frees_room(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('end_session', args=[self.session.id]))
        self.session.refresh_from_db()
        self.assertTrue(self.session.is_closed)
        self.assertTrue(AttendanceReport.objects.filter(session=self.session).exists())

    def test_login_rejects_open_redirect(self):
        resp = self.client.post(reverse('login'), {'username': 'admin', 'password': 'pass12345', 'next': 'https://evil.example.com/'})
        self.assertRedirects(resp, '/', fetch_redirect_response=False)

    def test_login_with_wrong_password_shows_error(self):
        resp = self.client.post(reverse('login'), {'username': 'admin', 'password': 'nope'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid credentials')
