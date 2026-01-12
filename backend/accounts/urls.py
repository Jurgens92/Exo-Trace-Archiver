"""
URL configuration for accounts app.

Provides API endpoints for:
- User management (admin only)
- Tenant management (admin only)
- Tenant permissions (admin only)
- Current user profile
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewSet,
    TenantViewSet,
    TenantPermissionViewSet,
    CurrentUserView,
    AccessibleTenantsView,
)

# Create router for ViewSets
router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'permissions', TenantPermissionViewSet, basename='permission')

urlpatterns = [
    # ViewSet routes
    path('', include(router.urls)),

    # Current user endpoints
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/tenants/', AccessibleTenantsView.as_view(), name='accessible-tenants'),
]
