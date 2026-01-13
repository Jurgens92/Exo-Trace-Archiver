"""
Task functions for pulling message traces from Microsoft 365.

This module contains the core business logic for:
1. Pulling message traces from Exchange Online
2. Storing them in the database
3. Logging pull history

The main function `pull_message_traces` can be called:
- By the scheduled task (daily at 01:00 UTC)
- Manually via the API endpoint
- Via the management command

For production deployments with high volume, consider:
- Using Celery for async task execution
- Implementing proper retry logic
- Adding progress tracking for long-running pulls
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import MessageTraceLog, PullHistory
from .ms365_client import (
    get_ms365_client,
    get_ms365_client_for_tenant,
    normalize_trace_data,
    MS365AuthenticationError,
    MS365APIError,
    MS365GraphAPINotAvailableError,
    TenantPowerShellClient,
)

logger = logging.getLogger('traces')


def pull_message_traces_for_tenant(
    tenant,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    triggered_by: str = 'system',
    trigger_type: str = 'Scheduled'
) -> dict[str, Any]:
    """
    Pull message traces from a specific MS365 tenant and store them in the database.

    This is the multi-tenant version of pull_message_traces().

    Args:
        tenant: Tenant model instance
        start_date: Start of date range (default: yesterday 00:00 UTC)
        end_date: End of date range (default: yesterday 23:59 UTC)
        triggered_by: Username or 'system' for scheduled pulls
        trigger_type: 'Scheduled' or 'Manual'

    Returns:
        Dictionary with pull results
    """
    # Set default date range (yesterday)
    now = timezone.now()
    if start_date is None:
        start_date = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if end_date is None:
        end_date = (now - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

    # Ensure dates are timezone-aware
    if start_date.tzinfo is None:
        start_date = timezone.make_aware(start_date)
    if end_date.tzinfo is None:
        end_date = timezone.make_aware(end_date)

    logger.info(
        f"Starting message trace pull for tenant {tenant.name}: {start_date} to {end_date} "
        f"(triggered by: {triggered_by})"
    )

    # Create pull history record
    pull_history = PullHistory.objects.create(
        tenant=tenant,
        pull_start_date=start_date,
        pull_end_date=end_date,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        api_method=tenant.api_method,
        status=PullHistory.Status.RUNNING
    )

    result = {
        'pull_history_id': pull_history.id,
        'tenant_id': tenant.id,
        'tenant_name': tenant.name,
        'status': 'Running',
        'records_pulled': 0,
        'records_new': 0,
        'records_updated': 0,
        'error_message': ''
    }

    try:
        # Get the MS365 client for this tenant
        client = get_ms365_client_for_tenant(tenant)
        api_method_used = tenant.api_method

        # Authenticate
        logger.info(f"Authenticating with Microsoft 365 for tenant: {tenant.name}")
        client.authenticate()

        # Pull traces (with fallback to PowerShell if Graph API not available)
        logger.info(f"Retrieving message traces for tenant: {tenant.name}")
        try:
            raw_traces = client.get_message_traces(
                start_date=start_date,
                end_date=end_date,
                page_size=settings.MESSAGE_TRACE_PAGE_SIZE
            )
        except MS365GraphAPINotAvailableError as e:
            # Graph API message trace endpoint not available - fall back to PowerShell
            logger.warning(
                f"Graph API not available for tenant {tenant.name}, falling back to PowerShell: {str(e)}"
            )
            # Check if tenant has required config for PowerShell fallback
            if not tenant.organization:
                raise MS365APIError(
                    f"Graph API message trace endpoint not available and PowerShell fallback "
                    f"cannot be used because 'organization' is not configured for tenant: {tenant.name}. "
                    f"Either configure the organization field (e.g., 'contoso.onmicrosoft.com') "
                    f"or add Office 365 Exchange Online API permissions in Azure AD. "
                    f"Original error: {str(e)}"
                )
            # Create PowerShell client and retry
            client = TenantPowerShellClient(tenant)
            client.authenticate()
            raw_traces = client.get_message_traces(
                start_date=start_date,
                end_date=end_date,
                page_size=settings.MESSAGE_TRACE_PAGE_SIZE
            )
            api_method_used = 'powershell'
            # Update pull history to reflect the actual method used
            pull_history.api_method = 'powershell'
            pull_history.save(update_fields=['api_method'])

        result['records_pulled'] = len(raw_traces)
        logger.info(f"Retrieved {len(raw_traces)} traces from tenant: {tenant.name}")

        # Process and store traces
        if raw_traces:
            records_new, records_updated = _store_traces_for_tenant(
                raw_traces,
                tenant=tenant,
                source=api_method_used
            )
            result['records_new'] = records_new
            result['records_updated'] = records_updated

        # Mark as success
        result['status'] = 'Success'
        pull_history.mark_complete(
            status=PullHistory.Status.SUCCESS,
            records_pulled=result['records_pulled'],
            records_new=result['records_new'],
            records_updated=result['records_updated']
        )

        logger.info(
            f"Pull completed for tenant {tenant.name}: {result['records_pulled']} pulled, "
            f"{result['records_new']} new, {result['records_updated']} updated"
        )

    except MS365AuthenticationError as e:
        logger.error(f"Authentication failed for tenant {tenant.name}: {str(e)}")
        result['status'] = 'Failed'
        result['error_message'] = f"Authentication error: {str(e)}"
        pull_history.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message=result['error_message']
        )

    except MS365APIError as e:
        logger.error(f"API error for tenant {tenant.name}: {str(e)}")
        result['status'] = 'Failed'
        result['error_message'] = f"API error: {str(e)}"
        pull_history.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message=result['error_message']
        )

    except Exception as e:
        logger.exception(f"Unexpected error during pull for tenant {tenant.name}: {str(e)}")
        result['status'] = 'Failed'
        result['error_message'] = f"Unexpected error: {str(e)}"
        pull_history.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message=result['error_message']
        )

    return result


def _store_traces_for_tenant(traces: list[dict], tenant, source: str = 'graph') -> tuple[int, int]:
    """
    Store message traces for a specific tenant in the database.

    Args:
        traces: List of raw trace dictionaries from API
        tenant: Tenant model instance
        source: 'graph' or 'powershell' for field mapping

    Returns:
        Tuple of (records_new, records_updated)
    """
    records_new = 0
    records_updated = 0
    trace_date = timezone.now()

    # Get organization domains from tenant for direction detection
    org_domains = tenant.get_organization_domains()

    # Process in batches
    batch_size = 100
    traces_to_create = []
    traces_to_update = []

    for trace in traces:
        normalized = normalize_trace_data(trace, source)

        # Parse received_date
        received_date = normalized['received_date']
        if isinstance(received_date, str):
            received_date = parse_datetime(received_date)
            if received_date is None:
                logger.warning(f"Could not parse date: {normalized['received_date']}")
                continue

        if received_date.tzinfo is None:
            received_date = timezone.make_aware(received_date)

        # Determine direction
        direction = MessageTraceLog.determine_direction(
            sender=normalized['sender'],
            recipient=normalized['recipient'],
            org_domains=org_domains
        )

        # Map status
        status = _normalize_status(normalized['status'])

        # Check if record exists for this tenant
        existing = MessageTraceLog.objects.filter(
            tenant=tenant,
            message_id=normalized['message_id'],
            recipient=normalized['recipient'],
            received_date=received_date
        ).first()

        if existing:
            existing.subject = normalized['subject']
            existing.status = status
            existing.direction = direction
            existing.size = normalized['size']
            existing.event_data = normalized['event_data']
            existing.raw_json = normalized['raw_json']
            existing.trace_date = trace_date
            traces_to_update.append(existing)
        else:
            traces_to_create.append(MessageTraceLog(
                tenant=tenant,
                message_id=normalized['message_id'],
                received_date=received_date,
                sender=normalized['sender'],
                recipient=normalized['recipient'],
                subject=normalized['subject'],
                status=status,
                direction=direction,
                size=normalized['size'],
                event_data=normalized['event_data'],
                raw_json=normalized['raw_json'],
                trace_date=trace_date
            ))

        # Process batches
        if len(traces_to_create) >= batch_size:
            with transaction.atomic():
                MessageTraceLog.objects.bulk_create(
                    traces_to_create,
                    ignore_conflicts=True
                )
            records_new += len(traces_to_create)
            traces_to_create = []

        if len(traces_to_update) >= batch_size:
            with transaction.atomic():
                MessageTraceLog.objects.bulk_update(
                    traces_to_update,
                    fields=['subject', 'status', 'direction', 'size',
                            'event_data', 'raw_json', 'trace_date']
                )
            records_updated += len(traces_to_update)
            traces_to_update = []

    # Process remaining records
    if traces_to_create:
        with transaction.atomic():
            MessageTraceLog.objects.bulk_create(
                traces_to_create,
                ignore_conflicts=True
            )
        records_new += len(traces_to_create)

    if traces_to_update:
        with transaction.atomic():
            MessageTraceLog.objects.bulk_update(
                traces_to_update,
                fields=['subject', 'status', 'direction', 'size',
                        'event_data', 'raw_json', 'trace_date']
            )
        records_updated += len(traces_to_update)

    return records_new, records_updated


def pull_all_tenants(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    triggered_by: str = 'system',
    trigger_type: str = 'Scheduled'
) -> list[dict[str, Any]]:
    """
    Pull message traces from all active tenants.

    Used by the scheduler to pull from all configured tenants.

    Args:
        start_date: Start of date range (default: yesterday 00:00 UTC)
        end_date: End of date range (default: yesterday 23:59 UTC)
        triggered_by: Username or 'system' for scheduled pulls
        trigger_type: 'Scheduled' or 'Manual'

    Returns:
        List of pull results, one per tenant
    """
    from accounts.models import Tenant

    results = []
    active_tenants = Tenant.objects.filter(is_active=True)

    logger.info(f"Starting pull for {active_tenants.count()} active tenant(s)")

    for tenant in active_tenants:
        try:
            result = pull_message_traces_for_tenant(
                tenant=tenant,
                start_date=start_date,
                end_date=end_date,
                triggered_by=triggered_by,
                trigger_type=trigger_type
            )
            results.append(result)
        except Exception as e:
            logger.exception(f"Failed to pull from tenant {tenant.name}: {str(e)}")
            results.append({
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'status': 'Failed',
                'error_message': str(e)
            })

    return results


def pull_message_traces(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    triggered_by: str = 'system',
    trigger_type: str = 'Scheduled'
) -> dict[str, Any]:
    """
    Pull message traces from Microsoft 365 and store them in the database.

    Args:
        start_date: Start of date range (default: yesterday 00:00 UTC)
        end_date: End of date range (default: yesterday 23:59 UTC)
        triggered_by: Username or 'system' for scheduled pulls
        trigger_type: 'Scheduled' or 'Manual'

    Returns:
        Dictionary with pull results:
        {
            'pull_history_id': int,
            'status': str,
            'records_pulled': int,
            'records_new': int,
            'records_updated': int,
            'error_message': str
        }
    """
    # Set default date range (yesterday)
    now = timezone.now()
    if start_date is None:
        start_date = (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if end_date is None:
        end_date = (now - timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

    # Ensure dates are timezone-aware
    if start_date.tzinfo is None:
        start_date = timezone.make_aware(start_date)
    if end_date.tzinfo is None:
        end_date = timezone.make_aware(end_date)

    logger.info(
        f"Starting message trace pull: {start_date} to {end_date} "
        f"(triggered by: {triggered_by})"
    )

    # Create pull history record
    pull_history = PullHistory.objects.create(
        pull_start_date=start_date,
        pull_end_date=end_date,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        api_method=settings.MS365_API_METHOD,
        status=PullHistory.Status.RUNNING
    )

    result = {
        'pull_history_id': pull_history.id,
        'status': 'Running',
        'records_pulled': 0,
        'records_new': 0,
        'records_updated': 0,
        'error_message': ''
    }

    try:
        # Get the appropriate MS365 client
        client = get_ms365_client()

        # Authenticate
        logger.info("Authenticating with Microsoft 365...")
        client.authenticate()

        # Pull traces
        logger.info("Retrieving message traces...")
        raw_traces = client.get_message_traces(
            start_date=start_date,
            end_date=end_date,
            page_size=settings.MESSAGE_TRACE_PAGE_SIZE
        )

        result['records_pulled'] = len(raw_traces)
        logger.info(f"Retrieved {len(raw_traces)} traces from API")

        # Process and store traces
        if raw_traces:
            records_new, records_updated = _store_traces(
                raw_traces,
                source=settings.MS365_API_METHOD
            )
            result['records_new'] = records_new
            result['records_updated'] = records_updated

        # Mark as success
        result['status'] = 'Success'
        pull_history.mark_complete(
            status=PullHistory.Status.SUCCESS,
            records_pulled=result['records_pulled'],
            records_new=result['records_new'],
            records_updated=result['records_updated']
        )

        logger.info(
            f"Pull completed successfully: {result['records_pulled']} pulled, "
            f"{result['records_new']} new, {result['records_updated']} updated"
        )

    except MS365AuthenticationError as e:
        logger.error(f"Authentication failed: {str(e)}")
        result['status'] = 'Failed'
        result['error_message'] = f"Authentication error: {str(e)}"
        pull_history.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message=result['error_message']
        )

    except MS365APIError as e:
        logger.error(f"API error: {str(e)}")
        result['status'] = 'Failed'
        result['error_message'] = f"API error: {str(e)}"
        pull_history.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message=result['error_message']
        )

    except Exception as e:
        logger.exception(f"Unexpected error during pull: {str(e)}")
        result['status'] = 'Failed'
        result['error_message'] = f"Unexpected error: {str(e)}"
        pull_history.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message=result['error_message']
        )

    return result


def _store_traces(traces: list[dict], source: str = 'graph') -> tuple[int, int]:
    """
    Store message traces in the database.

    Uses bulk operations for efficiency and handles duplicates
    using the unique constraint on (message_id, recipient, received_date).

    Args:
        traces: List of raw trace dictionaries from API
        source: 'graph' or 'powershell' for field mapping

    Returns:
        Tuple of (records_new, records_updated)
    """
    records_new = 0
    records_updated = 0
    trace_date = timezone.now()

    # Get organization domains for direction detection
    # This should be configured in settings or pulled from Azure AD
    org_domains = _get_organization_domains()

    # Process in batches for better performance
    batch_size = 100
    traces_to_create = []
    traces_to_update = []

    for trace in traces:
        normalized = normalize_trace_data(trace, source)

        # Parse received_date
        received_date = normalized['received_date']
        if isinstance(received_date, str):
            received_date = parse_datetime(received_date)
            if received_date is None:
                logger.warning(f"Could not parse date: {normalized['received_date']}")
                continue

        if received_date.tzinfo is None:
            received_date = timezone.make_aware(received_date)

        # Determine direction
        direction = MessageTraceLog.determine_direction(
            sender=normalized['sender'],
            recipient=normalized['recipient'],
            org_domains=org_domains
        )

        # Map status to our choices
        status = _normalize_status(normalized['status'])

        # Check if record exists
        existing = MessageTraceLog.objects.filter(
            message_id=normalized['message_id'],
            recipient=normalized['recipient'],
            received_date=received_date
        ).first()

        if existing:
            # Update existing record
            existing.subject = normalized['subject']
            existing.status = status
            existing.direction = direction
            existing.size = normalized['size']
            existing.event_data = normalized['event_data']
            existing.raw_json = normalized['raw_json']
            existing.trace_date = trace_date
            traces_to_update.append(existing)
        else:
            # Create new record
            traces_to_create.append(MessageTraceLog(
                message_id=normalized['message_id'],
                received_date=received_date,
                sender=normalized['sender'],
                recipient=normalized['recipient'],
                subject=normalized['subject'],
                status=status,
                direction=direction,
                size=normalized['size'],
                event_data=normalized['event_data'],
                raw_json=normalized['raw_json'],
                trace_date=trace_date
            ))

        # Process batches
        if len(traces_to_create) >= batch_size:
            with transaction.atomic():
                MessageTraceLog.objects.bulk_create(
                    traces_to_create,
                    ignore_conflicts=True
                )
            records_new += len(traces_to_create)
            traces_to_create = []

        if len(traces_to_update) >= batch_size:
            with transaction.atomic():
                MessageTraceLog.objects.bulk_update(
                    traces_to_update,
                    fields=['subject', 'status', 'direction', 'size',
                            'event_data', 'raw_json', 'trace_date']
                )
            records_updated += len(traces_to_update)
            traces_to_update = []

    # Process remaining records
    if traces_to_create:
        with transaction.atomic():
            MessageTraceLog.objects.bulk_create(
                traces_to_create,
                ignore_conflicts=True
            )
        records_new += len(traces_to_create)

    if traces_to_update:
        with transaction.atomic():
            MessageTraceLog.objects.bulk_update(
                traces_to_update,
                fields=['subject', 'status', 'direction', 'size',
                        'event_data', 'raw_json', 'trace_date']
            )
        records_updated += len(traces_to_update)

    return records_new, records_updated


def _normalize_status(status: str) -> str:
    """Map API status values to our model choices."""
    status_map = {
        'Delivered': MessageTraceLog.Status.DELIVERED,
        'Failed': MessageTraceLog.Status.FAILED,
        'Pending': MessageTraceLog.Status.PENDING,
        'Expanded': MessageTraceLog.Status.EXPANDED,
        'Quarantined': MessageTraceLog.Status.QUARANTINED,
        'FilteredAsSpam': MessageTraceLog.Status.FILTERED,
        'GettingStatus': MessageTraceLog.Status.PENDING,
        'None': MessageTraceLog.Status.NONE,
    }
    return status_map.get(status, MessageTraceLog.Status.UNKNOWN)


def _get_organization_domains() -> list[str]:
    """
    Get the list of organization email domains.

    This is used to determine message direction (Inbound/Outbound/Internal).
    In a production environment, this could be:
    - Pulled from Azure AD
    - Configured in settings
    - Cached and refreshed periodically

    For now, we extract from MS365_ORGANIZATION setting.
    """
    org = settings.MS365_ORGANIZATION
    if org:
        # Extract domain from organization (e.g., 'contoso.onmicrosoft.com')
        domains = [org]
        # Also add the vanity domain if different
        if '.onmicrosoft.com' in org:
            base_domain = org.replace('.onmicrosoft.com', '.com')
            domains.append(base_domain)
        return domains
    return []
