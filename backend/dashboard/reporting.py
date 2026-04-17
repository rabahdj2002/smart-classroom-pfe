from io import BytesIO
from datetime import timedelta

from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    line_height = 16

    title = f"Attendance Report - {report.classroom.name}"
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(40, y, title)
    y -= line_height * 2

    pdf.setFont('Helvetica', 10)
    metadata = [
        f"Generated: {timezone.localtime(report.generated_at).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Session start: {timezone.localtime(report.session_start).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Auto report time: {timezone.localtime(report.session_end).strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {report.duration_minutes} minutes",
        f"Teacher: {report.teacher.name if report.teacher else 'Not assigned'}",
        f"Students count: {report.total_students}",
        f"Staff count: {report.total_staff}",
    ]

    for line in metadata:
        pdf.drawString(40, y, line)
        y -= line_height

    y -= line_height
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(40, y, 'Details')
    y -= line_height

    pdf.setFont('Helvetica', 9)
    for raw_line in report.details.splitlines():
        chunks = [raw_line[i:i + 115] for i in range(0, len(raw_line), 115)] or ['']
        for chunk in chunks:
            if y < 50:
                pdf.showPage()
                y = height - 50
                pdf.setFont('Helvetica', 9)
            pdf.drawString(40, y, chunk)
            y -= 12

    pdf.save()
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
    settings_obj = settings_obj or get_system_settings()
    start_candidate = session.start_time
    classroom = session.classroom

    planned_end = start_candidate + timedelta(minutes=settings_obj.auto_finish_minutes)
    session_end = session_end or planned_end

    student_names = sorted(set(session.students.values_list('name', flat=True)) - {None})
    teacher = session.teacher
    staff_names = [teacher.name] if teacher else []

    duration_minutes = settings_obj.auto_finish_minutes

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
