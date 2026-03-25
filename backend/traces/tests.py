"""
Comprehensive tests for the traces app.

Tests cover:
- Models: MessageTraceLog, PullHistory
- Serializers: Trace serializers, PullHistory, ManualPullRequest, Dashboard
- Views: Traces list/detail, PullHistory, ManualPull, Dashboard, Config
- Filters: MessageTraceLogFilter, PullHistoryFilter
- Tasks: _normalize_status, pull logic helpers
- Scheduler: run_scheduler command
"""

from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status as http_status
from rest_framework.authtoken.models import Token

from accounts.models import UserProfile, Tenant, TenantPermission, AppSettings
from .models import MessageTraceLog, PullHistory
from .serializers import (
    MessageTraceLogSerializer,
    MessageTraceLogListSerializer,
    MessageTraceLogDetailSerializer,
    PullHistorySerializer,
    ManualPullRequestSerializer,
    DashboardStatsSerializer,
)
from .filters import MessageTraceLogFilter, PullHistoryFilter
from .tasks import _normalize_status


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class MessageTraceLogModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
            domains='contoso.com,contoso.onmicrosoft.com',
        )

    def _create_trace(self, **kwargs):
        defaults = {
            'tenant': self.tenant,
            'message_id': '<test@contoso.com>',
            'received_date': timezone.now(),
            'sender': 'user@contoso.com',
            'recipient': 'external@gmail.com',
            'subject': 'Test Email',
            'status': MessageTraceLog.Status.DELIVERED,
            'direction': MessageTraceLog.Direction.OUTBOUND,
            'size': 1024,
        }
        defaults.update(kwargs)
        return MessageTraceLog.objects.create(**defaults)

    def test_create_trace(self):
        trace = self._create_trace()
        self.assertEqual(trace.sender, 'user@contoso.com')
        self.assertEqual(trace.status, 'Delivered')

    def test_str_representation(self):
        trace = self._create_trace()
        result = str(trace)
        self.assertIn('user@contoso.com', result)
        self.assertIn('external@gmail.com', result)
        self.assertIn('Delivered', result)

    def test_determine_direction_outbound(self):
        direction = MessageTraceLog.determine_direction(
            sender='user@contoso.com',
            recipient='external@gmail.com',
            org_domains=['contoso.com'],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.OUTBOUND)

    def test_determine_direction_inbound(self):
        direction = MessageTraceLog.determine_direction(
            sender='external@gmail.com',
            recipient='user@contoso.com',
            org_domains=['contoso.com'],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.INBOUND)

    def test_determine_direction_internal(self):
        direction = MessageTraceLog.determine_direction(
            sender='user1@contoso.com',
            recipient='user2@contoso.com',
            org_domains=['contoso.com'],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.INTERNAL)

    def test_determine_direction_unknown(self):
        direction = MessageTraceLog.determine_direction(
            sender='user@external1.com',
            recipient='user@external2.com',
            org_domains=['contoso.com'],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.UNKNOWN)

    def test_determine_direction_case_insensitive(self):
        direction = MessageTraceLog.determine_direction(
            sender='USER@CONTOSO.COM',
            recipient='external@gmail.com',
            org_domains=['contoso.com'],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.OUTBOUND)

    def test_determine_direction_empty_domains(self):
        direction = MessageTraceLog.determine_direction(
            sender='user@contoso.com',
            recipient='external@gmail.com',
            org_domains=[],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.UNKNOWN)

    def test_determine_direction_no_at_sign(self):
        direction = MessageTraceLog.determine_direction(
            sender='noemail',
            recipient='user@contoso.com',
            org_domains=['contoso.com'],
        )
        self.assertEqual(direction, MessageTraceLog.Direction.INBOUND)

    def test_unique_constraint(self):
        now = timezone.now()
        self._create_trace(
            message_id='<unique@test.com>',
            received_date=now,
            recipient='a@gmail.com',
        )
        with self.assertRaises(Exception):
            self._create_trace(
                message_id='<unique@test.com>',
                received_date=now,
                recipient='a@gmail.com',
            )

    def test_ordering(self):
        now = timezone.now()
        t1 = self._create_trace(
            message_id='<1@test.com>',
            received_date=now - timedelta(hours=2),
            recipient='a@gmail.com',
        )
        t2 = self._create_trace(
            message_id='<2@test.com>',
            received_date=now,
            recipient='b@gmail.com',
        )
        traces = list(MessageTraceLog.objects.all())
        self.assertEqual(traces[0].id, t2.id)  # Newest first


class PullHistoryModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )

    def _create_pull(self, **kwargs):
        now = timezone.now()
        defaults = {
            'tenant': self.tenant,
            'pull_start_date': now - timedelta(days=1),
            'pull_end_date': now,
            'status': PullHistory.Status.SUCCESS,
            'trigger_type': PullHistory.TriggerType.SCHEDULED,
            'triggered_by': 'scheduler',
            'records_pulled': 100,
            'records_new': 90,
            'records_updated': 10,
        }
        defaults.update(kwargs)
        return PullHistory.objects.create(**defaults)

    def test_create_pull_history(self):
        pull = self._create_pull()
        self.assertEqual(pull.records_pulled, 100)
        self.assertEqual(pull.status, 'Success')

    def test_str_representation(self):
        pull = self._create_pull()
        result = str(pull)
        self.assertIn('Success', result)
        self.assertIn('100', result)

    def test_duration_seconds(self):
        now = timezone.now()
        pull = self._create_pull(
            start_time=now - timedelta(seconds=120),
        )
        pull.end_time = now
        pull.save()
        self.assertAlmostEqual(pull.duration_seconds, 120, places=0)

    def test_duration_seconds_no_end_time(self):
        pull = self._create_pull()
        pull.end_time = None
        pull.save()
        self.assertIsNone(pull.duration_seconds)

    def test_mark_complete(self):
        pull = self._create_pull(status=PullHistory.Status.RUNNING)
        pull.mark_complete(
            status=PullHistory.Status.SUCCESS,
            records_pulled=50,
            records_new=40,
            records_updated=10,
        )
        pull.refresh_from_db()
        self.assertEqual(pull.status, 'Success')
        self.assertEqual(pull.records_pulled, 50)
        self.assertIsNotNone(pull.end_time)

    def test_mark_complete_failed(self):
        pull = self._create_pull(status=PullHistory.Status.RUNNING)
        pull.mark_complete(
            status=PullHistory.Status.FAILED,
            error_message='Connection timeout',
        )
        pull.refresh_from_db()
        self.assertEqual(pull.status, 'Failed')
        self.assertEqual(pull.error_message, 'Connection timeout')

    def test_ordering(self):
        now = timezone.now()
        p1 = self._create_pull(start_time=now - timedelta(hours=2))
        p2 = self._create_pull(start_time=now)
        pulls = list(PullHistory.objects.all())
        self.assertEqual(pulls[0].id, p2.id)  # Newest first


# ---------------------------------------------------------------------------
# Serializer Tests
# ---------------------------------------------------------------------------

class MessageTraceLogSerializerTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )
        self.trace = MessageTraceLog.objects.create(
            tenant=self.tenant,
            message_id='<test@contoso.com>',
            received_date=timezone.now() - timedelta(hours=2),
            sender='user@contoso.com',
            recipient='external@gmail.com',
            subject='Test Email',
            status=MessageTraceLog.Status.DELIVERED,
            direction=MessageTraceLog.Direction.OUTBOUND,
            size=2048,
        )

    def test_serialization(self):
        serializer = MessageTraceLogSerializer(self.trace)
        data = serializer.data
        self.assertEqual(data['sender'], 'user@contoso.com')
        self.assertEqual(data['status'], 'Delivered')
        self.assertIn('size_formatted', data)
        self.assertIn('duration_since_received', data)

    def test_size_formatted_bytes(self):
        self.trace.size = 500
        self.trace.save()
        serializer = MessageTraceLogSerializer(self.trace)
        self.assertIn('B', serializer.data['size_formatted'])

    def test_size_formatted_kb(self):
        self.trace.size = 2048
        self.trace.save()
        serializer = MessageTraceLogSerializer(self.trace)
        self.assertIn('KB', serializer.data['size_formatted'])

    def test_size_formatted_mb(self):
        self.trace.size = 5 * 1024 * 1024
        self.trace.save()
        serializer = MessageTraceLogSerializer(self.trace)
        self.assertIn('MB', serializer.data['size_formatted'])

    def test_list_serializer_excludes_heavy_fields(self):
        serializer = MessageTraceLogListSerializer(self.trace)
        data = serializer.data
        self.assertNotIn('raw_json', data)
        self.assertNotIn('event_data', data)

    def test_detail_serializer_includes_raw_json(self):
        serializer = MessageTraceLogDetailSerializer(self.trace)
        data = serializer.data
        self.assertIn('raw_json', data)


class PullHistorySerializerTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )
        now = timezone.now()
        self.pull = PullHistory.objects.create(
            tenant=self.tenant,
            pull_start_date=now - timedelta(days=1),
            pull_end_date=now,
            start_time=now - timedelta(seconds=90),
            end_time=now,
            status=PullHistory.Status.SUCCESS,
            records_pulled=100,
            records_new=80,
            records_updated=20,
        )

    def test_serialization(self):
        serializer = PullHistorySerializer(self.pull)
        data = serializer.data
        self.assertEqual(data['records_pulled'], 100)
        self.assertEqual(data['status'], 'Success')
        self.assertIn('duration_formatted', data)

    def test_duration_formatted(self):
        serializer = PullHistorySerializer(self.pull)
        data = serializer.data
        self.assertIn('m', data['duration_formatted'])

    def test_duration_formatted_none(self):
        self.pull.end_time = None
        self.pull.save()
        serializer = PullHistorySerializer(self.pull)
        self.assertIsNone(serializer.data['duration_formatted'])


