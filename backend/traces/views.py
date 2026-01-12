"""
Django REST Framework views for Message Trace API.

Endpoints:
- GET /api/traces/ - List/search message traces
- GET /api/traces/<id>/ - Get trace detail
- GET /api/pull-history/ - List pull history
- POST /api/manual-pull/ - Trigger manual pull
- GET /api/dashboard/ - Dashboard statistics
- GET /api/config/ - View current configuration (sanitized)
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import UserRateThrottle

from .models import MessageTraceLog, PullHistory
from .serializers import (
    MessageTraceLogSerializer,
    MessageTraceLogDetailSerializer,
    MessageTraceLogListSerializer,
    PullHistorySerializer,
    ManualPullRequestSerializer,
    DashboardStatsSerializer,
)
from .filters import MessageTraceLogFilter, PullHistoryFilter

logger = logging.getLogger('traces')


class ManualPullRateThrottle(UserRateThrottle):
    """Custom throttle for manual pull endpoint to prevent abuse."""
    rate = '10/hour'


class MessageTraceLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing message trace logs.

    list:
        Return a paginated list of message traces with filtering support.

    retrieve:
        Return detailed information about a specific message trace.

    Filters:
        - start_date: Messages received on or after (ISO 8601)
        - end_date: Messages received on or before (ISO 8601)
        - sender: Exact sender email
        - sender_contains: Sender email contains
        - recipient: Exact recipient email
        - recipient_contains: Recipient email contains
        - status: Delivery status (Delivered, Failed, Pending, etc.)
        - direction: Message direction (Inbound, Outbound, Internal)
        - search: General search across sender, recipient, subject

    Ordering:
        Default: -received_date (newest first)
        Options: received_date, sender, recipient, status, size
    """

    queryset = MessageTraceLog.objects.all()
    permission_classes = [IsAuthenticated]
    filterset_class = MessageTraceLogFilter
    search_fields = ['sender', 'recipient', 'subject', 'message_id']
    ordering_fields = ['received_date', 'sender', 'recipient', 'status', 'size', 'trace_date']
    ordering = ['-received_date']

    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return MessageTraceLogListSerializer
        return MessageTraceLogDetailSerializer

    def list(self, request, *args, **kwargs):
        """
        List message traces with filtering and pagination.

        Query parameters are documented in the filter class.
        """
        queryset = self.filter_queryset(self.get_queryset())

        # Log the query for debugging
        logger.debug(f"Traces list query: {request.query_params}")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export filtered traces as CSV.

        Future enhancement: Add more export formats (JSON, Excel).
        """
        # TODO: Implement CSV export
        # This is a placeholder for future implementation
        return Response(
            {'message': 'Export feature coming soon'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class PullHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing pull operation history.

    Shows the history of all scheduled and manual pull operations,
    including success/failure status and record counts.
    """

    queryset = PullHistory.objects.all()
    serializer_class = PullHistorySerializer
    permission_classes = [IsAuthenticated]
    filterset_class = PullHistoryFilter
    ordering_fields = ['start_time', 'records_pulled', 'status']
    ordering = ['-start_time']


