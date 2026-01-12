"""
Management command to run the scheduled task scheduler.

This command starts an in-process scheduler that runs the message trace
pull task daily at 01:00 UTC (configurable via DAILY_PULL_HOUR/MINUTE).

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
from django.conf import settings

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from traces.tasks import pull_message_traces

logger = logging.getLogger('traces')


class Command(BaseCommand):
    help = 'Run the scheduled task scheduler for daily message trace pulls'

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
        self.stdout.write("Starting Exo-Trace-Archiver scheduler...")

        # Create scheduler
        self.scheduler = BlockingScheduler(timezone='UTC')

        # Schedule the daily pull task
        hour = settings.DAILY_PULL_HOUR
        minute = settings.DAILY_PULL_MINUTE

        self.scheduler.add_job(
            self._run_pull_task,
            trigger=CronTrigger(hour=hour, minute=minute),
            id='daily_message_trace_pull',
            name='Daily Message Trace Pull',
            replace_existing=True
        )

        self.stdout.write(self.style.SUCCESS(
            f"Scheduled daily pull at {hour:02d}:{minute:02d} UTC"
        ))

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
        self.stdout.write(f"Starting scheduled pull at {settings.DAILY_PULL_HOUR}:{settings.DAILY_PULL_MINUTE} UTC")
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

    def _shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.stdout.write("\nShutting down scheduler...")
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
        sys.exit(0)
