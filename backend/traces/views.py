"""
Django REST Framework views for Message Trace API.

Endpoints:
- GET /api/traces/ - List/search message traces
- GET /api/traces/<id>/ - Get trace detail
- GET /api/pull-history/ - List pull history
- POST /api/manual-pull/ - Trigger manual pull
- GET /api/dashboard/ - Dashboard statistics
- GET /api/config/ - View current configuration (sanitized)

Multi-tenant: All views filter data by tenant permissions.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle

from .pdf_generator import pdf_generator

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
from accounts.permissions import IsAdminRole, get_accessible_tenant_ids, user_is_admin
from accounts.models import Tenant

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
        - tenant: Filter by tenant ID (admin can see all, users see assigned)
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

    permission_classes = [IsAuthenticated]
    filterset_class = MessageTraceLogFilter
    search_fields = ['sender', 'recipient', 'subject', 'message_id']
    ordering_fields = ['received_date', 'sender', 'recipient', 'status', 'size', 'trace_date']
    ordering = ['-received_date']

    def get_queryset(self):
        """Filter queryset by accessible tenants."""
        tenant_ids = get_accessible_tenant_ids(self.request.user)

        # If user has no accessible tenants, return empty queryset
        if not tenant_ids:
            return MessageTraceLog.objects.none()

        queryset = MessageTraceLog.objects.filter(tenant_id__in=tenant_ids)

        # Allow filtering by specific tenant if provided
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id:
            try:
                tenant_id = int(tenant_id)
                if tenant_id in tenant_ids:
                    queryset = queryset.filter(tenant_id=tenant_id)
                else:
                    # User doesn't have access to this tenant
                    return MessageTraceLog.objects.none()
            except ValueError:
                pass

        return queryset

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

    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None):
        """
        Export a single message trace as PDF.

        GET /api/traces/{id}/export-pdf/

        Returns a downloadable PDF file with detailed trace information.
        """
        try:
            trace = self.get_object()
        except Exception:
            return Response(
                {'error': 'Trace not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get tenant name for multi-tenant context
        tenant_name = trace.tenant.name if trace.tenant else None

        # Generate PDF
        try:
            pdf_bytes = pdf_generator.generate_trace_detail_pdf(trace, tenant_name)
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate PDF', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create filename
        date_str = trace.received_date.strftime('%Y%m%d') if trace.received_date else 'unknown'
        filename = f"trace_detail_{trace.id}_{date_str}.pdf"

        # Return PDF response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'], url_path='export-search-pdf')
    def export_search_pdf(self, request):
        """
        Export search results as PDF.

        GET /api/traces/export-search-pdf/?search=...&status=...&direction=...

        Accepts all the same filter parameters as the list endpoint.
        Returns a downloadable PDF file with the filtered trace results.

        Note: Limited to first 500 results to keep PDF size reasonable.
        """
        # Get filtered queryset (same as list view)
        queryset = self.filter_queryset(self.get_queryset())

        # Limit to 500 results for PDF
        max_results = 500
        total_count = queryset.count()
        traces = list(queryset[:max_results])

        # Build filters dict from request params for display in PDF
        filters = {}
        filter_keys = ['search', 'status', 'direction', 'start_date', 'end_date',
                       'sender', 'recipient', 'sender_domain', 'recipient_domain']
        for key in filter_keys:
            value = request.query_params.get(key)
            if value:
                filters[key] = value

        # Get tenant name if filtering by specific tenant
        tenant_name = None
        tenant_id = request.query_params.get('tenant')
        if tenant_id:
            try:
                from accounts.models import Tenant
                tenant = Tenant.objects.get(id=int(tenant_id))
                tenant_name = tenant.name
            except (ValueError, Tenant.DoesNotExist):
                pass

        # Generate PDF
        try:
            pdf_bytes = pdf_generator.generate_search_results_pdf(
                traces=traces,
                filters=filters,
                tenant_name=tenant_name,
                total_count=total_count
            )
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Failed to generate PDF', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Create filename
        date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"trace_search_results_{date_str}.pdf"

        # Return PDF response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class PullHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing pull operation history.

    Shows the history of all scheduled and manual pull operations,
    including success/failure status and record counts.

    Multi-tenant: Users can only see pull history for tenants they have access to.
    """

    serializer_class = PullHistorySerializer
    permission_classes = [IsAuthenticated]
    filterset_class = PullHistoryFilter
    ordering_fields = ['start_time', 'records_pulled', 'status']
    ordering = ['-start_time']

    def get_queryset(self):
        """Filter queryset by accessible tenants."""
        tenant_ids = get_accessible_tenant_ids(self.request.user)

        if not tenant_ids:
            return PullHistory.objects.none()

        queryset = PullHistory.objects.filter(tenant_id__in=tenant_ids)

        # Allow filtering by specific tenant if provided
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id:
            try:
                tenant_id = int(tenant_id)
                if tenant_id in tenant_ids:
                    queryset = queryset.filter(tenant_id=tenant_id)
                else:
                    return PullHistory.objects.none()
            except ValueError:
                pass

        return queryset


