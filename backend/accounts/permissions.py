"""
Custom permission classes for multi-tenant user management.

Provides:
- IsAdminRole: Check if user has admin role
- HasTenantAccess: Check if user has access to a specific tenant
"""

from rest_framework import permissions

from .models import UserProfile, TenantPermission


class IsAdminRole(permissions.BasePermission):
    """
    Permission class that checks if user has admin role.

    Admin users can:
    - Manage all users
    - Manage all tenants
    - Access all tenant data
    """

    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        """Check if user is authenticated and has admin role."""
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has a profile with admin role
        if hasattr(request.user, 'profile'):
            return request.user.profile.is_admin

        # Fallback to Django's is_staff (for superusers)
        return request.user.is_staff


class HasTenantAccess(permissions.BasePermission):
    """
    Permission class that checks if user has access to a specific tenant.

    - Admin users have access to all tenants
    - Regular users need explicit TenantPermission
    """

    message = "You do not have access to this tenant."

    def has_permission(self, request, view):
        """Basic authentication check."""
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        """Check access to specific tenant or tenant-linked object."""
        user = request.user

        # Admin users have access to everything
        if hasattr(user, 'profile') and user.profile.is_admin:
            return True

        # Get tenant from object (could be Tenant itself or related model)
        tenant = self._get_tenant(obj)
        if not tenant:
            return False

        # Check if user has permission for this tenant
        return TenantPermission.objects.filter(
            user=user,
            tenant=tenant
        ).exists()

    def _get_tenant(self, obj):
        """Extract tenant from object."""
        from .models import Tenant

        # If object is a Tenant itself
        if isinstance(obj, Tenant):
            return obj

        # If object has a tenant attribute (e.g., MessageTraceLog, PullHistory)
        if hasattr(obj, 'tenant'):
            return obj.tenant

        return None


class CanAccessTenantData(permissions.BasePermission):
    """
    Permission for accessing tenant-related data (traces, pull history).

    Used when filtering querysets by tenant access.
    """

    def has_permission(self, request, view):
        """Check basic authentication."""
        return request.user and request.user.is_authenticated


def get_accessible_tenant_ids(user) -> list[int]:
    """
    Get list of tenant IDs a user can access.

    Args:
        user: Django User instance

    Returns:
        List of tenant IDs, or None for admin users (all access)
    """
    from .models import Tenant

    if not user or not user.is_authenticated:
        return []

    # Superusers and admin role users can access all tenants
    if user.is_superuser or user.is_staff:
        return list(Tenant.objects.filter(is_active=True).values_list('id', flat=True))

    if hasattr(user, 'profile') and user.profile.is_admin:
        return list(Tenant.objects.filter(is_active=True).values_list('id', flat=True))

    # Regular users only get explicitly assigned tenants
    return list(
        TenantPermission.objects.filter(user=user)
        .values_list('tenant_id', flat=True)
    )


def user_is_admin(user) -> bool:
    """
    Check if a user has admin role.

    Args:
        user: Django User instance

    Returns:
        True if user is admin, False otherwise
    """
    if not user or not user.is_authenticated:
        return False

    # Django superusers are always admins
    if user.is_superuser or user.is_staff:
        return True

    if hasattr(user, 'profile'):
        return user.profile.is_admin

    return False
