import csv
import json
from collections import defaultdict
from io import BytesIO, StringIO

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from .models import AttendanceReport, Classroom, Session, Staff, Student


def _json_datetime(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value).isoformat()


def _parse_datetime(value):
    if not value:
        return None

    parsed = parse_datetime(value)
    if parsed is None:
        raise ValueError(f'Invalid datetime value: {value}')
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _normalize_text(value):
    if value is None:
        return ''
    return str(value)


def _bool_text(value):
    return 'Yes' if bool(value) else 'No'


def _student_row(student):
    return [
        student.id,
        student.name,
        student.email,
        student.get_specialization_display(),
        student.year,
        student.student_card_id,
        student.rfid_number,
    ]


def _staff_row(staff):
    return [
        staff.id,
        staff.name,
        staff.email,
        staff.get_role_display(),
        staff.id_number,
        staff.rfid_number,
        _bool_text(staff.can_open_door),
        _bool_text(staff.can_control_lights),
        _bool_text(staff.can_control_projector),
        _bool_text(staff.can_manage_classrooms),
        _bool_text(staff.can_manage_staff),
    ]


def _classroom_row(classroom):
    return [
        classroom.id,
        classroom.name,
        _bool_text(classroom.occupied),
        _bool_text(classroom.lights_on),
        _bool_text(classroom.projector_on),
        _bool_text(classroom.door),
        _bool_text(classroom.smoke_detected),
        _bool_text(classroom.danger_indicator),
        _json_datetime(classroom.session_started_at),
        _json_datetime(classroom.last_activity_at),
    ]


def _session_row(session):
    report = getattr(session, 'report', None)
    students = list(session.students.order_by('name').values_list('name', flat=True))
    return [
        session.id,
        session.classroom.name if session.classroom_id else '',
        session.get_session_type_display(),
        session.get_access_type_display(),
        session.teacher.name if session.teacher_id else 'Not assigned',
        _json_datetime(session.start_time),
        _json_datetime(session.expected_report_time),
        _json_datetime(session.ended_at),
        _bool_text(session.is_closed),
        len(students),
        ', '.join(students),
        f'Report #{report.id}' if report else 'No report',
        report.duration_minutes if report else '',
        report.total_students if report else '',
        report.total_staff if report else '',
    ]


def build_backup_payload():
    staff_queryset = Staff.objects.order_by('id')
    student_queryset = Student.objects.order_by('id')
    classroom_queryset = Classroom.objects.order_by('id')
    session_queryset = Session.objects.select_related('classroom', 'teacher').prefetch_related('students').order_by('id')
    report_queryset = AttendanceReport.objects.select_related('session', 'classroom', 'teacher').order_by('id')

    return {
        'version': 1,
        'generated_at': _json_datetime(timezone.now()),
        'staff': [
            {
                'id': staff.id,
                'name': staff.name,
                'email': staff.email,
                'role': staff.role,
                'id_number': staff.id_number,
                'rfid_number': staff.rfid_number,
                'can_open_door': staff.can_open_door,
                'can_control_lights': staff.can_control_lights,
                'can_control_projector': staff.can_control_projector,
                'can_manage_classrooms': staff.can_manage_classrooms,
                'can_manage_staff': staff.can_manage_staff,
            }
            for staff in staff_queryset
        ],
        'students': [
            {
                'id': student.id,
                'name': student.name,
                'email': student.email,
                'specialization': student.specialization,
                'year': student.year,
                'student_card_id': student.student_card_id,
                'rfid_number': student.rfid_number,
            }
            for student in student_queryset
        ],
        'classrooms': [
            {
                'id': classroom.id,
                'name': classroom.name,
                'occupied': classroom.occupied,
                'lights_on': classroom.lights_on,
                'door': classroom.door,
                'projector_on': classroom.projector_on,
                'smoke_detected': classroom.smoke_detected,
                'session_started_at': _json_datetime(classroom.session_started_at),
                'last_activity_at': _json_datetime(classroom.last_activity_at),
                'danger_indicator': classroom.danger_indicator,
            }
            for classroom in classroom_queryset
        ],
        'sessions': [
            {
                'id': session.id,
                'classroom_id': session.classroom_id,
                'teacher_id': session.teacher_id,
                'session_type': session.session_type,
                'access_type': session.access_type,
                'student_ids': list(session.students.order_by('id').values_list('id', flat=True)),
                'start_time': _json_datetime(session.start_time),
                'expected_report_time': _json_datetime(session.expected_report_time),
                'ended_at': _json_datetime(session.ended_at),
                'is_closed': session.is_closed,
                'created_at': _json_datetime(session.created_at),
            }
            for session in session_queryset
        ],
        'attendance_reports': [
            {
                'id': report.id,
                'session_id': report.session_id,
                'classroom_id': report.classroom_id,
                'teacher_id': report.teacher_id,
                'session_start': _json_datetime(report.session_start),
                'session_end': _json_datetime(report.session_end),
                'duration_minutes': report.duration_minutes,
                'total_students': report.total_students,
                'total_staff': report.total_staff,
                'details': report.details,
                'generated_at': _json_datetime(report.generated_at),
                'emailed': report.emailed,
                'email_sent_at': _json_datetime(report.email_sent_at),
                'email_error': report.email_error,
            }
            for report in report_queryset
        ],
    }