class ManualPullView(views.APIView):
    """
    Trigger a manual pull of message traces.

    POST /api/manual-pull/

    Body:
        {
            "tenant_id": 1,                            // required: which tenant to pull from
            "start_date": "2024-01-01T00:00:00Z",      // default: yesterday 00:00 UTC
            "end_date": "2024-01-01T23:59:59Z"         // default: current time (up to today)
        }

    Note: Exchange Online only retains message traces for 10 days,
    so start_date cannot be more than 10 days ago.

    This endpoint is rate-limited to prevent abuse (10 requests/hour).
    Admin users can pull from any tenant.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    throttle_classes = [ManualPullRateThrottle]

    def post(self, request):
        """Trigger a manual pull operation."""
        serializer = ManualPullRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get tenant_id from request
        tenant_id = request.data.get('tenant_id')
        if not tenant_id:
            return Response(
                {'error': 'tenant_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate tenant exists and user has access
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Admin users can access any tenant
        if not user_is_admin(request.user):
            accessible_ids = get_accessible_tenant_ids(request.user)
            if tenant.id not in accessible_ids:
                return Response(
                    {'error': 'You do not have access to this tenant'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Get date range from request or use defaults
        # Default: yesterday 00:00 to now (allows pulling up to today)
        now = timezone.now()
        yesterday = now - timedelta(days=1)

        start_date = serializer.validated_data.get(
            'start_date',
            yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        )
        end_date = serializer.validated_data.get(
            'end_date',
            now  # Default to current time instead of yesterday, allows pulling up to today
        )

        logger.info(
            f"Manual pull triggered by {request.user.username} "
            f"for tenant {tenant.name} ({tenant.id}) "
            f"for date range {start_date} to {end_date}"
        )

        # Import here to avoid circular imports
        from .tasks import pull_message_traces_for_tenant

        try:
            # Run the pull task for the specific tenant
            result = pull_message_traces_for_tenant(
                tenant=tenant,
                start_date=start_date,
                end_date=end_date,
                triggered_by=request.user.username,
                trigger_type='Manual'
            )

            return Response({
                'message': 'Pull operation completed',
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
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
    GET /api/dashboard/?tenant=<id>  - Filter by specific tenant

    Returns:
        - Total trace count
        - Traces today/this week
        - Status breakdown
        - Direction breakdown
        - Last pull information
        - Recent pull history

    Multi-tenant: Shows aggregate data across all accessible tenants,
    or filtered by a specific tenant if tenant query param is provided.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return dashboard statistics."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Get accessible tenant IDs
        tenant_ids = get_accessible_tenant_ids(request.user)

        # Optional: filter by specific tenant
        specific_tenant = request.query_params.get('tenant')
        if specific_tenant:
            try:
                specific_tenant = int(specific_tenant)
                if specific_tenant in tenant_ids:
                    tenant_ids = [specific_tenant]
                else:
                    tenant_ids = []
            except ValueError:
                pass

        # Base querysets filtered by tenant
        traces_qs = MessageTraceLog.objects.filter(tenant_id__in=tenant_ids)
        pulls_qs = PullHistory.objects.filter(tenant_id__in=tenant_ids)

        # Get counts
        total_traces = traces_qs.count()
        traces_today = traces_qs.filter(
            received_date__gte=today_start
        ).count()
        traces_this_week = traces_qs.filter(
            received_date__gte=week_start
        ).count()

        # Status breakdown
        status_counts = traces_qs.values('status').annotate(
            count=Count('id')
        )
        status_dict = {item['status']: item['count'] for item in status_counts}

        # Direction breakdown
        direction_counts = traces_qs.values('direction').annotate(
            count=Count('id')
        )
        direction_dict = {item['direction']: item['count'] for item in direction_counts}

        # Last pull and recent pulls
        last_pull = pulls_qs.filter(
            status__in=['Success', 'Partial']
        ).first()
        recent_pulls = pulls_qs.all()[:5]

        # Get tenant info for response
        accessible_tenants = Tenant.objects.filter(id__in=tenant_ids).values('id', 'name')

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
            'tenant_count': len(tenant_ids),
            'accessible_tenants': list(accessible_tenants),
        }

        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)


class ConfigView(views.APIView):
    """
    View current configuration (sanitized - no secrets).

    GET /api/config/

    Returns sanitized configuration information for display
    in the settings page. Secrets are masked.

    Admin-only: Only admin users can view configuration.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Return sanitized configuration."""
        # Mask sensitive values
        def mask_secret(value: str) -> str:
            if not value:
                return '(not set)'
            if len(value) <= 8:
                return '*' * len(value)
            return value[:4] + '*' * (len(value) - 8) + value[-4:]

        # Get tenant count and list
        tenants = Tenant.objects.all()
        tenant_list = [
            {
                'id': t.id,
                'name': t.name,
                'is_active': t.is_active,
                'organization': t.organization,
            }
            for t in tenants
        ]

        config = {
            'multi_tenant': {
                'enabled': True,
                'tenant_count': tenants.count(),
                'tenants': tenant_list,
            },
            'legacy_microsoft365': {
                'tenant_id': mask_secret(getattr(settings, 'MS365_TENANT_ID', '')),
                'client_id': mask_secret(getattr(settings, 'MS365_CLIENT_ID', '')),
                'auth_method': getattr(settings, 'MS365_AUTH_METHOD', 'certificate'),
                'api_method': getattr(settings, 'MS365_API_METHOD', 'graph'),
                'organization': getattr(settings, 'MS365_ORGANIZATION', '') or '(not set)',
                'certificate_configured': bool(getattr(settings, 'MS365_CERTIFICATE_PATH', '')),
                'client_secret_configured': bool(getattr(settings, 'MS365_CLIENT_SECRET', '')),
            },
            'message_trace': {
                'lookback_days': getattr(settings, 'MESSAGE_TRACE_LOOKBACK_DAYS', 1),
                'page_size': getattr(settings, 'MESSAGE_TRACE_PAGE_SIZE', 1000),
            },
            'scheduler': {
                'daily_pull_hour': getattr(settings, 'DAILY_PULL_HOUR', 1),
                'daily_pull_minute': getattr(settings, 'DAILY_PULL_MINUTE', 0),
            },
            'database': {
                'engine': settings.DATABASES['default']['ENGINE'].split('.')[-1],
            },
            'debug_mode': settings.DEBUG,
        }

        return Response(config)


class DiscoverDomainsView(views.APIView):
    """
    Auto-discover organization domains from Microsoft 365.

    POST /api/discover-domains/

    Body:
        {
            "tenant_id": 1,           // required: which tenant to discover domains for
            "overwrite": false        // optional: overwrite existing domains (default: false)
        }

    This endpoint uses the Microsoft Graph API to fetch all verified domains
    for a tenant and automatically updates the tenant's 'domains' field.

    Required: Domain.Read.All permission in Azure AD (optional permission)

    Admin-only: Only admin users can discover domains.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        """Trigger domain discovery for a tenant."""
        tenant_id = request.data.get('tenant_id')
        overwrite = request.data.get('overwrite', False)

        if not tenant_id:
            return Response(
                {'error': 'tenant_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate tenant exists
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if domains already configured
        current_domains = tenant.get_organization_domains()
        if current_domains and not overwrite:
            return Response(
                {
                    'error': 'Tenant already has domains configured',
                    'current_domains': current_domains,
                    'message': 'Set overwrite=true to update existing domains'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(
            f"Domain discovery triggered by {request.user.username} "
            f"for tenant {tenant.name} (ID: {tenant.id})"
        )

        # Import here to avoid circular imports
        from .ms365_client import (
            get_ms365_client_for_tenant,
            MS365AuthenticationError,
            MS365APIError,
        )

        try:
            # Get client for this tenant
            client = get_ms365_client_for_tenant(tenant)

            # Check if client supports domain discovery (Graph API only)
            if not hasattr(client, 'get_verified_domains'):
                return Response(
                    {
                        'error': 'Domain discovery not supported',
                        'message': 'Only Microsoft Graph API supports automatic domain discovery. '
                                   'This tenant is configured to use PowerShell.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Authenticate
            client.authenticate()

            # Fetch domains
            discovered_domains = client.get_verified_domains()

            if not discovered_domains:
                return Response(
                    {
                        'error': 'No verified domains found',
                        'message': 'No verified domains were found for this tenant'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # Update tenant
            old_domains = tenant.domains
            tenant.domains = ','.join(discovered_domains)
            tenant.domains_last_updated = timezone.now()
            tenant.save()

            logger.info(
                f"Domains updated for tenant {tenant.name}: {tenant.domains}"
            )

            return Response({
                'message': 'Domains discovered and updated successfully',
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'old_domains': old_domains.split(',') if old_domains else [],
                'new_domains': discovered_domains,
                'next_steps': {
                    'message': 'Run fix_directions to update existing traces',
                    'command': f'python manage.py fix_directions --fix --tenant-id {tenant.id}'
                }
            }, status=status.HTTP_200_OK)

        except MS365AuthenticationError as e:
            logger.error(f"Authentication failed for domain discovery: {str(e)}")
            return Response({
                'error': 'Authentication failed',
                'detail': str(e),
                'troubleshooting': [
                    'Verify tenant credentials (Client ID, Tenant ID)',
                    'Check certificate/secret configuration',
                    'Ensure Azure AD app has correct permissions'
                ]
            }, status=status.HTTP_401_UNAUTHORIZED)

        except MS365APIError as e:
            logger.error(f"API error during domain discovery: {str(e)}")
            error_msg = str(e)

            # Check if it's a permissions error
            if 'Domain.Read.All' in error_msg or 'Insufficient permissions' in error_msg:
                return Response({
                    'error': 'Missing permissions',
                    'detail': 'Domain.Read.All permission required',
                    'instructions': [
                        'Go to Azure Portal > App Registrations',
                        f'Select your app (Client ID: {tenant.client_id})',
                        'Go to API Permissions',
                        'Add "Domain.Read.All" (Application permission)',
                        'Grant admin consent',
                    ],
                    'note': 'This permission is optional. You can manually configure domains if preferred.'
                }, status=status.HTTP_403_FORBIDDEN)

            return Response({
                'error': 'API error',
                'detail': error_msg
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(f"Unexpected error during domain discovery: {str(e)}")
            return Response({
                'error': 'Unexpected error',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