class ManualPullRequestSerializerTest(TestCase):
    def test_valid_date_range(self):
        now = timezone.now()
        serializer = ManualPullRequestSerializer(data={
            'start_date': (now - timedelta(days=1)).isoformat(),
            'end_date': now.isoformat(),
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_start_after_end_rejected(self):
        now = timezone.now()
        serializer = ManualPullRequestSerializer(data={
            'start_date': now.isoformat(),
            'end_date': (now - timedelta(days=1)).isoformat(),
        })
        self.assertFalse(serializer.is_valid())

    def test_start_date_too_old_rejected(self):
        serializer = ManualPullRequestSerializer(data={
            'start_date': (timezone.now() - timedelta(days=15)).isoformat(),
        })
        self.assertFalse(serializer.is_valid())

    def test_optional_dates(self):
        serializer = ManualPullRequestSerializer(data={})
        self.assertTrue(serializer.is_valid())


# ---------------------------------------------------------------------------
# Task Helper Tests
# ---------------------------------------------------------------------------

class NormalizeStatusTest(TestCase):
    def test_delivered(self):
        self.assertEqual(_normalize_status('Delivered'), 'Delivered')

    def test_failed(self):
        self.assertEqual(_normalize_status('Failed'), 'Failed')

    def test_pending(self):
        self.assertEqual(_normalize_status('Pending'), 'Pending')

    def test_getting_status_maps_to_pending(self):
        self.assertEqual(_normalize_status('GettingStatus'), 'Pending')

    def test_quarantined(self):
        self.assertEqual(_normalize_status('Quarantined'), 'Quarantined')

    def test_filtered_as_spam(self):
        self.assertEqual(_normalize_status('FilteredAsSpam'), 'FilteredAsSpam')

    def test_expanded(self):
        self.assertEqual(_normalize_status('Expanded'), 'Expanded')

    def test_unknown_status(self):
        self.assertEqual(_normalize_status('SomethingWeird'), 'Unknown')

    def test_none_status(self):
        self.assertEqual(_normalize_status('None'), 'None')


# ---------------------------------------------------------------------------
# Filter Tests
# ---------------------------------------------------------------------------

class MessageTraceLogFilterTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )
        now = timezone.now()
        self.trace1 = MessageTraceLog.objects.create(
            tenant=self.tenant,
            message_id='<msg1@test.com>',
            received_date=now - timedelta(hours=1),
            sender='alice@contoso.com',
            recipient='bob@gmail.com',
            subject='Meeting Tomorrow',
            status=MessageTraceLog.Status.DELIVERED,
            direction=MessageTraceLog.Direction.OUTBOUND,
            size=1024,
        )
        self.trace2 = MessageTraceLog.objects.create(
            tenant=self.tenant,
            message_id='<msg2@test.com>',
            received_date=now - timedelta(hours=2),
            sender='charlie@gmail.com',
            recipient='alice@contoso.com',
            subject='Re: Invoice',
            status=MessageTraceLog.Status.FAILED,
            direction=MessageTraceLog.Direction.INBOUND,
            size=2048,
        )

    def test_filter_by_status(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'status': 'Delivered'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().id, self.trace1.id)

    def test_filter_by_direction(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'direction': 'Inbound'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().id, self.trace2.id)

    def test_filter_by_sender(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'sender': 'alice@contoso.com'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)

    def test_filter_by_sender_contains(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'sender_contains': 'alice'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)

    def test_filter_by_recipient_domain(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'recipient_domain': 'gmail.com'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)

    def test_filter_by_search(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'search': 'Invoice'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().id, self.trace2.id)

    def test_filter_by_search_sender(self):
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({'search': 'charlie'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)

    def test_filter_by_date_range(self):
        now = timezone.now()
        qs = MessageTraceLog.objects.all()
        f = MessageTraceLogFilter({
            'start_date': (now - timedelta(hours=1, minutes=30)).isoformat(),
            'end_date': now.isoformat(),
        }, queryset=qs)
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs.first().id, self.trace1.id)


class PullHistoryFilterTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )
        now = timezone.now()
        self.pull1 = PullHistory.objects.create(
            tenant=self.tenant,
            pull_start_date=now - timedelta(days=1),
            pull_end_date=now,
            status=PullHistory.Status.SUCCESS,
            trigger_type=PullHistory.TriggerType.SCHEDULED,
        )
        self.pull2 = PullHistory.objects.create(
            tenant=self.tenant,
            pull_start_date=now - timedelta(days=1),
            pull_end_date=now,
            status=PullHistory.Status.FAILED,
            trigger_type=PullHistory.TriggerType.MANUAL,
        )

    def test_filter_by_status(self):
        qs = PullHistory.objects.all()
        f = PullHistoryFilter({'status': 'Success'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)

    def test_filter_by_trigger_type(self):
        qs = PullHistory.objects.all()
        f = PullHistoryFilter({'trigger_type': 'Manual'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)


# ---------------------------------------------------------------------------
# API View Tests
# ---------------------------------------------------------------------------

class BaseTraceAPITestCase(APITestCase):
    """Base test class for trace API tests."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            'admin', 'admin@example.com', 'AdminPass123!'
        )
        self.admin_user.profile.role = UserProfile.Role.ADMIN
        self.admin_user.profile.save()
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.regular_user = User.objects.create_user(
            'user', 'user@example.com', 'UserPass123!'
        )
        self.regular_user.profile.role = UserProfile.Role.USER
        self.regular_user.profile.save()
        self.user_token = Token.objects.create(user=self.regular_user)

        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
            domains='contoso.com',
        )

        # Create some test data
        now = timezone.now()
        self.trace1 = MessageTraceLog.objects.create(
            tenant=self.tenant,
            message_id='<msg1@test.com>',
            received_date=now - timedelta(hours=1),
            sender='alice@contoso.com',
            recipient='bob@gmail.com',
            subject='Meeting',
            status=MessageTraceLog.Status.DELIVERED,
            direction=MessageTraceLog.Direction.OUTBOUND,
            size=1024,
        )
        self.trace2 = MessageTraceLog.objects.create(
            tenant=self.tenant,
            message_id='<msg2@test.com>',
            received_date=now - timedelta(hours=2),
            sender='charlie@gmail.com',
            recipient='alice@contoso.com',
            subject='Invoice',
            status=MessageTraceLog.Status.DELIVERED,
            direction=MessageTraceLog.Direction.INBOUND,
            size=2048,
        )

        self.pull = PullHistory.objects.create(
            tenant=self.tenant,
            pull_start_date=now - timedelta(days=1),
            pull_end_date=now,
            status=PullHistory.Status.SUCCESS,
            trigger_type=PullHistory.TriggerType.SCHEDULED,
            records_pulled=2,
            records_new=2,
        )

    def auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def auth_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')


class MessageTraceLogViewSetTest(BaseTraceAPITestCase):
    def test_list_traces_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/traces/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_list_traces_as_regular_user_no_permission(self):
        self.auth_user()
        response = self.client.get('/api/traces/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_traces_as_regular_user_with_permission(self):
        TenantPermission.objects.create(user=self.regular_user, tenant=self.tenant)
        self.auth_user()
        response = self.client.get('/api/traces/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_list_traces_unauthenticated(self):
        response = self.client.get('/api/traces/')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_trace_detail(self):
        self.auth_admin()
        response = self.client.get(f'/api/traces/{self.trace1.id}/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['sender'], 'alice@contoso.com')
        self.assertIn('raw_json', response.data)

    def test_filter_by_status(self):
        self.auth_admin()
        response = self.client.get('/api/traces/', {'status': 'Delivered'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filter_by_direction(self):
        self.auth_admin()
        response = self.client.get('/api/traces/', {'direction': 'Outbound'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_by_search(self):
        self.auth_admin()
        response = self.client.get('/api/traces/', {'search': 'Invoice'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filter_by_tenant(self):
        self.auth_admin()
        response = self.client.get('/api/traces/', {'tenant': self.tenant.id})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filter_by_nonexistent_tenant(self):
        self.auth_admin()
        response = self.client.get('/api/traces/', {'tenant': 9999})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_ordering_default(self):
        self.auth_admin()
        response = self.client.get('/api/traces/')
        results = response.data['results']
        self.assertEqual(results[0]['id'], self.trace1.id)  # Newest first

    def test_ordering_by_size(self):
        self.auth_admin()
        response = self.client.get('/api/traces/', {'ordering': 'size'})
        results = response.data['results']
        self.assertEqual(results[0]['id'], self.trace1.id)  # Smallest first


class PullHistoryViewSetTest(BaseTraceAPITestCase):
    def test_list_pull_history_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/pull-history/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_list_pull_history_as_regular_user_no_permission(self):
        self.auth_user()
        response = self.client.get('/api/pull-history/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_list_pull_history_with_permission(self):
        TenantPermission.objects.create(user=self.regular_user, tenant=self.tenant)
        self.auth_user()
        response = self.client.get('/api/pull-history/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_retrieve_pull_detail(self):
        self.auth_admin()
        response = self.client.get(f'/api/pull-history/{self.pull.id}/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['records_pulled'], 2)


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_AUTHENTICATION_CLASSES': [
            'rest_framework.authentication.TokenAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            'rest_framework.permissions.IsAuthenticated',
        ],
        'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
        'PAGE_SIZE': 50,
        'DEFAULT_FILTER_BACKENDS': [
            'django_filters.rest_framework.DjangoFilterBackend',
            'rest_framework.filters.SearchFilter',
            'rest_framework.filters.OrderingFilter',
        ],
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {
            'manual_pull': '100/hour',
        },
    }
)
class ManualPullViewTest(BaseTraceAPITestCase):
    def test_manual_pull_requires_admin(self):
        self.auth_user()
        response = self.client.post('/api/manual-pull/', {
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_manual_pull_requires_tenant_id(self):
        self.auth_admin()
        response = self.client.post('/api/manual-pull/', {})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_manual_pull_nonexistent_tenant(self):
        self.auth_admin()
        response = self.client.post('/api/manual-pull/', {
            'tenant_id': 9999,
        })
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    @patch('traces.tasks.pull_message_traces_for_tenant')
    def test_manual_pull_success(self, mock_pull):
        mock_pull.return_value = {
            'pull_history_id': 1,
            'status': 'Success',
            'records_pulled': 10,
            'records_new': 8,
            'records_updated': 2,
        }
        self.auth_admin()
        response = self.client.post('/api/manual-pull/', {
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['records_pulled'], 10)
        mock_pull.assert_called_once()

    @patch('traces.tasks.pull_message_traces_for_tenant')
    def test_manual_pull_failure(self, mock_pull):
        mock_pull.side_effect = Exception('Connection failed')
        self.auth_admin()
        response = self.client.post('/api/manual-pull/', {
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_manual_pull_unauthenticated(self):
        response = self.client.post('/api/manual-pull/', {
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class DashboardViewTest(BaseTraceAPITestCase):
    def test_dashboard_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_traces'], 2)
        self.assertIn('delivered_count', response.data)
        self.assertIn('inbound_count', response.data)
        self.assertIn('recent_pulls', response.data)

    def test_dashboard_filter_by_tenant(self):
        self.auth_admin()
        response = self.client.get('/api/dashboard/', {'tenant': self.tenant.id})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_traces'], 2)

    def test_dashboard_as_regular_user(self):
        self.auth_user()
        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data['total_traces'], 0)  # No tenant access

    def test_dashboard_unauthenticated(self):
        response = self.client.get('/api/dashboard/')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class ConfigViewTest(BaseTraceAPITestCase):
    def test_config_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/config/')
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertIn('scheduler', response.data)
        self.assertIn('pull_interval_hours', response.data['scheduler'])
        self.assertIn('pull_interval_minutes', response.data['scheduler'])
        self.assertIn('multi_tenant', response.data)
        self.assertIn('database', response.data)

    def test_config_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.get('/api/config/')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_config_unauthenticated(self):
        response = self.client.get('/api/config/')
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Scheduler Command Tests
# ---------------------------------------------------------------------------

class RunSchedulerCommandTest(TestCase):
    def test_get_interval_from_settings(self):
        """Test that scheduler reads interval from DB settings."""
        settings = AppSettings.get_settings()
        settings.scheduled_pull_interval_hours = 6
        settings.scheduled_pull_interval_minutes = 15
        settings.save()

        from traces.management.commands.run_scheduler import Command
        cmd = Command()
        hours, minutes, enabled = cmd._get_interval_from_settings()
        self.assertEqual(hours, 6)
        self.assertEqual(minutes, 15)
        self.assertTrue(enabled)

    def test_get_interval_disabled(self):
        settings = AppSettings.get_settings()
        settings.scheduled_pull_enabled = False
        settings.save()

        from traces.management.commands.run_scheduler import Command
        cmd = Command()
        _, _, enabled = cmd._get_interval_from_settings()
        self.assertFalse(enabled)

    def test_get_interval_defaults(self):
        """Test default values when no settings exist yet."""
        from traces.management.commands.run_scheduler import Command
        cmd = Command()
        hours, minutes, enabled = cmd._get_interval_from_settings()
        self.assertEqual(hours, 24)
        self.assertEqual(minutes, 0)
        self.assertTrue(enabled)
