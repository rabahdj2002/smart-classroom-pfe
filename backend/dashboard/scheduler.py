import logging
import os
import sys
import threading
import time

from django.conf import settings
from django.utils import timezone

from .reporting import auto_finish_active_classrooms, try_claim_auto_finish_run

logger = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _should_start_scheduler():
    if not getattr(settings, 'DASHBOARD_INTERNAL_SCHEDULER_ENABLED', True):
        return False

    # Avoid duplicate thread from Django autoreload parent process.
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver' and os.environ.get('RUN_MAIN') != 'true':
        return False

    management_commands_without_scheduler = {
        'makemigrations',
        'migrate',
        'collectstatic',
        'shell',
        'dbshell',
        'createsuperuser',
        'check',
        'test',
        'loaddata',
        'dumpdata',
    }
    if len(sys.argv) > 1 and sys.argv[1] in management_commands_without_scheduler:
        return False

    return True


def _run_scheduler_loop():
    poll_seconds = max(5, int(getattr(settings, 'DASHBOARD_INTERNAL_SCHEDULER_POLL_SECONDS', 20)))

    while True:
        try:
            now = timezone.now()
            claimed, _, _ = try_claim_auto_finish_run(now=now)
            if claimed:
                auto_finish_active_classrooms(now=now)
        except Exception:
            logger.exception('Internal auto-finish scheduler tick failed.')

        time.sleep(poll_seconds)


def start_internal_scheduler():
    global _scheduler_started

    if not _should_start_scheduler():
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        thread = threading.Thread(
            target=_run_scheduler_loop,
            name='dashboard-internal-scheduler',
            daemon=True,
        )
        thread.start()
        _scheduler_started = True
