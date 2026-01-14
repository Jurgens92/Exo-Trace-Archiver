"""
API views for multi-tenant user management.

Provides endpoints for:
- User CRUD (admin only)
- Tenant CRUD (admin only)
- Tenant permission management (admin only)
- Current user profile
- Certificate upload
"""

import os
import uuid
import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import viewsets, views, status, filters
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import UserProfile, Tenant, TenantPermission
from .serializers import (
    UserListSerializer,
    UserDetailSerializer,
    UserCreateSerializer,
    UserUpdateSerializer,
    TenantListSerializer,
    TenantDetailSerializer,
    TenantCreateSerializer,
    TenantUpdateSerializer,
    TenantPermissionSerializer,
    TenantPermissionCreateSerializer,
    BulkTenantPermissionSerializer,
    CurrentUserSerializer,
)
from .permissions import IsAdminRole, get_accessible_tenant_ids


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users.

    Admin-only endpoints for:
    - List all users
    - Create new users
    - Update existing users
    - Delete users
    - Manage user tenant permissions
    """

    queryset = User.objects.select_related('profile').order_by('-date_joined')
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'email', 'date_joined', 'last_login']
    ordering = ['-date_joined']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserDetailSerializer

    def destroy(self, request, *args, **kwargs):
        """Delete user - prevent self-deletion."""
        user = self.get_object()
        if user == request.user:
            return Response(
                {'detail': 'Cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def set_role(self, request, pk=None):
        """Set user role (admin or user)."""
        user = self.get_object()

        if user == request.user:
            return Response(
                {'detail': 'Cannot change your own role.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        role = request.data.get('role')
        if role not in [UserProfile.Role.ADMIN, UserProfile.Role.USER]:
            return Response(
                {'detail': f'Invalid role. Must be one of: {UserProfile.Role.ADMIN}, {UserProfile.Role.USER}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()

        return Response({'detail': f'Role updated to {role}.'})

    @action(detail=True, methods=['get', 'post', 'delete'])
    def tenant_permissions(self, request, pk=None):
        """Manage tenant permissions for a user."""
        user = self.get_object()

        if request.method == 'GET':
            # List user's tenant permissions
            permissions = TenantPermission.objects.filter(user=user).select_related('tenant')
            serializer = TenantPermissionSerializer(permissions, many=True)
            return Response(serializer.data)

        elif request.method == 'POST':
            # Add tenant permission
            serializer = BulkTenantPermissionSerializer(data={
                'user_id': user.id,
                'tenant_ids': request.data.get('tenant_ids', [])
            })
            serializer.is_valid(raise_exception=True)

            tenant_ids = serializer.validated_data['tenant_ids']
            created = []

            with transaction.atomic():
                for tenant_id in tenant_ids:
                    perm, was_created = TenantPermission.objects.get_or_create(
                        user=user,
                        tenant_id=tenant_id,
                        defaults={'granted_by': request.user}
                    )
                    if was_created:
                        created.append(tenant_id)

            return Response({
                'detail': f'Added permissions for {len(created)} tenant(s).',
                'created_tenant_ids': created
            })

        elif request.method == 'DELETE':
            # Remove tenant permissions
            tenant_ids = request.data.get('tenant_ids', [])
            deleted = TenantPermission.objects.filter(
                user=user,
                tenant_id__in=tenant_ids
            ).delete()[0]

            return Response({
                'detail': f'Removed {deleted} permission(s).'
            })


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing MS365 tenants.

    Admin-only endpoints for:
    - List all tenants
    - Create new tenants
    - Update tenant configuration
    - Delete tenants
    - View tenant users
    """

    queryset = Tenant.objects.order_by('name')
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'tenant_id', 'organization']
    filterset_fields = ['is_active', 'auth_method', 'api_method']
    ordering_fields = ['name', 'created_at', 'organization']
    ordering = ['name']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return TenantListSerializer
        elif self.action == 'create':
            return TenantCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TenantUpdateSerializer
        return TenantDetailSerializer

    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get list of users with access to this tenant."""
        tenant = self.get_object()
        permissions = TenantPermission.objects.filter(
            tenant=tenant
        ).select_related('user', 'granted_by')

        serializer = TenantPermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_users(self, request, pk=None):
        """Add multiple users to this tenant."""
        tenant = self.get_object()
        user_ids = request.data.get('user_ids', [])

        if not user_ids:
            return Response(
                {'detail': 'No user IDs provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate users exist
        users = User.objects.filter(id__in=user_ids)
        if users.count() != len(user_ids):
            return Response(
                {'detail': 'One or more user IDs are invalid.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = []
        skipped = []

        with transaction.atomic():
            for user in users:
                # Skip admin users
                if hasattr(user, 'profile') and user.profile.is_admin:
                    skipped.append({'id': user.id, 'reason': 'Admin users have access to all tenants'})
                    continue

                perm, was_created = TenantPermission.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={'granted_by': request.user}
                )
                if was_created:
                    created.append(user.id)
                else:
                    skipped.append({'id': user.id, 'reason': 'Already has permission'})

        return Response({
            'detail': f'Added {len(created)} user(s) to tenant.',
            'created_user_ids': created,
            'skipped': skipped
        })

    @action(detail=True, methods=['post'])
    def remove_users(self, request, pk=None):
        """Remove multiple users from this tenant."""
        tenant = self.get_object()
        user_ids = request.data.get('user_ids', [])

        if not user_ids:
            return Response(
                {'detail': 'No user IDs provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted = TenantPermission.objects.filter(
            tenant=tenant,
            user_id__in=user_ids
        ).delete()[0]

        return Response({
            'detail': f'Removed {deleted} user(s) from tenant.'
        })

    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test connection to the MS365 tenant."""
        import logging
        logger = logging.getLogger('accounts')

        tenant = self.get_object()

        try:
            from traces.ms365_client import get_ms365_client_for_tenant
            client = get_ms365_client_for_tenant(tenant)
            # Try to authenticate
            client._get_access_token()
            return Response({
                'status': 'success',
                'detail': 'Successfully authenticated with tenant.'
            })
        except Exception as e:
            logger.error(f"Test connection failed for tenant {tenant.name}: {str(e)}")
            return Response({
                'status': 'failed',
                'detail': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class TenantPermissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant permissions directly.

    Admin-only endpoints for CRUD operations on permissions.
    """

    queryset = TenantPermission.objects.select_related(
        'user', 'tenant', 'granted_by'
    ).order_by('-granted_at')
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'tenant']

    def get_serializer_class(self):
        if self.action == 'create':
            return TenantPermissionCreateSerializer
        return TenantPermissionSerializer


class CurrentUserView(views.APIView):
    """
    View for getting/updating the current authenticated user's profile.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current user's profile with accessible tenants."""
        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update current user's profile (limited fields)."""
        allowed_fields = ['email', 'first_name', 'last_name']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}

        for key, value in update_data.items():
            setattr(request.user, key, value)
        request.user.save()

        serializer = CurrentUserSerializer(request.user)
        return Response(serializer.data)


class AccessibleTenantsView(views.APIView):
    """
    View for getting list of tenants accessible to current user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get list of tenants the current user can access."""
        tenant_ids = get_accessible_tenant_ids(request.user)
        tenants = Tenant.objects.filter(id__in=tenant_ids, is_active=True)

        serializer = TenantListSerializer(tenants, many=True)
        return Response(serializer.data)


class CertificateUploadView(views.APIView):
    """
    View for uploading certificate files for tenant authentication.

    Accepts .pfx, .pem, or .cer certificate files and stores them
    in a secure location on the server.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    ALLOWED_EXTENSIONS = {'.pfx', '.pem', '.cer', '.crt', '.p12'}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    def post(self, request):
        """Upload a certificate file."""
        if 'certificate' not in request.FILES:
            return Response(
                {'detail': 'No certificate file provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cert_file = request.FILES['certificate']

        # Validate file extension
        file_ext = Path(cert_file.name).suffix.lower()
        if file_ext not in self.ALLOWED_EXTENSIONS:
            return Response(
                {'detail': f'Invalid file type. Allowed types: {", ".join(self.ALLOWED_EXTENSIONS)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate file size
        if cert_file.size > self.MAX_FILE_SIZE:
            return Response(
                {'detail': f'File too large. Maximum size is {self.MAX_FILE_SIZE // (1024 * 1024)} MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate unique filename
        unique_id = uuid.uuid4().hex[:12]
        safe_name = f"cert_{unique_id}{file_ext}"

        # Create certificates directory if it doesn't exist
        cert_dir = getattr(settings, 'CERTIFICATES_DIR', settings.BASE_DIR / 'certificates')
        cert_dir = Path(cert_dir)
        cert_dir.mkdir(parents=True, exist_ok=True)

        # Save the file
        cert_path = cert_dir / safe_name

        try:
            with open(cert_path, 'wb+') as destination:
                for chunk in cert_file.chunks():
                    destination.write(chunk)

            # Set restrictive permissions (owner read/write only)
            os.chmod(cert_path, 0o600)

            # Calculate thumbprint for PFX/PEM files
            thumbprint = None
            try:
                thumbprint = self._calculate_thumbprint(cert_path, file_ext)
            except Exception:
                # Thumbprint calculation is optional - don't fail the upload
                pass

            return Response({
                'certificate_path': str(cert_path),
                'certificate_thumbprint': thumbprint,
                'filename': safe_name,
                'size': cert_file.size,
            }, status=status.HTTP_201_CREATED)

        except IOError as e:
            return Response(
                {'detail': f'Failed to save certificate: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _calculate_thumbprint(self, cert_path: Path, file_ext: str) -> str | None:
        """
        Calculate the SHA1 thumbprint of a certificate.

        Note: This is a simplified implementation. For production use,
        you may want to use cryptography library for proper cert parsing.
        """
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.serialization import pkcs12

            with open(cert_path, 'rb') as f:
                cert_data = f.read()

            if file_ext in ['.pfx', '.p12']:
                # Parse PKCS12 (try without password first)
                try:
                    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                        cert_data, None
                    )
                except Exception:
                    # Certificate may be password protected
                    return None

                if certificate:
                    fingerprint = certificate.fingerprint(hashes.SHA1())
                    return fingerprint.hex().upper()
            elif file_ext in ['.pem', '.cer', '.crt']:
                # Parse PEM certificate
                try:
                    certificate = x509.load_pem_x509_certificate(cert_data)
                    fingerprint = certificate.fingerprint(hashes.SHA1())
                    return fingerprint.hex().upper()
                except Exception:
                    # Try DER format
                    try:
                        certificate = x509.load_der_x509_certificate(cert_data)
                        fingerprint = certificate.fingerprint(hashes.SHA1())
                        return fingerprint.hex().upper()
                    except Exception:
                        return None
        except ImportError:
            # cryptography library not available
            return None
        except Exception:
            return None

        return None


class AppSettingsView(views.APIView):
    """
    View for getting and updating application-wide settings.

    GET /api/app-settings/
    PATCH /api/app-settings/

    Admin-only: Only admin users can view or update app settings.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        """Get current application settings."""
        from .models import AppSettings
        from .serializers import AppSettingsSerializer

        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(settings)
        return Response(serializer.data)

    def patch(self, request):
        """Update application settings."""
        from .models import AppSettings
        from .serializers import AppSettingsSerializer

        settings = AppSettings.get_settings()
        serializer = AppSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Update settings
        for key, value in serializer.validated_data.items():
            setattr(settings, key, value)

        settings.updated_by = request.user
        settings.save()

        return Response({
            'message': 'Settings updated successfully',
            'settings': AppSettingsSerializer(settings).data
        })
