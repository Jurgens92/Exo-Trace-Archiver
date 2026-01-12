"""
Management command to pull message traces from Microsoft 365.

Usage:
    # Pull yesterday's traces (default)
    python manage.py pull_traces

    # Pull traces for a specific date range
    python manage.py pull_traces --start-date 2024-01-01 --end-date 2024-01-02

    # Pull traces for the last N days
    python manage.py pull_traces --days 7

This command can be run:
- Manually for on-demand pulls
- Via cron for scheduled daily pulls
- Via the scheduler command for in-process scheduling

Example cron entry for daily pull at 01:00 UTC:
    0 1 * * * cd /path/to/backend && /path/to/venv/bin/python manage.py pull_traces
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from traces.tasks import pull_message_traces


class Command(BaseCommand):
    help = 'Pull message traces from Microsoft 365 Exchange Online'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date (YYYY-MM-DD format). Default: yesterday'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date (YYYY-MM-DD format). Default: yesterday'
        )
        parser.add_argument(
            '--days',
            type=int,
            help='Pull traces for the last N days (alternative to date range)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be pulled without actually pulling'
        )

    def handle(self, *args, **options):
        start_date = None
        end_date = None

        # Parse date range options
        if options['days']:
            # Pull last N days
            now = timezone.now()
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_date = (now - timedelta(days=options['days'])).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif options['start_date'] or options['end_date']:
            # Parse explicit dates
            if options['start_date']:
                try:
                    start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
                    start_date = timezone.make_aware(start_date)
                except ValueError:
                    raise CommandError(
                        f"Invalid start-date format: {options['start_date']}. "
                        "Use YYYY-MM-DD."
                    )

            if options['end_date']:
                try:
                    end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
                    end_date = timezone.make_aware(end_date.replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    ))
                except ValueError:
                    raise CommandError(
                        f"Invalid end-date format: {options['end_date']}. "
                        "Use YYYY-MM-DD."
                    )

        # Set defaults if not specified
        if start_date is None:
            now = timezone.now()
            start_date = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        if end_date is None:
            now = timezone.now()
            end_date = (now - timedelta(days=1)).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

        # Validate date range
        if start_date >= end_date:
            raise CommandError("start-date must be before end-date")

        # Check Exchange Online 10-day limit
        min_date = timezone.now() - timedelta(days=10)
        if start_date < min_date:
            self.stdout.write(self.style.WARNING(
                f"Warning: Exchange Online only retains traces for 10 days. "
                f"Start date {start_date.date()} may return no results."
            ))

        self.stdout.write(
            f"Pulling message traces from {start_date.date()} to {end_date.date()}"
        )

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                "DRY RUN - No data will be pulled"
            ))
            return

        # Execute the pull
        try:
            result = pull_message_traces(
                start_date=start_date,
                end_date=end_date,
                triggered_by='management_command',
                trigger_type='Manual'
            )

            if result['status'] == 'Success':
                self.stdout.write(self.style.SUCCESS(
                    f"Pull completed successfully!\n"
                    f"  Records pulled: {result['records_pulled']}\n"
                    f"  New records: {result['records_new']}\n"
                    f"  Updated records: {result['records_updated']}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"Pull failed: {result['error_message']}"
                ))
                raise CommandError(result['error_message'])

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            raise CommandError(str(e))
