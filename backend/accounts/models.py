"""
Models for multi-tenant user management.

This module provides:
1. UserProfile - Extended user profile with admin role
2. Tenant - Microsoft 365 tenant configurations
3. TenantPermission - Links users to tenants they can access
"""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    Extended user profile that adds role-based access control.

    - Admin users can see all tenants and manage users
    - Regular users can only see tenants they have explicit permission for
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        USER = 'user', 'User'

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
        help_text="User role determines access level"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == self.Role.ADMIN


class Tenant(models.Model):
    """
    Microsoft 365 tenant configuration.

    Stores the Azure AD app registration details and Exchange Online
    configuration for each tenant.
    """

    class AuthMethod(models.TextChoices):
        CERTIFICATE = 'certificate', 'Certificate'
        SECRET = 'secret', 'Client Secret'

    class ApiMethod(models.TextChoices):
        GRAPH = 'graph', 'Microsoft Graph API'
        POWERSHELL = 'powershell', 'Exchange Online PowerShell'

    # Display name for the tenant
    name = models.CharField(
        max_length=255,
        help_text="Friendly name for this tenant (e.g., 'Contoso Production')"
    )

    # Azure AD / Microsoft Entra ID configuration
    tenant_id = models.CharField(
        max_length=36,
        help_text="Azure AD Tenant ID (GUID)"
    )
    client_id = models.CharField(
        max_length=36,
        help_text="Azure AD Application (Client) ID"
    )

    # Authentication method
    auth_method = models.CharField(
        max_length=20,
        choices=AuthMethod.choices,
        default=AuthMethod.CERTIFICATE,
        help_text="Authentication method for this tenant"
    )

    # Client secret (encrypted in production)
    client_secret = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Client secret (only for secret auth method)"
    )

    # Certificate configuration
    certificate_path = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Path to certificate file (.pfx or .pem)"
    )
    certificate_thumbprint = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="Certificate thumbprint (for PowerShell)"
    )
    certificate_password = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Certificate password (if protected)"
    )

    # API method
    api_method = models.CharField(
        max_length=20,
        choices=ApiMethod.choices,
        default=ApiMethod.GRAPH,
        help_text="API method for retrieving message traces"
    )

    # Exchange organization
    organization = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Exchange organization name (e.g., contoso.onmicrosoft.com)"
    )

    # Organization email domains for direction detection
    # Comma-separated list of domains (e.g., "contoso.com,contoso.onmicrosoft.com,contoso.mail.onmicrosoft.com")
    domains = models.TextField(
        blank=True,
        default='',
        help_text="Comma-separated list of organization email domains for direction detection (e.g., contoso.com,contoso.onmicrosoft.com)"
    )

    # Tenant status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this tenant is active for trace collection"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tenants',
        help_text="User who created this tenant"
    )

    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['tenant_id'],
                name='unique_tenant_id'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant_id[:8]}...)"

    def get_organization_domains(self) -> list[str]:
        """
        Get list of organization domains for direction detection.

        Returns domains from:
        1. The explicit 'domains' field (comma-separated)
        2. The 'organization' field as fallback
        """
        result = []

        # First, use the explicit domains field if configured
        if self.domains:
            for domain in self.domains.split(','):
                domain = domain.strip().lower()
                if domain and domain not in result:
                    result.append(domain)

        # If no explicit domains, fall back to organization field
        if not result and self.organization:
            result.append(self.organization.lower())
            # If it's an onmicrosoft.com domain, also add the base domain
            if '.onmicrosoft.com' in self.organization.lower():
                base_domain = self.organization.lower().replace('.onmicrosoft.com', '.com')
                if base_domain not in result:
                    result.append(base_domain)

        return result


class TenantPermission(models.Model):
    """
    Links users to tenants they have permission to access.

    Admin users don't need explicit permissions - they can access all tenants.
    Regular users need a TenantPermission record for each tenant they can access.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='tenant_permissions'
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='user_permissions'
    )

    # When the permission was granted
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_permissions',
        help_text="Admin who granted this permission"
    )

    class Meta:
        verbose_name = 'Tenant Permission'
        verbose_name_plural = 'Tenant Permissions'
        ordering = ['user__username', 'tenant__name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'tenant'],
                name='unique_user_tenant_permission'
            )
        ]

    def __str__(self):
        return f"{self.user.username} -> {self.tenant.name}"


# Signal to create UserProfile when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile for new users."""
    if created:
        # First user (usually the superuser) gets admin role
        is_first_user = User.objects.count() == 1
        role = UserProfile.Role.ADMIN if is_first_user else UserProfile.Role.USER
        UserProfile.objects.create(user=instance, role=role)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure UserProfile is saved when User is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()
