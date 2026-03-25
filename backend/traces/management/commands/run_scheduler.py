"""
Management command to run the scheduled task scheduler.

This command starts an in-process scheduler that runs the message trace
pull task at a configurable interval (default: every 24 hours).

The scheduler reads its configuration from the database (AppSettings)
and dynamically reschedules when settings change.

Usage:
    python manage.py run_scheduler

For production deployments, consider:
1. Running as a systemd service
2. Using Celery Beat for more robust scheduling
3. Using cron with the pull_traces command directly

The scheduler uses APScheduler for simplicity and reliability.
It's suitable for single-instance deployments.
"""

import signal
import sys
import logging

from django.core.management.base import BaseCommand

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from traces.tasks import pull_message_traces

logger = logging.getLogger('traces')


class Command(BaseCommand):
    help = 'Run the scheduled task scheduler for message trace pulls'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheduler = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--run-now',
            action='store_true',
            help='Run the pull task immediately in addition to scheduling'
        )

    def _get_interval_from_settings(self):
        """Read pull interval from database AppSettings."""
        from accounts.models import AppSettings
        try:
            app_settings = AppSettings.get_settings()
            hours = app_settings.scheduled_pull_interval_hours
            minutes = app_settings.scheduled_pull_interval_minutes
            enabled = app_settings.scheduled_pull_enabled
        except Exception as e:
            logger.warning(f"Could not load AppSettings, using defaults: {e}")
            hours = 24
            minutes = 0
            enabled = True
        return hours, minutes, enabled

    def handle(self, *args, **options):
        self.stdout.write("Starting Exo-Trace-Archiver scheduler...")

        # Create scheduler
        self.scheduler = BlockingScheduler(timezone='UTC')

        # Read interval from database settings
        hours, minutes, enabled = self._get_interval_from_settings()

        if not enabled:
            self.stdout.write(self.style.WARNING(
                "Scheduled pulls are disabled in settings. "
                "Scheduler will start but check periodically for re-enablement."
            ))

        # Schedule the pull task with interval trigger
        self.scheduler.add_job(
            self._run_pull_task,
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
            self._check_settings_change,
            trigger=IntervalTrigger(minutes=5),
            id='settings_check',
            name='Settings Change Check',
            replace_existing=True
        )

        # Run immediately if requested
        if options['run_now']:
            self.stdout.write("Running immediate pull...")
            self._run_pull_task()

        # Handle shutdown signals gracefully
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.stdout.write("Scheduler is running. Press Ctrl+C to stop.")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Scheduler stopped.")

    def _run_pull_task(self):
        """Execute the message trace pull task."""
        # Check if pulls are enabled before running
        _, _, enabled = self._get_interval_from_settings()
        if not enabled:
            logger.info("Scheduled pull skipped: pulls are disabled in settings")
            self.stdout.write("Scheduled pull skipped (disabled in settings)")
            return

        hours, minutes, _ = self._get_interval_from_settings()
        self.stdout.write(f"Starting scheduled pull (interval: every {hours}h {minutes}m)")
        logger.info("Starting scheduled message trace pull")

        try:
            result = pull_message_traces(
                triggered_by='scheduler',
                trigger_type='Scheduled'
            )

            if result['status'] == 'Success':
                msg = (
                    f"Scheduled pull completed: "
                    f"{result['records_pulled']} pulled, "
                    f"{result['records_new']} new, "
                    f"{result['records_updated']} updated"
                )
                logger.info(msg)
                self.stdout.write(self.style.SUCCESS(msg))
            else:
                msg = f"Scheduled pull failed: {result['error_message']}"
                logger.error(msg)
                self.stdout.write(self.style.ERROR(msg))

        except Exception as e:
            msg = f"Scheduler error: {str(e)}"
            logger.exception(msg)
            self.stdout.write(self.style.ERROR(msg))

    def _check_settings_change(self):
        """Check if settings have changed and reschedule if needed."""
        hours, minutes, _ = self._get_interval_from_settings()

        job = self.scheduler.get_job('message_trace_pull')
        if job:
            current_trigger = job.trigger
            current_interval = current_trigger.interval
            new_total_seconds = hours * 3600 + minutes * 60

            if current_interval.total_seconds() != new_total_seconds and new_total_seconds > 0:
                self.scheduler.reschedule_job(
                    'message_trace_pull',
                    trigger=IntervalTrigger(hours=hours, minutes=minutes)
                )
                logger.info(f"Rescheduled pulls to every {hours}h {minutes}m")
                self.stdout.write(self.style.SUCCESS(
                    f"Rescheduled pulls to every {hours}h {minutes}m"
                ))

    def _shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.stdout.write("\nShutting down scheduler...")
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        sys.exit(0)
