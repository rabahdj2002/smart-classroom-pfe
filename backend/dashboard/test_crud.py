from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Classroom, Session, Specialization, Staff, Student


class CrudFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user('admin', password='pass12345', is_staff=True)
        cls.spec, _ = Specialization.objects.get_or_create(code='INFO', defaults={'name': 'Computer Science'})

    def setUp(self):
        self.client.force_login(self.admin)

    def student_payload(self, **overrides):
        data = {'name': 'New Student', 'email': 'new@example.com', 'specialization': 'INFO', 'year': 'M1',
                'student_card_id': 'C-9', 'rfid_number': 'RF-9', 'is_active': 'on'}
        data.update(overrides)
        return data

    def staff_payload(self, **overrides):
        data = {'name': 'New Prof', 'email': 'prof@example.com', 'role': 'PROF', 'id_number': 'T-9', 'rfid_number': 'RF-T-9'}
        data.update(overrides)
        return data

    def test_classroom_create_edit_and_bulk_delete(self):
        self.client.post(reverse('add_class'), {'name': 'C1', 'building': 'B', 'floor': '2', 'capacity': '35'})
        room = Classroom.objects.get(name='C1')
        self.assertEqual(room.capacity, 35)
        self.client.post(reverse('edit_class', args=[room.id]), {'name': 'C1-renamed', 'building': 'B', 'floor': '2', 'capacity': '50'})
        room.refresh_from_db()
        self.assertEqual((room.name, room.capacity), ('C1-renamed', 50))
        self.client.post(reverse('bulk_delete_classes'), {'class_ids': [room.id]})
        self.assertFalse(Classroom.objects.filter(id=room.id).exists())

    def test_classroom_invalid_capacity_is_rejected_without_crash(self):
        resp = self.client.post(reverse('add_class'), {'name': 'Bad', 'capacity': 'lots'})
        self.assertLess(resp.status_code, 500)
        self.assertFalse(Classroom.objects.filter(name='Bad', capacity=0).exists())

    def test_student_create_edit_and_duplicate_rejected(self):
        self.client.post(reverse('add_student'), self.student_payload())
        student = Student.objects.get(email='new@example.com')
        resp = self.client.post(reverse('add_student'), self.student_payload(name='Clone'))
        self.assertLess(resp.status_code, 500)
        self.assertEqual(Student.objects.filter(email='new@example.com').count(), 1)
        self.client.post(reverse('edit_student', args=[student.id]), self.student_payload(name='Renamed', year='M2'))
        student.refresh_from_db()
        self.assertEqual((student.name, student.year), ('Renamed', 'M2'))
        self.client.post(reverse('bulk_delete_students'), {'student_ids': [student.id]})
        self.assertFalse(Student.objects.filter(id=student.id).exists())

    def test_staff_create_edit_duplicate_and_delete(self):
        self.client.post(reverse('add_staff'), self.staff_payload())
        member = Staff.objects.get(email='prof@example.com')
        resp = self.client.post(reverse('add_staff'), self.staff_payload(name='Dup'))
        self.assertLess(resp.status_code, 500)
        self.assertEqual(Staff.objects.filter(email='prof@example.com').count(), 1)
        self.client.post(reverse('edit_staff', args=[member.id]), self.staff_payload(name='Prof Renamed'))
        member.refresh_from_db()
        self.assertEqual(member.name, 'Prof Renamed')
        self.client.post(reverse('delete_staff', args=[member.id]))
        self.assertFalse(Staff.objects.filter(id=member.id).exists())

    def test_specialization_create_and_delete(self):
        self.client.post(reverse('add_specialization'), {'code': 'ROBO', 'name': 'Robotics', 'is_active': 'on'})
        spec = Specialization.objects.get(code='ROBO')
        self.client.post(reverse('delete_specialization', args=[spec.id]))
        self.assertFalse(Specialization.objects.filter(id=spec.id).exists())

    def test_session_create_and_delete(self):
        room = Classroom.objects.create(name='S1')
        teacher = Staff.objects.create(name='T', email='t@example.com', role='PROF', id_number='T-1', rfid_number='R-1')
        self.client.post(reverse('add_session'), {'classroom_id': room.id, 'teacher_id': teacher.id, 'session_type': 'class', 'start_time': '2026-11-24T08:00'})
        session = Session.objects.get(classroom=room)
        self.assertEqual(session.teacher, teacher)
        self.client.post(reverse('delete_session', args=[session.id]))
        self.assertFalse(Session.objects.filter(id=session.id).exists())

    def test_session_with_missing_classroom_is_rejected(self):
        resp = self.client.post(reverse('add_session'), {'classroom_id': '99999', 'session_type': 'class', 'start_time': '2026-11-24T08:00'})
        self.assertLess(resp.status_code, 500)
        self.assertFalse(Session.objects.exists())

    def test_logout_requires_post(self):
        self.client.get(reverse('logout'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