def _build_csv_response(headers, rows, filename):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _build_xlsx_response(headers, rows, sheet_name, filename):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name[:31] or 'Export'
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)

    for column_cells in worksheet.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            cell_value = '' if cell.value is None else str(cell.value)
            max_length = max(max_length, len(cell_value))
        worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)

    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _build_pdf_response(title, headers, rows, filename):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'BackupTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#1f3c88'),
        spaceAfter=10,
    )
    meta_style = ParagraphStyle(
        'BackupMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=10,
    )
    cell_style = ParagraphStyle(
        'BackupCell',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
    )

    story = [
        Paragraph(title, title_style),
        Paragraph(f'Export generated at {timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")}', meta_style),
    ]

    table_data = [[Paragraph(str(header), cell_style) for header in headers]]
    for row in rows:
        table_data.append([Paragraph(_normalize_text(value), cell_style) for value in row])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f3c88')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def build_section_export(section, export_format, queryset):
    if section == 'students':
        headers = ['ID', 'Name', 'Email', 'Specialization', 'Year', 'Student Card ID', 'RFID Number']
        rows = [_student_row(student) for student in queryset]
        title = 'Students Export'
        filename_prefix = 'students'
        sheet_name = 'Students'
    elif section == 'staff':
        headers = [
            'ID',
            'Name',
            'Email',
            'Job',
            'ID Number',
            'RFID Card Serial',
            'Can Open Door',
            'Can Control Lights',
            'Can Control Projector',
            'Can Manage Classrooms',
            'Can Manage Staff',
        ]
        rows = [_staff_row(staff) for staff in queryset]
        title = 'Staff Export'
        filename_prefix = 'staff'
        sheet_name = 'Staff'
    elif section == 'classrooms':
        headers = [
            'ID',
            'Name',
            'Occupied',
            'Lights On',
            'Projector On',
            'Door Open',
            'Smoke Detected',
            'Danger Indicator',
            'Session Started At',
            'Last Activity At',
        ]
        rows = [_classroom_row(classroom) for classroom in queryset]
        title = 'Classrooms Export'
        filename_prefix = 'classrooms'
        sheet_name = 'Classrooms'
    elif section == 'sessions':
        headers = [
            'ID',
            'Classroom',
            'Type',
            'Access Type',
            'Teacher',
            'Start Time',
            'Expected Report Time',
            'Ended At',
            'Closed',
            'Student Count',
            'Students',
            'Report',
            'Duration Minutes',
            'Total Students',
            'Total Staff',
        ]
        rows = [_session_row(session) for session in queryset]
        title = 'Sessions Export'
        filename_prefix = 'sessions'
        sheet_name = 'Sessions'
    else:
        raise ValueError(f'Unsupported export section: {section}')

    if export_format == 'csv':
        return _build_csv_response(headers, rows, f'{filename_prefix}.csv')
    if export_format == 'xlsx':
        return _build_xlsx_response(headers, rows, sheet_name, f'{filename_prefix}.xlsx')
    if export_format == 'pdf':
        return _build_pdf_response(title, headers, rows, f'{filename_prefix}.pdf')
    raise ValueError(f'Unsupported export format: {export_format}')


def build_backup_response():
    payload = build_backup_payload()
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8'),
        content_type='application/json',
    )
    generated_at = timezone.localtime(timezone.now()).strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="smart_classroom_backup_{generated_at}.json"'
    return response


def _restore_staff_item(item):
    staff = Staff.objects.create(
        id=item['id'],
        name=item['name'],
        email=item['email'],
        role=item['role'],
        id_number=item['id_number'],
        rfid_number=item['rfid_number'],
        can_open_door=bool(item.get('can_open_door')),
        can_control_lights=bool(item.get('can_control_lights')),
        can_control_projector=bool(item.get('can_control_projector')),
        can_manage_classrooms=bool(item.get('can_manage_classrooms')),
        can_manage_staff=bool(item.get('can_manage_staff')),
    )
    return staff


def _restore_student_item(item):
    return Student.objects.create(
        id=item['id'],
        name=item['name'],
        email=item['email'],
        specialization=item['specialization'],
        year=item['year'],
        student_card_id=item['student_card_id'],
        rfid_number=item['rfid_number'],
    )


