from io import BytesIO
from datetime import timedelta
from html import escape

from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch

from .models import AttendanceReport, Classroom, Session, SystemSettings


def get_system_settings():
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return settings_obj


def try_claim_auto_finish_run(now=None):
    now = now or timezone.now()
    settings_obj = get_system_settings()

    with transaction.atomic():
        locked = SystemSettings.objects.select_for_update().get(pk=settings_obj.pk)

        if not locked.auto_finish_enabled:
            return False, locked, None

        interval_minutes = max(1, locked.cron_interval_minutes)
        next_allowed = None
        if locked.last_auto_finish_run_at:
            next_allowed = locked.last_auto_finish_run_at + timedelta(minutes=interval_minutes)
            if now < next_allowed:
                return False, locked, next_allowed

        locked.last_auto_finish_run_at = now
        locked.save(update_fields=['last_auto_finish_run_at'])

    return True, settings_obj, None


def _build_report_details(staff_names, student_names, session):
    lines = []
    lines.append("Total attendance records: session-based summary")
    lines.append(f"Staff present ({len(staff_names)}): {', '.join(staff_names) if staff_names else 'None'}")
    lines.append(f"Students present ({len(student_names)}): {', '.join(student_names) if student_names else 'None'}")
    lines.append("Event timeline:")
    lines.append(f"- Session started at {timezone.localtime(session.start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    if session.teacher:
        lines.append(f"- Teacher assigned: {session.teacher.name}")
    if session.students.exists():
        for student_name in session.students.values_list('name', flat=True):
            lines.append(f"- Student: {student_name}")

    return "\n".join(lines)


def _build_pdf_attachment(report):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=3,
        fontName='Helvetica-Bold',
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=12,
        fontName='Helvetica',
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold',
    )

    story = []

    story.append(Paragraph('Attendance Report', title_style))
    story.append(Paragraph(f"Session #{report.session_id or 'N/A'}", subtitle_style))

    session_start_local = timezone.localtime(report.session_start)
    session_end_local = timezone.localtime(report.session_end)

    header_data = [
        ['Date', escape(session_start_local.strftime('%Y-%m-%d')), 'Classroom', escape(report.classroom.name)],
        ['Start Time', escape(session_start_local.strftime('%H:%M:%S')), 'End Time', escape(session_end_local.strftime('%H:%M:%S'))],
        ['Teacher', escape(report.teacher.name if report.teacher else 'Not assigned'), 'Duration', escape(f'{report.duration_minutes} minutes')],
        ['Generated At', escape(timezone.localtime(report.generated_at).strftime('%Y-%m-%d %H:%M:%S')), 'Students', escape(str(report.total_students))],
    ]

    header_table = Table(header_data, colWidths=[1.2 * inch, 2.0 * inch, 1.2 * inch, 2.2 * inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#0f172a')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#bfdbfe')),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor('#bfdbfe')),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#dbeafe')),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.22 * inch))

    story.append(Paragraph('Student Roster', heading_style))
    students = []
    if report.session_id:
        students = list(report.session.students.order_by('name'))

    roster_data = [['Student ID', 'Student Name', 'Speciality']]
    for student in students:
        roster_data.append([
            escape(student.student_card_id or str(student.id)),
            escape(student.name),
            escape(student.get_specialization_display()),
        ])

    if len(roster_data) == 1:
        roster_data.append(['-', 'No students linked to this session', '-'])

    roster_table = Table(roster_data, colWidths=[1.5 * inch, 2.9 * inch, 2.2 * inch])
    roster_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1f2937')),
        ('FONTSIZE', (0, 1), (-1, -1), 9.2),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d1d5db')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.append(roster_table)
    story.append(Spacer(1, 0.18 * inch))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#94a3b8'),
        alignment=1,
    )
    story.append(Paragraph('Smart Classroom Control System | Confidential', footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def build_report_pdf_attachment(report):
    return _build_pdf_attachment(report)


def maybe_email_report(report, settings_obj=None, force=False):
    settings_obj = settings_obj or get_system_settings()

    if not force and not settings_obj.email_reports_enabled:
        return
    if not report.teacher or not report.teacher.email:
        report.email_error = 'No teacher email available for this report.'
        report.save(update_fields=['email_error'])
        return
    if not settings_obj.smtp_host or not settings_obj.smtp_from_email:
        report.email_error = 'SMTP host/from email are not configured.'
        report.save(update_fields=['email_error'])
        return

    try:
        connection = get_connection(
            host=settings_obj.smtp_host,
            port=settings_obj.smtp_port,
            username=settings_obj.smtp_username or None,
            password=settings_obj.smtp_password or None,
            use_tls=settings_obj.smtp_use_tls,
            fail_silently=False,
        )

        subject = f"Attendance Report - {report.classroom.name}"
        body = (
            f"Hello {report.teacher.name},\n\n"
            f"Please find attached the attendance report for {report.classroom.name}.\n"
            f"Session started at: {timezone.localtime(report.session_start).strftime('%Y-%m-%d %H:%M')}\n"
            f"Report was generated automatically after {report.duration_minutes} minutes.\n\n"
            "Regards,\nSmart Classroom System"
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings_obj.smtp_from_email,
            to=[report.teacher.email],
            connection=connection,
        )
        email.attach(
            filename=f"attendance_report_{report.id}.pdf",
            content=_build_pdf_attachment(report),
            mimetype='application/pdf',
        )
        email.send(fail_silently=False)

        report.emailed = True
        report.email_error = ''
        report.email_sent_at = timezone.now()
        report.save(update_fields=['emailed', 'email_error', 'email_sent_at'])
    except Exception as exc:
        report.email_error = str(exc)
        report.save(update_fields=['email_error'])


def generate_attendance_report_for_session(session, session_end=None, settings_obj=None):
    if session.session_type == 'inspection':
        session.is_closed = True
        if session.ended_at is None:
            session.ended_at = session.start_time
        session.expected_report_time = None
        session.save(update_fields=['ended_at', 'expected_report_time', 'is_closed'])
        return None

    settings_obj = settings_obj or get_system_settings()
    start_candidate = session.start_time
    classroom = session.classroom

    planned_end = start_candidate + timedelta(minutes=settings_obj.auto_finish_minutes)
    session_end = session_end or planned_end

    student_names = sorted(set(session.students.values_list('name', flat=True)) - {None})
    teacher = session.teacher
    staff_names = [teacher.name] if teacher else []

    duration_minutes = settings_obj.auto_finish_minutes

    # Check if report already exists for this session
    existing_report = AttendanceReport.objects.filter(session=session).first()
    
    if existing_report:
        # Update existing report with new end time
        report = existing_report
        report.session_end = session_end
        report.save(update_fields=['session_end'])
    else:
        # Create new report
        report = AttendanceReport.objects.create(
            session=session,
            classroom=classroom,
            teacher=teacher,
            session_start=start_candidate,
            session_end=session_end,
            duration_minutes=duration_minutes,
            total_students=len(student_names),
            total_staff=1 if teacher else 0,
            details=_build_report_details(staff_names, student_names, session),
        )

    session.teacher = teacher
    session.ended_at = session_end
    session.expected_report_time = planned_end
    session.is_closed = True
    session.save(update_fields=['teacher', 'ended_at', 'expected_report_time', 'is_closed'])

    maybe_email_report(report, settings_obj=settings_obj)
    return report


def auto_finish_active_classrooms(now=None):
    now = now or timezone.now()
    settings_obj = get_system_settings()

    if not settings_obj.auto_finish_enabled:
        return []

    finished_reports = []
    open_sessions = Session.objects.select_related('classroom', 'teacher').filter(is_closed=False)

    for session in open_sessions:
        if session.session_type == 'inspection':
            continue

        scheduled_report_time = session.start_time + timedelta(minutes=settings_obj.auto_finish_minutes)
        if session.expected_report_time != scheduled_report_time:
            session.expected_report_time = scheduled_report_time
            session.save(update_fields=['expected_report_time'])

        if now < scheduled_report_time:
            continue

        existing_report = AttendanceReport.objects.filter(session=session).first()
        if existing_report:
            session.is_closed = True
            session.ended_at = existing_report.session_end
            session.save(update_fields=['is_closed', 'ended_at'])
            continue

        report = generate_attendance_report_for_session(
            session,
            session_end=scheduled_report_time,
            settings_obj=settings_obj,
        )
        if not report:
            continue

        # Keep classroom occupancy synced with active session existence.
        classroom = session.classroom
        has_open = Session.objects.filter(classroom=classroom, is_closed=False).exists()
        if not has_open:
            classroom.occupied = False
            classroom.session_started_at = None
            classroom.last_activity_at = None
            classroom.save(update_fields=['occupied', 'session_started_at', 'last_activity_at'])

        finished_reports.append(report)

    return finished_reports
