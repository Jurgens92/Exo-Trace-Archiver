"""
Background scheduler for automated message trace pulls.

This module provides a BackgroundScheduler that runs alongside the Django
server. It reads configuration from the database (AppSettings) and
dynamically reschedules when settings change.

The scheduler is started automatically when the Django app starts via
AppConfig.ready(). It can also be run standalone via the run_scheduler
management command.
"""

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger('traces')

# Module-level scheduler instance (singleton)
_scheduler = None


def get_interval_from_settings():
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


def _run_pull_task():
    """Execute the message trace pull task."""
    from .tasks import pull_all_tenants

    _, _, enabled = get_interval_from_settings()
    if not enabled:
        logger.info("Scheduled pull skipped: pulls are disabled in settings")
        return

    hours, minutes, _ = get_interval_from_settings()
    logger.info(f"Starting scheduled pull (interval: every {hours}h {minutes}m)")

    try:
        results = pull_all_tenants(
            triggered_by='scheduler',
            trigger_type='Scheduled'
        )

        total_pulled = sum(r.get('records_pulled', 0) for r in results)
        total_new = sum(r.get('records_new', 0) for r in results)
        total_updated = sum(r.get('records_updated', 0) for r in results)
        failed = [r for r in results if r.get('status') == 'Failed']

        if not failed:
            logger.info(
                f"Scheduled pull completed for {len(results)} tenant(s): "
                f"{total_pulled} pulled, {total_new} new, {total_updated} updated"
            )
        else:
            msg = (
                f"Scheduled pull completed with {len(failed)} failure(s) "
                f"out of {len(results)} tenant(s): "
                f"{total_pulled} pulled, {total_new} new"
            )
            for f_result in failed:
                msg += f"\n  - {f_result.get('tenant_name', 'Unknown')}: {f_result.get('error_message', 'Unknown error')}"
            logger.warning(msg)

    except Exception as e:
        logger.exception(f"Scheduler error: {str(e)}")


def _check_settings_change():
    """Check if settings have changed and reschedule if needed."""
    global _scheduler
    if not _scheduler:
        return

    hours, minutes, _ = get_interval_from_settings()

    job = _scheduler.get_job('message_trace_pull')
    if job:
        current_interval = job.trigger.interval
        new_total_seconds = hours * 3600 + minutes * 60

        if current_interval.total_seconds() != new_total_seconds and new_total_seconds > 0:
            _scheduler.reschedule_job(
                'message_trace_pull',
                trigger=IntervalTrigger(hours=hours, minutes=minutes)
            )
            logger.info(f"Rescheduled pulls to every {hours}h {minutes}m")


def start_scheduler():
    """
    Start the background scheduler.

    This is called from AppConfig.ready() when the Django server starts.
    The scheduler runs in a background daemon thread and stops automatically
    when the main process exits.
    """
    global _scheduler

    # Don't start if already running
    if _scheduler and _scheduler.running:
        return

    # In development, Django's auto-reloader runs ready() twice - once in
    # the main process and once in the reloader. We only want the scheduler
    # in the reloader process (where RUN_MAIN=true). In production (no
    # reloader), RUN_MAIN won't be set, so we always start.
    is_dev_server = 'RUN_MAIN' in os.environ or os.environ.get('DJANGO_DEV_SERVER')
    is_reloader_process = os.environ.get('RUN_MAIN') == 'true'

    if is_dev_server and not is_reloader_process:
        # This is the outer/watcher process in dev - skip
        return

    hours, minutes, enabled = get_interval_from_settings()

    _scheduler = BackgroundScheduler(timezone='UTC')

    # Schedule the pull task
    _scheduler.add_job(
        _run_pull_task,
        trigger=IntervalTrigger(hours=hours, minutes=minutes),
        id='message_trace_pull',
        name='Message Trace Pull',
        replace_existing=True
    )

    # Check for settings changes every 5 minutes
    _scheduler.add_job(
        _check_settings_change,
        trigger=IntervalTrigger(minutes=5),
        id='settings_check',
        name='Settings Change Check',
        replace_existing=True
    )

    _scheduler.start()

    if enabled:
        logger.info(f"Scheduler started: pulling every {hours}h {minutes}m")
    else:
        logger.info(f"Scheduler started (pulls disabled, interval: {hours}h {minutes}m)")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
        _scheduler = None
