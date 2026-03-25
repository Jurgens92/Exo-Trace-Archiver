"""
Management command to run the scheduler as a standalone blocking process.

In most cases you don't need this - the scheduler starts automatically
with the Django server (runserver). This command is useful for production
deployments where you want to run the scheduler as a separate service
(e.g., systemd, Docker container).

Usage:
    python manage.py run_scheduler
    python manage.py run_scheduler --run-now
"""

import signal
import sys
import logging

from django.core.management.base import BaseCommand

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from traces.scheduler import get_interval_from_settings, _run_pull_task, _check_settings_change

logger = logging.getLogger('traces')


class Command(BaseCommand):
    help = 'Run the scheduled task scheduler as a standalone blocking process'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheduler = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-now',
            action='store_true',
            help='Run the pull task immediately in addition to scheduling'
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting Exo-Trace-Archiver scheduler (standalone mode)...")

        # Create blocking scheduler (not background)
        self.scheduler = BlockingScheduler(timezone='UTC')

        # Read interval from database settings
        hours, minutes, enabled = get_interval_from_settings()

        if not enabled:
            self.stdout.write(self.style.WARNING(
                "Scheduled pulls are disabled in settings. "
                "Scheduler will start but skip pulls until re-enabled."
            ))

        # Schedule the pull task with interval trigger
        self.scheduler.add_job(
            _run_pull_task,
            trigger=IntervalTrigger(hours=hours, minutes=minutes),
            id='message_trace_pull',
            name='Message Trace Pull',
            replace_existing=True
        )

        self.stdout.write(self.style.SUCCESS(
            f"Scheduled pulls every {hours}h {minutes}m"
        ))

        # Add a job to check for settings changes every 5 minutes
        self.scheduler.add_job(
            _check_settings_change,
            trigger=IntervalTrigger(minutes=5),
            id='settings_check',
            name='Settings Change Check',
            replace_existing=True
        )

        # Run immediately if requested
        if options['run_now']:
            self.stdout.write("Running immediate pull...")
            _run_pull_task()

        # Handle shutdown signals gracefully
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.stdout.write("Scheduler is running. Press Ctrl+C to stop.")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Scheduler stopped.")

    def _shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.stdout.write("\nShutting down scheduler...")
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        sys.exit(0)