class ManualPullView(views.APIView):
    """
    Trigger a manual pull of message traces.

    POST /api/manual-pull/

    Body (optional):
        {
            "start_date": "2024-01-01T00:00:00Z",  // default: yesterday 00:00 UTC
            "end_date": "2024-01-01T23:59:59Z"     // default: yesterday 23:59 UTC
        }

    Note: Exchange Online only retains message traces for 10 days,
    so start_date cannot be more than 10 days ago.

    This endpoint is rate-limited to prevent abuse (10 requests/hour).
    """

    permission_classes = [IsAdminUser]
    throttle_classes = [ManualPullRateThrottle]

    def post(self, request):
        """Trigger a manual pull operation."""
        serializer = ManualPullRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get date range from request or use defaults (yesterday)
        now = timezone.now()
        yesterday = now - timedelta(days=1)

        start_date = serializer.validated_data.get(
            'start_date',
            yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        )
        end_date = serializer.validated_data.get(
            'end_date',
            yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        )

        logger.info(
            f"Manual pull triggered by {request.user.username} "
            f"for date range {start_date} to {end_date}"
        )

        # Import here to avoid circular imports
        from .tasks import pull_message_traces

        try:
            # Run the pull task
            # In production with Celery, this would be: pull_message_traces.delay(...)
            result = pull_message_traces(
                start_date=start_date,
                end_date=end_date,
                triggered_by=request.user.username,
                trigger_type='Manual'
            )

            return Response({
                'message': 'Pull operation completed',
                'pull_history_id': result.get('pull_history_id'),
                'records_pulled': result.get('records_pulled', 0),
                'records_new': result.get('records_new', 0),
                'status': result.get('status', 'Unknown')
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Manual pull failed: {str(e)}", exc_info=True)
            return Response({
                'error': 'Pull operation failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DashboardView(views.APIView):
    """
    Get dashboard statistics and summary data.

    GET /api/dashboard/

    Returns:
        - Total trace count
        - Traces today/this week
        - Status breakdown
        - Direction breakdown
        - Last pull information
        - Recent pull history
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return dashboard statistics."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Get counts
        total_traces = MessageTraceLog.objects.count()
        traces_today = MessageTraceLog.objects.filter(
            received_date__gte=today_start
        ).count()
        traces_this_week = MessageTraceLog.objects.filter(
            received_date__gte=week_start
        ).count()

        # Status breakdown
        status_counts = MessageTraceLog.objects.values('status').annotate(
            count=Count('id')
        )
        status_dict = {item['status']: item['count'] for item in status_counts}

        # Direction breakdown
        direction_counts = MessageTraceLog.objects.values('direction').annotate(
            count=Count('id')
        )
        direction_dict = {item['direction']: item['count'] for item in direction_counts}

        # Last pull and recent pulls
        last_pull = PullHistory.objects.filter(
            status__in=['Success', 'Partial']
        ).first()
        recent_pulls = PullHistory.objects.all()[:5]

        data = {
            'total_traces': total_traces,
            'traces_today': traces_today,
            'traces_this_week': traces_this_week,
            'last_pull': last_pull,
            'delivered_count': status_dict.get('Delivered', 0),
            'failed_count': status_dict.get('Failed', 0),
            'pending_count': status_dict.get('Pending', 0),
            'quarantined_count': status_dict.get('Quarantined', 0),
            'inbound_count': direction_dict.get('Inbound', 0),
            'outbound_count': direction_dict.get('Outbound', 0),
            'internal_count': direction_dict.get('Internal', 0),
            'recent_pulls': recent_pulls,
        }

        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)


class ConfigView(views.APIView):
    """
    View current configuration (sanitized - no secrets).

    GET /api/config/

    Returns sanitized configuration information for display
    in the settings page. Secrets are masked.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        """Return sanitized configuration."""
        # Mask sensitive values
        def mask_secret(value: str) -> str:
            if not value:
                return '(not set)'
            if len(value) <= 8:
                return '*' * len(value)
            return value[:4] + '*' * (len(value) - 8) + value[-4:]

        config = {
            'microsoft365': {
                'tenant_id': mask_secret(settings.MS365_TENANT_ID),
                'client_id': mask_secret(settings.MS365_CLIENT_ID),
                'auth_method': settings.MS365_AUTH_METHOD,
                'api_method': settings.MS365_API_METHOD,
                'organization': settings.MS365_ORGANIZATION or '(not set)',
                'certificate_configured': bool(settings.MS365_CERTIFICATE_PATH),
                'client_secret_configured': bool(settings.MS365_CLIENT_SECRET),
            },
            'message_trace': {
                'lookback_days': settings.MESSAGE_TRACE_LOOKBACK_DAYS,
                'page_size': settings.MESSAGE_TRACE_PAGE_SIZE,
            },
            'scheduler': {
                'daily_pull_hour': settings.DAILY_PULL_HOUR,
                'daily_pull_minute': settings.DAILY_PULL_MINUTE,
            },
            'database': {
                'engine': settings.DATABASES['default']['ENGINE'].split('.')[-1],
            },
            'debug_mode': settings.DEBUG,
        }

        return Response(config)
