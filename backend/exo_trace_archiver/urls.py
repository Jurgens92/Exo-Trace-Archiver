"""
URL configuration for exo_trace_archiver project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path('admin/', admin.site.urls),
    # DRF token authentication endpoint
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),
    # Accounts app API endpoints (users, tenants, permissions)
    path('api/accounts/', include('accounts.urls')),
    # Traces app API endpoints
    path('api/', include('traces.urls')),
]
