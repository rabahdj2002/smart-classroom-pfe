from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.reporting import auto_finish_active_classrooms, try_claim_auto_finish_run


class Command(BaseCommand):
    help = 'Auto-finish classroom sessions that exceeded the configured duration and generate attendance reports.'

    def handle(self, *args, **options):
        now = timezone.now()

        claimed, settings_obj, next_allowed = try_claim_auto_finish_run(now=now)

        if not settings_obj.auto_finish_enabled:
            self.stdout.write(self.style.WARNING('Auto-finish is disabled in settings.'))
            return

        if not claimed and next_allowed:
            self.stdout.write(
                self.style.WARNING(
                    f'Skipped: next execution allowed at {timezone.localtime(next_allowed):%Y-%m-%d %H:%M:%S} '
                    f'(interval: {settings_obj.cron_interval_minutes} min).'
                )
            )
            return

        reports = auto_finish_active_classrooms(now=now)
        self.stdout.write(self.style.SUCCESS(f'Finished {len(reports)} classroom session(s).'))
        for report in reports:
            self.stdout.write(
                f'- Report #{report.id} | {report.classroom.name} | {report.session_start:%Y-%m-%d %H:%M} -> {report.session_end:%H:%M}'
            )
