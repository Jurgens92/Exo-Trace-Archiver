"""
Comprehensive tests for the accounts app.

Tests cover:
- Models: UserProfile, Tenant, TenantPermission, TenantAuditLog, AppSettings
- Serializers: All account serializers
- Views: User, Tenant, Permission, Settings, CurrentUser endpoints
- Permissions: IsAdminRole, HasTenantAccess, get_accessible_tenant_ids
"""

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from .models import UserProfile, Tenant, TenantPermission, TenantAuditLog, AppSettings
from .serializers import (
    AppSettingsSerializer,
    TenantCreateSerializer,
    TenantListSerializer,
    UserCreateSerializer,
    UserListSerializer,
    CurrentUserSerializer,
    TenantPermissionCreateSerializer,
)
from .permissions import IsAdminRole, get_accessible_tenant_ids, user_is_admin


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class UserProfileModelTest(TestCase):
    def test_profile_created_on_user_creation(self):
        user = User.objects.create_user('testuser', 'test@example.com', 'password123')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)

    def test_first_user_gets_admin_role(self):
        user = User.objects.create_user('firstuser', 'first@example.com', 'password123')
        self.assertEqual(user.profile.role, UserProfile.Role.ADMIN)
        self.assertTrue(user.profile.is_admin)

    def test_second_user_gets_user_role(self):
        User.objects.create_user('firstuser', 'first@example.com', 'password123')
        user2 = User.objects.create_user('seconduser', 'second@example.com', 'password123')
        self.assertEqual(user2.profile.role, UserProfile.Role.USER)
        self.assertFalse(user2.profile.is_admin)

    def test_str_representation(self):
        user = User.objects.create_user('testuser', 'test@example.com', 'password123')
        self.assertIn('testuser', str(user.profile))

    def test_is_admin_property(self):
        user = User.objects.create_user('admin', 'admin@example.com', 'password123')
        user.profile.role = UserProfile.Role.ADMIN
        user.profile.save()
        self.assertTrue(user.profile.is_admin)

        user.profile.role = UserProfile.Role.USER
        user.profile.save()
        self.assertFalse(user.profile.is_admin)


class TenantModelTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            auth_method='certificate',
            certificate_path='/path/to/cert.pfx',
            api_method='graph',
            organization='contoso.onmicrosoft.com',
            domains='contoso.com,contoso.onmicrosoft.com',
        )

    def test_str_representation(self):
        self.assertIn('Test Tenant', str(self.tenant))
        self.assertIn('12345678', str(self.tenant))

    def test_get_organization_domains_from_domains_field(self):
        domains = self.tenant.get_organization_domains()
        self.assertIn('contoso.com', domains)
        self.assertIn('contoso.onmicrosoft.com', domains)

    def test_get_organization_domains_fallback_to_organization(self):
        self.tenant.domains = ''
        self.tenant.save()
        domains = self.tenant.get_organization_domains()
        self.assertIn('contoso.onmicrosoft.com', domains)

    def test_get_organization_domains_empty(self):
        self.tenant.domains = ''
        self.tenant.organization = ''
        self.tenant.save()
        domains = self.tenant.get_organization_domains()
        self.assertEqual(domains, [])

    def test_get_organization_domains_dedup(self):
        self.tenant.domains = 'contoso.com,contoso.com,contoso.onmicrosoft.com'
        self.tenant.save()
        domains = self.tenant.get_organization_domains()
        self.assertEqual(len(domains), 2)

    def test_unique_tenant_id_constraint(self):
        with self.assertRaises(Exception):
            Tenant.objects.create(
                name='Duplicate Tenant',
                tenant_id='12345678-1234-1234-1234-123456789012',
                client_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                certificate_path='/path/to/cert.pfx',
            )

    def test_default_values(self):
        tenant = Tenant.objects.create(
            name='Minimal Tenant',
            tenant_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            client_id='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            certificate_path='/path/to/cert.pfx',
        )
        self.assertTrue(tenant.is_active)
        self.assertEqual(tenant.auth_method, 'certificate')
        self.assertEqual(tenant.api_method, 'graph')


class TenantPermissionModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'password123')
        self.user = User.objects.create_user('user', 'user@example.com', 'password123')
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )

    def test_create_permission(self):
        perm = TenantPermission.objects.create(
            user=self.user,
            tenant=self.tenant,
            granted_by=self.admin,
        )
        self.assertEqual(str(perm), f"{self.user.username} -> {self.tenant.name}")

    def test_unique_user_tenant_constraint(self):
        TenantPermission.objects.create(user=self.user, tenant=self.tenant)
        with self.assertRaises(Exception):
            TenantPermission.objects.create(user=self.user, tenant=self.tenant)


class TenantAuditLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('admin', 'admin@example.com', 'password123')
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )

    def test_create_audit_log(self):
        log = TenantAuditLog.objects.create(
            tenant=self.tenant,
            tenant_name=self.tenant.name,
            action=TenantAuditLog.Action.CREATE,
            status=TenantAuditLog.Status.SUCCESS,
            detail='Test log entry',
            performed_by=self.user,
        )
        self.assertIn('create', str(log))
        self.assertIn('Test Tenant', str(log))

    def test_audit_log_ordering(self):
        TenantAuditLog.objects.create(
            tenant=self.tenant, tenant_name='T1',
            action=TenantAuditLog.Action.CREATE,
            status=TenantAuditLog.Status.SUCCESS,
        )
        TenantAuditLog.objects.create(
            tenant=self.tenant, tenant_name='T2',
            action=TenantAuditLog.Action.UPDATE,
            status=TenantAuditLog.Status.SUCCESS,
        )
        logs = TenantAuditLog.objects.all()
        self.assertTrue(logs[0].created_at >= logs[1].created_at)


class AppSettingsModelTest(TestCase):
    def test_singleton_creation(self):
        settings = AppSettings.get_settings()
        self.assertEqual(settings.pk, 1)
        self.assertTrue(settings.scheduled_pull_enabled)
        self.assertEqual(settings.scheduled_pull_interval_hours, 24)
        self.assertEqual(settings.scheduled_pull_interval_minutes, 0)

    def test_singleton_enforced(self):
        s1 = AppSettings.get_settings()
        s2 = AppSettings.get_settings()
        self.assertEqual(s1.pk, s2.pk)

    def test_cannot_delete(self):
        settings = AppSettings.get_settings()
        settings.delete()
        # Should still exist
        self.assertTrue(AppSettings.objects.filter(pk=1).exists())

    def test_default_values(self):
        settings = AppSettings.get_settings()
        self.assertTrue(settings.domain_discovery_auto_refresh)
        self.assertEqual(settings.domain_discovery_refresh_hours, 24)
        self.assertTrue(settings.scheduled_pull_enabled)
        self.assertEqual(settings.scheduled_pull_interval_hours, 24)
        self.assertEqual(settings.scheduled_pull_interval_minutes, 0)

    def test_update_settings(self):
        settings = AppSettings.get_settings()
        settings.scheduled_pull_interval_hours = 12
        settings.scheduled_pull_interval_minutes = 30
        settings.save()

        reloaded = AppSettings.get_settings()
        self.assertEqual(reloaded.scheduled_pull_interval_hours, 12)
        self.assertEqual(reloaded.scheduled_pull_interval_minutes, 30)

    def test_str_representation(self):
        settings = AppSettings.get_settings()
        self.assertEqual(str(settings), "Application Settings")


# ---------------------------------------------------------------------------
# Serializer Tests
# ---------------------------------------------------------------------------

