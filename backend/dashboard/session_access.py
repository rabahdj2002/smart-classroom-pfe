from datetime import datetime, time as dt_time, timedelta

from django.utils import timezone

from .models import ClassTimetableSlot, Staff, SystemSettings

TIMETABLE_SLOT_STARTS = [
    dt_time(8, 0),
    dt_time(9, 30),
    dt_time(11, 0),
    dt_time(12, 30),
    dt_time(14, 0),
    dt_time(15, 30),
]
TIMETABLE_SLOT_DURATION_MINUTES = 90
RAMADAN_SLOT_DURATION_MINUTES = 75


def _slot_bounds(reference_date, slot_index, settings_obj):
    if settings_obj.ramadan_mode:
        start_time = settings_obj.ramadan_start_time or dt_time(8, 30)
        duration = RAMADAN_SLOT_DURATION_MINUTES
        slot_start_dt = datetime.combine(reference_date, start_time) + timedelta(minutes=slot_index * duration)
        slot_start = timezone.make_aware(slot_start_dt, timezone.get_current_timezone())
    else:
        slot_start_naive = datetime.combine(reference_date, TIMETABLE_SLOT_STARTS[slot_index])
        slot_start = timezone.make_aware(slot_start_naive, timezone.get_current_timezone())
        duration = TIMETABLE_SLOT_DURATION_MINUTES

    slot_end = slot_start + timedelta(minutes=duration)
    return slot_start, slot_end


def _get_system_settings():
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return settings_obj


def resolve_session_access_type(classroom, teacher, event_time, session_type='class'):
    if session_type != 'class':
        return 'out_of_schedule'

    if not teacher or not isinstance(teacher, Staff) or teacher.role != 'PROF':
        return 'out_of_schedule'

    settings_obj = _get_system_settings()
    window_minutes = settings_obj.teacher_access_window_minutes or 10
    checked_at = timezone.localtime(event_time)
    weekday = checked_at.weekday()

    teacher_slots = ClassTimetableSlot.objects.filter(
        classroom=classroom,
        weekday=weekday,
        teacher=teacher,
    ).order_by('slot_index')

    for slot in teacher_slots:
        slot_start, slot_end = _slot_bounds(checked_at.date(), slot.slot_index, settings_obj)
        lower_bound = slot_start - timedelta(minutes=window_minutes)
        upper_bound = slot_end + timedelta(minutes=window_minutes)
        if lower_bound <= event_time <= upper_bound:
            return 'scheduled'

    return 'out_of_schedule'