def _restore_classroom_item(item):
    return Classroom.objects.create(
        id=item['id'],
        name=item['name'],
        occupied=bool(item.get('occupied')),
        lights_on=bool(item.get('lights_on')),
        door=bool(item.get('door')),
        projector_on=bool(item.get('projector_on')),
        smoke_detected=bool(item.get('smoke_detected')),
        session_started_at=_parse_datetime(item.get('session_started_at')),
        last_activity_at=_parse_datetime(item.get('last_activity_at')),
        danger_indicator=bool(item.get('danger_indicator')),
    )


def _restore_session_item(item, staff_map, student_map, classroom_map):
    classroom = classroom_map.get(item['classroom_id'])
    if not classroom:
        raise ValueError(f"Missing classroom for session {item.get('id')}")

    teacher = None
    teacher_id = item.get('teacher_id')
    if teacher_id is not None:
        teacher = staff_map.get(teacher_id)
        if teacher is None:
            raise ValueError(f"Missing teacher for session {item.get('id')}")

    session = Session.objects.create(
        id=item['id'],
        classroom=classroom,
        teacher=teacher,
        session_type=item.get('session_type', 'class'),
        access_type=item.get('access_type', 'timetable'),
        start_time=_parse_datetime(item.get('start_time')) or timezone.now(),
        expected_report_time=_parse_datetime(item.get('expected_report_time')),
        ended_at=_parse_datetime(item.get('ended_at')),
        is_closed=bool(item.get('is_closed')),
        created_at=_parse_datetime(item.get('created_at')) or timezone.now(),
    )

    student_ids = item.get('student_ids') or []
    session.students.set([student_map[student_id] for student_id in student_ids if student_id in student_map])
    return session


def _restore_report_item(item, session_map, staff_map, classroom_map):
    session = session_map.get(item['session_id'])
    if not session:
        raise ValueError(f"Missing session for report {item.get('id')}")

    classroom = classroom_map.get(item['classroom_id'])
    if not classroom:
        raise ValueError(f"Missing classroom for report {item.get('id')}")

    teacher = None
    teacher_id = item.get('teacher_id')
    if teacher_id is not None:
        teacher = staff_map.get(teacher_id)
        if teacher is None:
            raise ValueError(f"Missing teacher for report {item.get('id')}")

    return AttendanceReport.objects.create(
        id=item['id'],
        session=session,
        classroom=classroom,
        teacher=teacher,
        session_start=_parse_datetime(item.get('session_start')) or session.start_time,
        session_end=_parse_datetime(item.get('session_end')) or session.start_time,
        duration_minutes=item.get('duration_minutes') or 0,
        total_students=item.get('total_students') or 0,
        total_staff=item.get('total_staff') or 0,
        details=item.get('details', ''),
        generated_at=_parse_datetime(item.get('generated_at')) or timezone.now(),
        emailed=bool(item.get('emailed')),
        email_sent_at=_parse_datetime(item.get('email_sent_at')),
        email_error=item.get('email_error', ''),
    )


def restore_backup_from_file(uploaded_file):
    raw_content = uploaded_file.read()
    if isinstance(raw_content, bytes):
        raw_content = raw_content.decode('utf-8-sig')

    payload = json.loads(raw_content)
    if not isinstance(payload, dict):
        raise ValueError('Backup file must contain a JSON object.')

    required_sections = ['staff', 'students', 'classrooms', 'sessions', 'attendance_reports']
    for section in required_sections:
        if section not in payload:
            raise ValueError(f'Missing backup section: {section}')

    counts = defaultdict(int)

    with transaction.atomic():
        AttendanceReport.objects.all().delete()
        Session.objects.all().delete()
        Student.objects.all().delete()
        Classroom.objects.all().delete()
        Staff.objects.all().delete()

        staff_map = {}
        for item in payload.get('staff', []):
            staff = _restore_staff_item(item)
            staff_map[staff.id] = staff
            counts['staff'] += 1

        student_map = {}
        for item in payload.get('students', []):
            student = _restore_student_item(item)
            student_map[student.id] = student
            counts['students'] += 1

        classroom_map = {}
        for item in payload.get('classrooms', []):
            classroom = _restore_classroom_item(item)
            classroom_map[classroom.id] = classroom
            counts['classrooms'] += 1

        session_map = {}
        for item in payload.get('sessions', []):
            session = _restore_session_item(item, staff_map, student_map, classroom_map)
            session_map[session.id] = session
            counts['sessions'] += 1

        for item in payload.get('attendance_reports', []):
            _restore_report_item(item, session_map, staff_map, classroom_map)
            counts['attendance_reports'] += 1

    return {
        'staff': counts['staff'],
        'students': counts['students'],
        'classrooms': counts['classrooms'],
        'sessions': counts['sessions'],
        'attendance_reports': counts['attendance_reports'],
    }