class AppSettingsSerializerTest(TestCase):
    def test_serialization(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(settings)
        data = serializer.data
        self.assertIn('scheduled_pull_interval_hours', data)
        self.assertIn('scheduled_pull_interval_minutes', data)
        self.assertIn('scheduled_pull_enabled', data)
        self.assertIn('domain_discovery_auto_refresh', data)

    def test_valid_update(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(
            settings,
            data={'scheduled_pull_interval_hours': 6, 'scheduled_pull_interval_minutes': 30},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_interval_hours(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(
            settings,
            data={'scheduled_pull_interval_hours': 200},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())

    def test_invalid_interval_minutes(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(
            settings,
            data={'scheduled_pull_interval_minutes': 60},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())

    def test_zero_interval_rejected(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(
            settings,
            data={'scheduled_pull_interval_hours': 0, 'scheduled_pull_interval_minutes': 0},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())

    def test_invalid_refresh_hours(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(
            settings,
            data={'domain_discovery_refresh_hours': 0},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())

    def test_valid_minimum_interval(self):
        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(
            settings,
            data={'scheduled_pull_interval_hours': 0, 'scheduled_pull_interval_minutes': 1},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)


class TenantCreateSerializerTest(TestCase):
    def test_valid_tenant_creation(self):
        user = User.objects.create_user('admin', 'admin@example.com', 'password123')
        from rest_framework.test import APIRequestFactory
        factory = APIRequestFactory()
        request = factory.post('/')
        request.user = user

        data = {
            'name': 'New Tenant',
            'tenant_id': '12345678-1234-1234-1234-123456789012',
            'client_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'auth_method': 'certificate',
            'certificate_path': '/path/to/cert.pfx',
        }
        serializer = TenantCreateSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_tenant_id_format(self):
        data = {
            'name': 'New Tenant',
            'tenant_id': 'not-a-guid',
            'client_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'certificate_path': '/path/to/cert.pfx',
        }
        serializer = TenantCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('tenant_id', serializer.errors)

    def test_invalid_client_id_format(self):
        data = {
            'name': 'New Tenant',
            'tenant_id': '12345678-1234-1234-1234-123456789012',
            'client_id': 'not-a-guid',
            'certificate_path': '/path/to/cert.pfx',
        }
        serializer = TenantCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('client_id', serializer.errors)

    def test_secret_auth_requires_secret(self):
        data = {
            'name': 'New Tenant',
            'tenant_id': '12345678-1234-1234-1234-123456789012',
            'client_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'auth_method': 'secret',
        }
        serializer = TenantCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_certificate_auth_requires_path(self):
        data = {
            'name': 'New Tenant',
            'tenant_id': '12345678-1234-1234-1234-123456789012',
            'client_id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'auth_method': 'certificate',
        }
        serializer = TenantCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class UserCreateSerializerTest(TestCase):
    def test_valid_user_creation(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'role': 'user',
        }
        serializer = UserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_password_mismatch(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password_confirm': 'DifferentPass123!',
        }
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_confirm', serializer.errors)

    def test_weak_password_rejected(self):
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': '123',
            'password_confirm': '123',
        }
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class TenantPermissionCreateSerializerTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'password123')
        self.user = User.objects.create_user('user', 'user@example.com', 'password123')
        self.user.profile.role = UserProfile.Role.USER
        self.user.profile.save()
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            tenant_id='12345678-1234-1234-1234-123456789012',
            client_id='abcdefgh-abcd-abcd-abcd-abcdefghijkl',
            certificate_path='/path/to/cert.pfx',
        )

    def test_admin_user_rejected(self):
        """Admin users should not need explicit permissions."""
        data = {'user': self.admin.id, 'tenant': self.tenant.id}
        serializer = TenantPermissionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_duplicate_permission_rejected(self):
        TenantPermission.objects.create(user=self.user, tenant=self.tenant)
        data = {'user': self.user.id, 'tenant': self.tenant.id}
        serializer = TenantPermissionCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())


# ---------------------------------------------------------------------------
# Permission Tests
# ---------------------------------------------------------------------------

class PermissionHelperTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', 'admin@example.com', 'password123')
        self.admin.profile.role = UserProfile.Role.ADMIN
        self.admin.profile.save()

        self.regular_user = User.objects.create_user('user', 'user@example.com', 'password123')
        self.regular_user.profile.role = UserProfile.Role.USER
        self.regular_user.profile.save()

        self.tenant1 = Tenant.objects.create(
            name='Tenant 1',
            tenant_id='11111111-1111-1111-1111-111111111111',
            client_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            certificate_path='/path/to/cert.pfx',
        )
        self.tenant2 = Tenant.objects.create(
            name='Tenant 2',
            tenant_id='22222222-2222-2222-2222-222222222222',
            client_id='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            certificate_path='/path/to/cert.pfx',
        )

    def test_admin_gets_all_tenant_ids(self):
        ids = get_accessible_tenant_ids(self.admin)
        self.assertIn(self.tenant1.id, ids)
        self.assertIn(self.tenant2.id, ids)

    def test_regular_user_gets_only_assigned_tenants(self):
        TenantPermission.objects.create(user=self.regular_user, tenant=self.tenant1)
        ids = get_accessible_tenant_ids(self.regular_user)
        self.assertIn(self.tenant1.id, ids)
        self.assertNotIn(self.tenant2.id, ids)

    def test_regular_user_no_permissions(self):
        ids = get_accessible_tenant_ids(self.regular_user)
        self.assertEqual(ids, [])

    def test_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser
        ids = get_accessible_tenant_ids(AnonymousUser())
        self.assertEqual(ids, [])

    def test_user_is_admin_helper(self):
        self.assertTrue(user_is_admin(self.admin))
        self.assertFalse(user_is_admin(self.regular_user))

    def test_superuser_is_admin(self):
        superuser = User.objects.create_superuser('super', 'super@example.com', 'password123')
        self.assertTrue(user_is_admin(superuser))
        ids = get_accessible_tenant_ids(superuser)
        self.assertEqual(len(ids), 2)

    def test_inactive_tenants_excluded(self):
        self.tenant2.is_active = False
        self.tenant2.save()
        ids = get_accessible_tenant_ids(self.admin)
        self.assertIn(self.tenant1.id, ids)
        self.assertNotIn(self.tenant2.id, ids)


# ---------------------------------------------------------------------------
# API View Tests
# ---------------------------------------------------------------------------

class BaseAPITestCase(APITestCase):
    """Base test class with common setup for API tests."""

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
            auth_method='certificate',
            certificate_path='/path/to/cert.pfx',
            api_method='graph',
            organization='contoso.onmicrosoft.com',
            domains='contoso.com,contoso.onmicrosoft.com',
        )

    def auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def auth_user(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_token.key}')


class UserViewSetTest(BaseAPITestCase):
    def test_list_users_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_users_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_user_as_admin(self):
        self.auth_admin()
        response = self.client.post('/api/accounts/users/', {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
            'role': 'user',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_create_user_unauthenticated(self):
        response = self.client.post('/api/accounts/users/', {
            'username': 'newuser',
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_user_as_admin(self):
        self.auth_admin()
        response = self.client.delete(f'/api/accounts/users/{self.regular_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_delete_self(self):
        self.auth_admin()
        response = self.client.delete(f'/api/accounts/users/{self.admin_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_user_as_admin(self):
        self.auth_admin()
        response = self.client.patch(
            f'/api/accounts/users/{self.regular_user.id}/',
            {'first_name': 'Updated'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Updated')


class TenantViewSetTest(BaseAPITestCase):
    def test_list_tenants_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/tenants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_tenants_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.get('/api/accounts/tenants/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_tenant_as_admin(self):
        self.auth_admin()
        response = self.client.post('/api/accounts/tenants/', {
            'name': 'New Tenant',
            'tenant_id': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            'client_id': 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            'auth_method': 'certificate',
            'certificate_path': '/path/to/cert.pfx',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tenant.objects.filter(name='New Tenant').exists())
        # Verify audit log was created
        self.assertTrue(TenantAuditLog.objects.filter(
            action=TenantAuditLog.Action.CREATE
        ).exists())

    def test_update_tenant_creates_audit_log(self):
        self.auth_admin()
        response = self.client.patch(
            f'/api/accounts/tenants/{self.tenant.id}/',
            {'name': 'Updated Tenant'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(TenantAuditLog.objects.filter(
            action=TenantAuditLog.Action.UPDATE
        ).exists())

    def test_delete_tenant_creates_audit_log(self):
        self.auth_admin()
        response = self.client.delete(f'/api/accounts/tenants/{self.tenant.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(TenantAuditLog.objects.filter(
            action=TenantAuditLog.Action.DELETE
        ).exists())

    def test_retrieve_tenant_detail(self):
        self.auth_admin()
        response = self.client.get(f'/api/accounts/tenants/{self.tenant.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Tenant')


class CurrentUserViewTest(BaseAPITestCase):
    def test_get_current_user(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'admin')
        self.assertTrue(response.data['is_admin'])

    def test_regular_user_profile(self):
        self.auth_user()
        response = self.client.get('/api/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'user')
        self.assertFalse(response.data['is_admin'])

    def test_update_current_user(self):
        self.auth_user()
        response = self.client.patch('/api/accounts/me/', {
            'first_name': 'Updated',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Updated')

    def test_unauthenticated_access(self):
        response = self.client.get('/api/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AccessibleTenantsViewTest(BaseAPITestCase):
    def test_admin_sees_all_tenants(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/me/tenants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_regular_user_sees_assigned_tenants(self):
        TenantPermission.objects.create(
            user=self.regular_user,
            tenant=self.tenant,
        )
        self.auth_user()
        response = self.client.get('/api/accounts/me/tenants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_regular_user_no_tenants(self):
        self.auth_user()
        response = self.client.get('/api/accounts/me/tenants/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class AppSettingsViewTest(BaseAPITestCase):
    def test_get_settings_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/settings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('scheduled_pull_interval_hours', response.data)
        self.assertIn('scheduled_pull_interval_minutes', response.data)
        self.assertIn('scheduled_pull_enabled', response.data)

    def test_get_settings_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.get('/api/accounts/settings/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_settings_as_admin(self):
        self.auth_admin()
        response = self.client.patch('/api/accounts/settings/', {
            'scheduled_pull_interval_hours': 12,
            'scheduled_pull_interval_minutes': 30,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings = AppSettings.get_settings()
        self.assertEqual(settings.scheduled_pull_interval_hours, 12)
        self.assertEqual(settings.scheduled_pull_interval_minutes, 30)

    def test_update_settings_sets_updated_by(self):
        self.auth_admin()
        self.client.patch('/api/accounts/settings/', {
            'scheduled_pull_enabled': False,
        })
        settings = AppSettings.get_settings()
        self.assertEqual(settings.updated_by, self.admin_user)

    def test_update_settings_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.patch('/api/accounts/settings/', {
            'scheduled_pull_interval_hours': 1,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_interval_rejected(self):
        self.auth_admin()
        response = self.client.patch('/api/accounts/settings/', {
            'scheduled_pull_interval_hours': 0,
            'scheduled_pull_interval_minutes': 0,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disable_scheduled_pulls(self):
        self.auth_admin()
        response = self.client.patch('/api/accounts/settings/', {
            'scheduled_pull_enabled': False,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings = AppSettings.get_settings()
        self.assertFalse(settings.scheduled_pull_enabled)

    def test_update_domain_discovery_settings(self):
        self.auth_admin()
        response = self.client.patch('/api/accounts/settings/', {
            'domain_discovery_auto_refresh': False,
            'domain_discovery_refresh_hours': 48,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        settings = AppSettings.get_settings()
        self.assertFalse(settings.domain_discovery_auto_refresh)
        self.assertEqual(settings.domain_discovery_refresh_hours, 48)


class TenantPermissionViewSetTest(BaseAPITestCase):
    def test_list_permissions_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/permissions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_permission_as_admin(self):
        self.auth_admin()
        response = self.client.post('/api/accounts/permissions/', {
            'user': self.regular_user.id,
            'tenant': self.tenant.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_permission_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.post('/api/accounts/permissions/', {
            'user': self.regular_user.id,
            'tenant': self.tenant.id,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AuditLogViewSetTest(BaseAPITestCase):
    def test_list_audit_logs_as_admin(self):
        self.auth_admin()
        response = self.client.get('/api/accounts/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_audit_logs_as_regular_user_forbidden(self):
        self.auth_user()
        response = self.client.get('/api/accounts/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
