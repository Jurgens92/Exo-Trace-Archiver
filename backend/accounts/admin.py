from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile, Tenant, TenantPermission


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_role')

    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.role
        return '-'
    get_role.short_description = 'Role'


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant_id', 'organization', 'auth_method', 'api_method', 'is_active')
    list_filter = ('is_active', 'auth_method', 'api_method')
    search_fields = ('name', 'tenant_id', 'organization')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TenantPermission)
class TenantPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'granted_at', 'granted_by')
    list_filter = ('tenant', 'granted_at')
    search_fields = ('user__username', 'tenant__name')
    raw_id_fields = ('user', 'tenant', 'granted_by')


# Re-register User admin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
