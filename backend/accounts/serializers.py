"""
Serializers for multi-tenant user management.

Provides serializers for:
- User management (create, update, list)
- Tenant management (CRUD)
- Tenant permissions (assign/revoke)
"""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import UserProfile, Tenant, TenantPermission


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""

    class Meta:
        model = UserProfile
        fields = ['role', 'is_admin', 'created_at', 'updated_at']
        read_only_fields = ['is_admin', 'created_at', 'updated_at']


class UserListSerializer(serializers.ModelSerializer):
    """Serializer for listing users with their profile info."""

    role = serializers.CharField(source='profile.role', read_only=True)
    is_admin = serializers.BooleanField(source='profile.is_admin', read_only=True)
    tenant_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login',
            'role', 'is_admin', 'tenant_count'
        ]
        read_only_fields = ['date_joined', 'last_login']

    def get_tenant_count(self, obj) -> int:
        """Get count of tenants user has access to."""
        if hasattr(obj, 'profile') and obj.profile.is_admin:
            return Tenant.objects.filter(is_active=True).count()
        return obj.tenant_permissions.count()


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single user with tenant permissions."""

    role = serializers.CharField(source='profile.role', read_only=True)
    is_admin = serializers.BooleanField(source='profile.is_admin', read_only=True)
    tenant_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login',
            'role', 'is_admin', 'tenant_permissions'
        ]
        read_only_fields = ['date_joined', 'last_login']

    def get_tenant_permissions(self, obj) -> list:
        """Get list of tenant permissions for the user."""
        permissions = TenantPermission.objects.filter(user=obj).select_related('tenant')
        return [
            {
                'id': perm.id,
                'tenant_id': perm.tenant.id,
                'tenant_name': perm.tenant.name,
                'granted_at': perm.granted_at,
            }
            for perm in permissions
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    role = serializers.ChoiceField(
        choices=UserProfile.Role.choices,
        default=UserProfile.Role.USER,
        required=False
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role'
        ]

    def validate(self, attrs):
        """Validate password confirmation matches."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords do not match."
            })
        return attrs

    def create(self, validated_data):
        """Create user with profile."""
        role = validated_data.pop('role', UserProfile.Role.USER)
        validated_data.pop('password_confirm')

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
        )

        # Update the profile that was auto-created by the signal
        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing users."""

    role = serializers.ChoiceField(
        choices=UserProfile.Role.choices,
        required=False
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'is_active', 'role', 'password'
        ]

    def update(self, instance, validated_data):
        """Update user and profile."""
        role = validated_data.pop('role', None)
        password = validated_data.pop('password', None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        # Update profile if role provided
        if role and hasattr(instance, 'profile'):
            instance.profile.role = role
            instance.profile.save()

        return instance


class TenantListSerializer(serializers.ModelSerializer):
    """Serializer for listing tenants (without sensitive data)."""

    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'tenant_id', 'organization',
            'auth_method', 'api_method', 'is_active',
            'created_at', 'user_count'
        ]

    def get_user_count(self, obj) -> int:
        """Get count of users with access to this tenant."""
        return obj.user_permissions.count()


class TenantDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for a single tenant (admin view)."""

    user_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True,
        default=None
    )
    # Mask sensitive fields for display
    client_id_masked = serializers.SerializerMethodField()
    has_client_secret = serializers.SerializerMethodField()
    has_certificate = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'tenant_id', 'client_id', 'client_id_masked',
            'organization', 'auth_method', 'api_method',
            'certificate_path', 'certificate_thumbprint',
            'has_client_secret', 'has_certificate',
            'is_active', 'created_at', 'updated_at',
            'created_by', 'created_by_username', 'user_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

    def get_user_count(self, obj) -> int:
        return obj.user_permissions.count()

    def get_client_id_masked(self, obj) -> str:
        """Return masked client_id for display."""
        if obj.client_id:
            return f"{obj.client_id[:8]}...{obj.client_id[-4:]}"
        return ''

    def get_has_client_secret(self, obj) -> bool:
        """Check if client secret is configured."""
        return bool(obj.client_secret)

    def get_has_certificate(self, obj) -> bool:
        """Check if certificate is configured."""
        return bool(obj.certificate_path)


class TenantCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new tenants."""

    class Meta:
        model = Tenant
        fields = [
            'name', 'tenant_id', 'client_id',
            'auth_method', 'client_secret',
            'certificate_path', 'certificate_thumbprint', 'certificate_password',
            'api_method', 'organization', 'is_active'
        ]

    def validate_tenant_id(self, value):
        """Validate tenant_id format (GUID)."""
        import re
        guid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not guid_pattern.match(value):
            raise serializers.ValidationError(
                "Tenant ID must be a valid GUID format."
            )
        return value

    def validate_client_id(self, value):
        """Validate client_id format (GUID)."""
        import re
        guid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        if not guid_pattern.match(value):
            raise serializers.ValidationError(
                "Client ID must be a valid GUID format."
            )
        return value

    def validate(self, attrs):
        """Validate auth method has required credentials."""
        auth_method = attrs.get('auth_method', Tenant.AuthMethod.CERTIFICATE)

        if auth_method == Tenant.AuthMethod.SECRET:
            if not attrs.get('client_secret'):
                raise serializers.ValidationError({
                    'client_secret': "Client secret is required for secret authentication."
                })
        elif auth_method == Tenant.AuthMethod.CERTIFICATE:
            if not attrs.get('certificate_path'):
                raise serializers.ValidationError({
                    'certificate_path': "Certificate path is required for certificate authentication."
                })

        return attrs

    def create(self, validated_data):
        """Create tenant with created_by set to current user."""
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        return super().create(validated_data)


class TenantUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating tenants."""

    class Meta:
        model = Tenant
        fields = [
            'name', 'client_id',
            'auth_method', 'client_secret',
            'certificate_path', 'certificate_thumbprint', 'certificate_password',
            'api_method', 'organization', 'is_active'
        ]

    def validate(self, attrs):
        """Validate auth method has required credentials."""
        instance = self.instance
        auth_method = attrs.get('auth_method', instance.auth_method if instance else None)

        if auth_method == Tenant.AuthMethod.SECRET:
            client_secret = attrs.get('client_secret', instance.client_secret if instance else '')
            if not client_secret:
                raise serializers.ValidationError({
                    'client_secret': "Client secret is required for secret authentication."
                })
        elif auth_method == Tenant.AuthMethod.CERTIFICATE:
            cert_path = attrs.get('certificate_path', instance.certificate_path if instance else '')
            if not cert_path:
                raise serializers.ValidationError({
                    'certificate_path': "Certificate path is required for certificate authentication."
                })

        return attrs


class TenantPermissionSerializer(serializers.ModelSerializer):
    """Serializer for tenant permissions."""

    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    granted_by_username = serializers.CharField(
        source='granted_by.username',
        read_only=True,
        default=None
    )

    class Meta:
        model = TenantPermission
        fields = [
            'id', 'user', 'user_username', 'user_email',
            'tenant', 'tenant_name',
            'granted_at', 'granted_by', 'granted_by_username'
        ]
        read_only_fields = ['granted_at', 'granted_by']


class TenantPermissionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tenant permissions."""

    class Meta:
        model = TenantPermission
        fields = ['user', 'tenant']

    def validate(self, attrs):
        """Validate permission doesn't already exist."""
        user = attrs['user']
        tenant = attrs['tenant']

        # Check if user is admin (they don't need explicit permissions)
        if hasattr(user, 'profile') and user.profile.is_admin:
            raise serializers.ValidationError(
                "Admin users have access to all tenants by default."
            )

        # Check for existing permission
        if TenantPermission.objects.filter(user=user, tenant=tenant).exists():
            raise serializers.ValidationError(
                "User already has permission to this tenant."
            )

        return attrs

    def create(self, validated_data):
        """Create permission with granted_by set to current user."""
        request = self.context.get('request')
        if request and request.user:
            validated_data['granted_by'] = request.user
        return super().create(validated_data)


class BulkTenantPermissionSerializer(serializers.Serializer):
    """Serializer for bulk assigning tenant permissions."""

    user_id = serializers.IntegerField()
    tenant_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True
    )

    def validate_user_id(self, value):
        """Validate user exists."""
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

    def validate_tenant_ids(self, value):
        """Validate all tenants exist."""
        existing_ids = set(Tenant.objects.filter(id__in=value).values_list('id', flat=True))
        invalid_ids = set(value) - existing_ids
        if invalid_ids:
            raise serializers.ValidationError(
                f"Tenants with IDs {list(invalid_ids)} do not exist."
            )
        return value


class CurrentUserSerializer(serializers.ModelSerializer):
    """Serializer for the current authenticated user."""

    role = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    accessible_tenants = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'is_admin', 'accessible_tenants'
        ]

    def get_role(self, obj) -> str:
        """Get user role, defaulting to admin for superusers."""
        if obj.is_superuser or obj.is_staff:
            return 'admin'
        if hasattr(obj, 'profile'):
            return obj.profile.role
        return 'user'

    def get_is_admin(self, obj) -> bool:
        """Check if user is admin (superuser or admin role)."""
        if obj.is_superuser or obj.is_staff:
            return True
        if hasattr(obj, 'profile'):
            return obj.profile.is_admin
        return False

    def get_accessible_tenants(self, obj) -> list:
        """Get list of tenants the user can access."""
        is_admin = obj.is_superuser or obj.is_staff or (
            hasattr(obj, 'profile') and obj.profile.is_admin
        )

        if is_admin:
            # Admin users can access all active tenants
            tenants = Tenant.objects.filter(is_active=True)
        else:
            # Regular users can only access assigned tenants
            tenant_ids = obj.tenant_permissions.values_list('tenant_id', flat=True)
            tenants = Tenant.objects.filter(id__in=tenant_ids, is_active=True)

        return [
            {
                'id': t.id,
                'name': t.name,
                'organization': t.organization,
            }
            for t in tenants
        ]
